import argparse
import os

from configs.settings import settings
from src.ai_balancer.training.model_report import load_model, top_weights


def main():
    parser = argparse.ArgumentParser(description="Inspect the hero-draft baseline model")
    parser.add_argument("--model-path", default=os.path.join(settings.MODEL_DIR, "hero_draft_baseline_ranked.json"))
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    model = load_model(args.model_path)
    metrics = model.get("metrics", {})
    weights = model.get("weights", {})
    positive, negative = top_weights(weights, args.limit)

    print(f"Model version: {model.get('model_version')}")
    print(f"Weights: {len(weights)} heroes")
    print(f"Metrics: {metrics}")

    print("Top positive Radiant-side hero weights:")
    for hero_id, weight in positive:
        print(f"  hero_id={hero_id}: {weight:.4f}")

    print("Top negative Radiant-side hero weights:")
    for hero_id, weight in negative:
        print(f"  hero_id={hero_id}: {weight:.4f}")


if __name__ == "__main__":
    main()
