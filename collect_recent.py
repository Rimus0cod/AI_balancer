import argparse
import os
import time
from typing import Literal, Optional

from configs.settings import settings
from src.ai_balancer.ingestion.opendota import OpenDotaClient, looks_like_ranked, rank_bucket
from src.ai_balancer.processing.transformer import validate_and_report
from src.ai_balancer.storage.local import LocalStorage

IngestStatus = Literal["processed", "skipped", "filtered", "invalid"]


def processed_path_for(category: str, match_id: int) -> str:
    target_dir = {
        "ranked": settings.RANKED_PROCESSED_DATA_DIR,
        "unranked": settings.UNRANKED_PROCESSED_DATA_DIR,
        "filtered": settings.FILTERED_PROCESSED_DATA_DIR,
    }[category]
    return os.path.join(target_dir, f"{match_id}.json")


def try_validate(raw: dict):
    """Returns (match_obj, error_report)."""
    return validate_and_report(raw)


def ingest_match(
    client: OpenDotaClient,
    storage: LocalStorage,
    match_id: int,
    skip_existing: bool,
    target: str,
    listing_avg_rank_tier: Optional[int],
) -> IngestStatus:
    if skip_existing and os.path.exists(processed_path_for(target, match_id)):
        return "skipped"

    raw_data, provenance = client.fetch_match(match_id)
    raw_path = storage.save_raw(match_id, raw_data, provenance)

    if raw_data.get("avg_rank_tier") is None and listing_avg_rank_tier is not None:
        raw_data["avg_rank_tier"] = listing_avg_rank_tier

    if target == "ranked" and not looks_like_ranked(raw_data):
        print(f"{match_id}: detail check failed ranked gates (raw kept in {raw_path})")
        return "filtered"

    match_obj, report = try_validate(raw_data)

    if not match_obj:
        print(f"{match_id}: {report}  (raw kept in {raw_path})")
        return "invalid"

    processed_path = os.path.join(
        {
            "ranked": settings.RANKED_PROCESSED_DATA_DIR,
            "unranked": settings.UNRANKED_PROCESSED_DATA_DIR,
            "filtered": settings.FILTERED_PROCESSED_DATA_DIR,
        }[target],
        f"{match_id}.json",
    )
    storage.save_processed_to(processed_path, match_obj)
    print(
        f"{match_id}: saved -> {target} "
        f"dur={match_obj.duration}s tier={match_obj.avg_rank_tier} ({rank_bucket(match_obj.avg_rank_tier)})"
    )
    return "processed"


def main():
    parser = argparse.ArgumentParser(description="Collect recent public matches with quality filters")
    parser.add_argument("--count", type=int, default=50,
                        help="How many robust matches to store in data/processed/ranked")
    parser.add_argument("--limit", type=int, dest="count", help="Backward-compatible alias for --count")
    parser.add_argument("--lookback", type=int, default=500,
                        help="How many recent public matches to scan to find enough ranked games")
    parser.add_argument("--delay", type=float, default=1.5, help="Delay between match detail requests")
    parser.add_argument("--skip-existing", action="store_true", help="Skip already processed matches")
    parser.add_argument("--stop-after-errors", type=int, default=10)
    parser.add_argument("--min-rank-tier", type=int, default=settings.MIN_MATCH_AVG_RANK_TIER,
                        help="Listing-level filter, e.g. 70 for Ancient+ games")
    args = parser.parse_args()

    client = OpenDotaClient()
    storage = LocalStorage()

    listing = client.fetch_public_matches(max_limit=args.lookback, min_rank_tier=args.min_rank_tier)
    print(f"Fetched {len(listing)} raw listings from OpenDota (lookback={args.lookback}, min_rank_tier={args.min_rank_tier})")

    stored = 0
    stats = {"processed": 0, "skipped": 0, "filtered": 0, "invalid": 0}
    consecutive_errors = 0

    for row in listing:
        if stored >= args.count:
            break
        match_id = row.get("match_id")
        if match_id is None:
            stats["filtered"] += 1
            continue
        duration = row.get("duration") or 0
        lobby_ok = (row.get("lobby_type") == settings.REQUIRED_LOBBY_TYPE
                    and row.get("game_mode") == settings.REQUIRED_GAME_MODE)
        long_enough = duration >= settings.MIN_MATCH_DURATION_SECONDS

        if not (lobby_ok and long_enough):
            stats["filtered"] += 1
            continue

        target = "ranked"
        try:
            status = ingest_match(
                client,
                storage,
                match_id,
                args.skip_existing,
                target,
                row.get("avg_rank_tier"),
            )
        except Exception as exc:
            consecutive_errors += 1
            print(f"{match_id}: ERROR: {exc}")
            if consecutive_errors >= args.stop_after_errors:
                print(f"Stopping after {consecutive_errors} consecutive errors")
                break
            if args.delay > 0:
                time.sleep(args.delay)
            continue

        consecutive_errors = 0
        stats[status] += 1
        if status == "processed":
            stored += 1

        if args.delay > 0:
            time.sleep(args.delay)

    print(
        f"Finished: requested_ranked={args.count} new_ranked={stored} "
        f"(listing scan={len(listing)}, filtered_out={stats['filtered']}, "
        f"already_processed={stats['skipped']}, invalid={stats['invalid']})"
    )


if __name__ == "__main__":
    main()
