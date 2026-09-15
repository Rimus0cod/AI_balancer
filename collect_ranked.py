import argparse
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from configs.settings import settings
from src.ai_balancer.ingestion.collector_state import (
    DEFAULT_COLLECTION_ORDER,
    RANK_BUCKETS,
    CollectorState,
    parse_bucket_order,
)
from src.ai_balancer.ingestion.opendota import OpenDotaClient, looks_like_ranked, rank_bucket
from src.ai_balancer.processing.transformer import validate_and_report
from src.ai_balancer.storage.local import LocalStorage


class RatePacer:
    """Thread-safe pacing to a fixed requests-per-minute ceiling."""

    def __init__(self, rpm: float):
        self.min_interval = 60.0 / max(rpm, 0.01)
        self._lock = threading.Lock()
        self._next_slot = time.monotonic()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next_slot - now
            if wait <= 0:
                self._next_slot = now + self.min_interval
                return
            self._next_slot += self.min_interval
        time.sleep(wait)


def processed_path(bucket_name: str, match_id: int) -> str:
    return os.path.join(settings.RANKED_PROCESSED_DATA_DIR, bucket_name, f"{match_id}.json")


def bootstrap_existing_files(state: CollectorState, bucket_names: list[str]) -> None:
    for bucket_name in bucket_names:
        bucket_dir = Path(settings.RANKED_PROCESSED_DATA_DIR) / bucket_name
        for path in bucket_dir.glob("*.json"):
            if path.stem.isdigit():
                state.record_match(bucket_name, int(path.stem))
    state.save()


def ingest_detail(
    client: OpenDotaClient,
    storage: LocalStorage,
    bucket_name: str,
    row: dict,
) -> tuple[bool, str]:
    match_id = int(row["match_id"])
    existing_path = processed_path(bucket_name, match_id)
    if os.path.exists(existing_path):
        return True, "exists"

    raw_data, provenance = client.fetch_match(match_id)
    raw_path = storage.save_raw(match_id, raw_data, provenance)

    if raw_data.get("avg_rank_tier") is None and row.get("avg_rank_tier") is not None:
        raw_data["avg_rank_tier"] = row.get("avg_rank_tier")

    if not looks_like_ranked(raw_data):
        return False, f"filtered-detail raw={raw_path}"

    match_obj, report = validate_and_report(raw_data)
    if not match_obj:
        return False, report

    storage.save_processed_to(existing_path, match_obj)
    return True, f"saved dur={match_obj.duration}s tier={match_obj.avg_rank_tier} ({rank_bucket(match_obj.avg_rank_tier)})"


def fetch_row_task(client: OpenDotaClient, storage: LocalStorage, bucket_name: str, row: dict, pacer: "RatePacer | None"):
    """Worker entry for parallel collection; safe because client/storage are stateless per call."""
    if pacer is not None:
        pacer.acquire()
    match_id = int(row["match_id"])
    try:
        ok, message = ingest_detail(client, storage, bucket_name, row)
    except Exception as exc:
        ok, message = False, f"unhandled: {type(exc).__name__}: {exc}"
    return match_id, ok, message


def main():
    parser = argparse.ArgumentParser(description="Collect ranked OpenDota matches by rank bucket with resumable state")
    parser.add_argument("--target-per-bucket", type=int, default=10000)
    parser.add_argument("--buckets", default=",".join(DEFAULT_COLLECTION_ORDER),
                        help="Comma-separated rank buckets, or 'all'")
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Delay between detail requests in sequential mode. Auto-raised to respect daily budget.")
    parser.add_argument("--workers", type=int, default=1,
                        help="Parallel detail fetchers. >1 switches to paced parallel mode (--rpm governs speed).")
    parser.add_argument("--rpm", type=float, default=0,
                        help="Requests per minute ceiling in parallel mode. 0 = derive from daily budget (budget/1440).")
    parser.add_argument("--daily-budget", type=int, default=settings.OPENDOTA_DAILY_REQUEST_BUDGET)
    parser.add_argument("--state-path", default=settings.COLLECTOR_STATE_PATH)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    bucket_names = parse_bucket_order(args.buckets)
    state = CollectorState(args.state_path)
    bootstrap_existing_files(state, bucket_names)

    print("Collector state:")
    for line in state.summary(bucket_names, args.target_per_bucket, args.daily_budget):
        print(f"  {line}")
    if args.summary_only:
        return

    client = OpenDotaClient()
    storage = LocalStorage()

    for bucket_name in bucket_names:
        min_rank, max_rank = RANK_BUCKETS[bucket_name]
        print(f"\n=== Bucket {bucket_name} avg_rank_tier=[{min_rank}, {max_rank}) ===")

        while state.count(bucket_name) < args.target_per_bucket:
            if state.budget_exhausted(args.daily_budget):
                print("Daily request budget exhausted; stopping safely.")
                state.save()
                for line in state.summary(bucket_names, args.target_per_bucket, args.daily_budget):
                    print(f"  {line}")
                return

            before_match_id = state.frontier(bucket_name)
            try:
                page = client.fetch_public_matches_page(
                    min_rank_tier=min_rank,
                    max_rank_tier=max_rank,
                    before_match_id=before_match_id,
                    limit=args.page_size,
                )
            except Exception as exc:
                print(f"{bucket_name}: explorer page failed ({type(exc).__name__}: {exc}); keep going")
                state.save()
                break
            state.increment_requests()

            if not page:
                # Empty response can mean either end-of-list or a transient network drop.
                # Don't mark exhausted unless we have a signal; just break so state is durable.
                print(f"{bucket_name}: empty explorer page; assuming end-of-list (or transient issue)")
                state.set_exhausted(bucket_name, True)
                state.save()
                break

            page_frontier = min(
                (int(row["match_id"]) for row in page if row.get("match_id") is not None),
                default=None,
            )
            fully_processed_page = True
            saved_on_page = 0

            seen = state.ids(bucket_name)
            pending = []
            for row in page:
                if state.count(bucket_name) >= args.target_per_bucket:
                    break
                match_id = row.get("match_id")
                if match_id is None or int(match_id) in seen:
                    continue
                pending.append(row)

            def record_result(match_id: int, ok: bool, message: str) -> None:
                nonlocal saved_on_page
                state.increment_requests()
                if ok:
                    state.record_match(bucket_name, match_id)
                    saved_on_page += 1
                    if state.count(bucket_name) % args.progress_every == 0:
                        remaining = max(0, args.target_per_bucket - state.count(bucket_name))
                        print(
                            f"{bucket_name}: {state.count(bucket_name)}/{args.target_per_bucket} "
                            f"remaining={remaining}; requests={state.requests_today()}/{args.daily_budget}"
                        )
                else:
                    print(f"{bucket_name}:{match_id}: skipped ({message})")

            if args.workers > 1:
                rpm = args.rpm or max(1.0, args.daily_budget / 1440.0)
                pacer = RatePacer(rpm)
                with ThreadPoolExecutor(max_workers=args.workers) as pool:
                    futures = {}
                    for row in pending:
                        if state.budget_exhausted(args.daily_budget) or state.count(bucket_name) >= args.target_per_bucket:
                            fully_processed_page = False
                            break
                        futures[pool.submit(fetch_row_task, client, storage, bucket_name, row, pacer)] = int(row["match_id"])

                    for fut in as_completed(futures):
                        match_id, ok, message = fut.result()
                        record_result(match_id, ok, message)

                        if state.budget_exhausted(args.daily_budget) and not fut.done():
                            continue
            else:
                pacer = None
                for row in pending:
                    match_id, ok, message = fetch_row_task(client, storage, bucket_name, row, pacer)
                    record_result(match_id, ok, message)
                    if args.delay > 0:
                        time.sleep(args.delay)
                    if state.budget_exhausted(args.daily_budget):
                        fully_processed_page = False
                        break

            if fully_processed_page:
                state.set_frontier(bucket_name, page_frontier)
            state.save()
            print(
                f"{bucket_name}: page done saved={saved_on_page}, "
                f"total={state.count(bucket_name)}/{args.target_per_bucket}, "
                f"frontier={state.frontier(bucket_name)}, "
                f"requests={state.requests_today()}/{args.daily_budget}"
            )

            if not fully_processed_page:
                print("Stopped mid-page because the daily request budget is exhausted.")
                break

    print("\nCollection pass completed:")
    for line in state.summary(bucket_names, args.target_per_bucket, args.daily_budget):
        print(f"  {line}")


if __name__ == "__main__":
    main()
