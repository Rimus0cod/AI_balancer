import argparse
import json
import os
import time
from collections import defaultdict
from pathlib import Path

from configs.settings import settings
from src.ai_balancer.ingestion.collector_state import (
    DEFAULT_COLLECTION_ORDER,
    RANK_BUCKETS,
    CollectorState,
    parse_bucket_order,
)
from src.ai_balancer.ingestion.opendota import OpenDotaClient


def bucket_file(out_dir: str, bucket_name: str) -> Path:
    return Path(out_dir) / f"drafts_{bucket_name}.jsonl"


def rows_to_matches(rows: list[dict]) -> list[dict]:
    """Group player rows into one record per match."""
    by_match: dict[int, dict] = {}
    for row in rows:
        match_id = row.get("match_id")
        if match_id is None:
            continue
        match_id = int(match_id)
        match = by_match.get(match_id)
        if match is None:
            match = {
                "match_id": match_id,
                "start_time": row.get("start_time"),
                "duration": row.get("duration"),
                "radiant_win": bool(row.get("radiant_win")),
                "avg_rank_tier": row.get("avg_rank_tier"),
                "players": [],
            }
            by_match[match_id] = match
        hero_id = row.get("hero_id")
        player_slot = row.get("player_slot")
        if hero_id is None or player_slot is None:
            continue
        match["players"].append({
            "hero_id": int(hero_id),
            "player_slot": int(player_slot),
        })

    valid = []
    for match in by_match.values():
        if len(match["players"]) != 10:
            continue
        match["radiant"] = sorted(p["hero_id"] for p in match["players"] if p["player_slot"] < 128)
        match["dire"] = sorted(p["hero_id"] for p in match["players"] if p["player_slot"] >= 128)
        if len(match["radiant"]) == 5 and len(match["dire"]) == 5:
            del match["players"]
            valid.append(match)
    return valid


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for _ in handle)


def main():
    parser = argparse.ArgumentParser(
        description="Bulk-collect draft-only ranked matches via OpenDota Explorer (thousands of matches per request)"
    )
    parser.add_argument("--target-per-bucket", type=int, default=100000,
                        help="Matches per rank bucket (draft data is cheap; think big)")
    parser.add_argument("--buckets", default=",".join(DEFAULT_COLLECTION_ORDER))
    parser.add_argument("--rows-per-request", type=int, default=10000,
                        help="Player rows per explorer request; 10 rows = 1 match. Explorer caps around 10000, so 50000 may 400.")
    parser.add_argument("--hero-chunk", type=int, default=200,
                        help="Match IDs per hero-lookup IN query when JOIN fallback is used (keeps URL short)")
    parser.add_argument("--daily-budget", type=int, default=settings.OPENDOTA_DAILY_REQUEST_BUDGET)
    parser.add_argument("--state-path", default=settings.COLLECTOR_STATE_PATH)
    parser.add_argument("--out-dir", default=os.path.join("data", "bulk"))
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()

    bucket_names = parse_bucket_order(args.buckets)
    state = CollectorState(args.state_path)

    # Bootstrap stored counts from existing files.
    for bucket_name in bucket_names:
        key = f"bulk:{bucket_name}"
        if state.count(key) == 0 and not state.frontier(key):
            stored = count_lines(bucket_file(args.out_dir, bucket_name))
            if stored:
                state.bucket(key)["count"] = stored

    print("Bulk collector state:")
    for line in state.summary([f"bulk:{b}" for b in bucket_names], args.target_per_bucket, args.daily_budget):
        print(f"  {line}")
    if args.summary_only:
        state.save()
        return

    client = OpenDotaClient()

    for bucket_name in bucket_names:
        key = f"bulk:{bucket_name}"
        min_rank, max_rank = RANK_BUCKETS[bucket_name]
        out_path = bucket_file(args.out_dir, bucket_name)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"\n=== Bulk {bucket_name} avg_rank_tier=[{min_rank}, {max_rank}) -> {out_path} ===")

        # Track whether JOIN is permanently rejected so we don't retry a known-bad query every page.
        use_fallback = False

        while state.count(key) < args.target_per_bucket:
            if state.budget_exhausted(args.daily_budget):
                print("Daily request budget exhausted; stopping safely.")
                break

            before = state.frontier(key)
            rows: list[dict] | None = None
            requests_on_page = 0
            fallback_used = use_fallback

            if not use_fallback:
                try:
                    rows = client.fetch_draft_page(
                        min_rank_tier=min_rank,
                        max_rank_tier=max_rank,
                        before_match_id=before,
                        limit=args.rows_per_request,
                    )
                    requests_on_page = 1
                except Exception as exc:
                    msg = str(exc)
                    is_400 = "400" in msg or "Bad Request" in msg
                    if is_400:
                        print(f"{bucket_name}: JOIN rejected by Explorer (400), switching to chunked fallback for this and remaining pages")
                        print(f"  detail: {msg[:600]}")
                        use_fallback = True
                        fallback_used = True
                        rows = None  # trigger fallback below
                    else:
                        print(f"{bucket_name}: explorer request failed ({type(exc).__name__}: {exc}); stopping pass")
                        break

            if fallback_used or rows is None:
                # Fallback: 1 request for match IDs + N requests for heroes in chunks.
                # Still ~ (limit/10)/hero_chunk +1 requests per page, e.g. 1000 matches + chunk 200 => 6 req/page => ~166 matches/req.
                try:
                    match_limit = max(1, args.rows_per_request // 10)
                    meta = client.fetch_public_matches_page(
                        min_rank_tier=min_rank,
                        max_rank_tier=max_rank,
                        before_match_id=before,
                        limit=match_limit,
                    )
                    state.increment_requests()  # meta page
                    if not meta:
                        print(f"{bucket_name}: no more rows; marking exhausted")
                        state.set_exhausted(key, True)
                        break
                    match_ids = [int(r["match_id"]) for r in meta if r.get("match_id") is not None]
                    meta_by_id = {int(r["match_id"]): r for r in meta if r.get("match_id") is not None}

                    hero_rows: list[dict] = []
                    for i in range(0, len(match_ids), args.hero_chunk):
                        chunk = match_ids[i:i + args.hero_chunk]
                        if state.budget_exhausted(args.daily_budget):
                            break
                        chunk_rows = client.fetch_heroes_for_matches(chunk)
                        state.increment_requests()
                        hero_rows.extend(chunk_rows)
                        time.sleep(0.2)

                    # Merge back into the same shape as the JOIN would have returned
                    rows = []
                    for hr in hero_rows:
                        mid = hr.get("match_id")
                        if mid is None:
                            continue
                        mid = int(mid)
                        m = meta_by_id.get(mid)
                        if not m:
                            continue
                        rows.append({
                            "match_id": mid,
                            "start_time": m.get("start_time"),
                            "duration": m.get("duration"),
                            "radiant_win": m.get("radiant_win"),
                            "avg_rank_tier": m.get("avg_rank_tier"),
                            "hero_id": hr.get("hero_id"),
                            "player_slot": hr.get("player_slot"),
                        })
                except Exception as exc:
                    print(f"{bucket_name}: fallback request failed ({type(exc).__name__}: {exc}); stopping pass")
                    break
            else:
                state.increment_requests()

            if not rows:
                print(f"{bucket_name}: no more rows; marking exhausted")
                state.set_exhausted(key, True)
                break

            matches = rows_to_matches(rows)
            page_frontier = min(int(row["match_id"]) for row in rows if row.get("match_id") is not None)

            appended = 0
            with out_path.open("a", encoding="utf-8") as handle:
                for match in matches:
                    handle.write(json.dumps(match, ensure_ascii=False) + "\n")
                    appended += 1

            state.bucket(key)["count"] = int(state.bucket(key).get("count") or 0) + appended
            state.set_frontier(key, page_frontier)
            state.save()
            print(
                f"{bucket_name}: +{appended} matches (page), total={state.count(key)}/{args.target_per_bucket}, "
                f"frontier={page_frontier}, requests={state.requests_today()}/{args.daily_budget}"
            )

    print("\nBulk collection summary:")
    for line in state.summary([f"bulk:{b}" for b in bucket_names], args.target_per_bucket, args.daily_budget):
        print(f"  {line}")


if __name__ == "__main__":
    main()
