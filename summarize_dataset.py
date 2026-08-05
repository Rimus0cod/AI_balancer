import argparse

from configs.settings import settings
from src.ai_balancer.quality.dataset_summary import (
    load_processed_matches,
    summarize_matches,
    summarize_raw_quality,
)


def main():
    parser = argparse.ArgumentParser(description="Summarize local AI Balancer data")
    parser.add_argument("--raw-dir", default=settings.RAW_DATA_DIR)
    parser.add_argument("--processed-dir", default=settings.RANKED_PROCESSED_DATA_DIR)
    args = parser.parse_args()

    matches = load_processed_matches(args.processed_dir)
    match_summary = summarize_matches(matches)
    raw_summary = summarize_raw_quality(args.raw_dir, args.processed_dir)

    print(f"Raw matches: {raw_summary['raw_matches']}")
    print(f"Processed matches: {match_summary['processed_matches']}")
    print(f"Raw without processed: {raw_summary['raw_without_processed']}")
    print(f"Raw duration=0: {raw_summary['raw_duration_zero']}")
    print(f"Unique heroes: {match_summary['unique_heroes']}")

    if match_summary["radiant_win_rate"] is not None:
        print(f"Radiant win rate: {match_summary['radiant_win_rate']:.3f}")
        duration = match_summary["duration_seconds"]
        print(f"Duration seconds: min={duration['min']}, avg={duration['avg']:.1f}, max={duration['max']}")
        if match_summary["avg_rank_tier"] is not None:
            print(f"Average rank tier: {match_summary['avg_rank_tier']:.1f}")

    print(f"Patches: {match_summary['patches']}")
    print(f"Game modes: {match_summary['game_modes']}")
    print(f"Lobby types: {match_summary['lobby_types']}")
    print(f"Rank buckets: {match_summary['rank_buckets']}")


if __name__ == "__main__":
    main()
