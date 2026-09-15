import argparse
import os

from configs.settings import settings
from src.ai_balancer.ingestion.opendota import rank_bucket
from src.ai_balancer.training.hero_draft_baseline import (
    load_bulk_matches,
    load_processed_matches,
    save_model,
    train_hero_draft_model,
)


def main():
    parser = argparse.ArgumentParser(description="Train a baseline hero-draft win probability model")
    parser.add_argument("--processed-dir", default=settings.RANKED_PROCESSED_DATA_DIR)
    parser.add_argument("--bulk-dir", default=None,
                        help="Optional dir with drafts_*.jsonl from collect_bulk_drafts.py; merged into training data")
    parser.add_argument("--processed-only", action="store_true",
                        help="Skip default processed dir (use only --bulk-dir)")
    parser.add_argument("--model-path", default=None)
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-rank-tier", type=int, default=0)
    parser.add_argument(
        "--rank-bucket",
        default="all",
        choices=["all", "herald", "guardian", "crusader", "archon", "legend", "ancient", "divine", "immortal", "unknown"],
    )
    args = parser.parse_args()

    matches = [] if args.processed_only else load_processed_matches(args.processed_dir)
    if args.bulk_dir:
        bulk = load_bulk_matches(args.bulk_dir)
        print(f"Bulk draft matches loaded: {len(bulk)}")
        matches.extend(bulk)
    if not matches:
        print("No training data found")
        return
    if args.min_rank_tier > 0:
        matches = [match for match in matches if (match.avg_rank_tier or 0) >= args.min_rank_tier]
    if args.rank_bucket != "all":
        matches = [match for match in matches if rank_bucket(match.avg_rank_tier) == args.rank_bucket]

    model_path = args.model_path
    if model_path is None:
        suffix = args.rank_bucket if args.rank_bucket != "all" else "ranked"
        if args.min_rank_tier > 0:
            suffix += f"_min{args.min_rank_tier}"
        model_path = os.path.join(settings.MODEL_DIR, f"hero_draft_baseline_{suffix}.json")

    model, metrics = train_hero_draft_model(
        matches,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        validation_fraction=args.validation_fraction,
        seed=args.seed,
    )
    model_path = save_model(model, model_path)

    print(f"Loaded processed matches: {len(matches)}")
    print(f"Rank bucket: {args.rank_bucket}")
    print(f"Min rank tier: {args.min_rank_tier}")
    print(f"Train samples: {metrics['train_samples']:.0f}")
    print(f"Train accuracy: {metrics['train_accuracy']:.3f}")
    print(f"Train log loss: {metrics['train_log_loss']:.3f}")
    if "validation_samples" in metrics:
        print(f"Validation samples: {metrics['validation_samples']:.0f}")
        print(f"Validation accuracy: {metrics['validation_accuracy']:.3f}")
        print(f"Validation log loss: {metrics['validation_log_loss']:.3f}")
    print(f"Model saved to {model_path}")


if __name__ == "__main__":
    main()
