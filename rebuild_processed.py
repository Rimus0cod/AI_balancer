import argparse
import json
from pathlib import Path

from configs.settings import settings
from src.ai_balancer.ingestion.opendota import looks_like_ranked, rank_bucket
from src.ai_balancer.processing.transformer import validate_and_report
from src.ai_balancer.storage.local import LocalStorage


def clear_processed_dirs():
    processed_root = Path("data") / "processed"
    if not processed_root.exists():
        return
    for path in processed_root.rglob("*.json"):
        path.unlink()


def rebuild(include_filtered: bool):
    storage = LocalStorage()
    stats = {"ranked": 0, "filtered": 0, "invalid": 0}

    for raw_path in sorted(Path(settings.RAW_DATA_DIR).glob("*.json")):
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        raw_data = payload.get("raw_data", {})
        match_obj, _ = validate_and_report(raw_data)

        if not match_obj:
            stats["invalid"] += 1
            continue

        if looks_like_ranked(raw_data):
            bucket = rank_bucket(match_obj.avg_rank_tier)
            storage.save_processed_to(
                str(Path(settings.RANKED_PROCESSED_DATA_DIR) / bucket / f"{match_obj.match_id}.json"),
                match_obj,
            )
            stats["ranked"] += 1
        elif include_filtered:
            storage.save_processed_filtered(match_obj.match_id, match_obj)
            stats["filtered"] += 1
        else:
            stats["filtered"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Rebuild processed datasets from preserved raw OpenDota payloads")
    parser.add_argument("--clear", action="store_true", help="Delete existing data/processed/**/*.json before rebuilding")
    parser.add_argument("--include-filtered", action="store_true", help="Also write non-ranked valid matches to data/processed/filtered")
    args = parser.parse_args()

    if args.clear:
        clear_processed_dirs()
        print("Cleared existing processed JSON files")

    stats = rebuild(include_filtered=args.include_filtered)
    print(
        "Rebuilt processed data: "
        f"ranked={stats['ranked']}, filtered={stats['filtered']}, invalid={stats['invalid']}"
    )


if __name__ == "__main__":
    main()
