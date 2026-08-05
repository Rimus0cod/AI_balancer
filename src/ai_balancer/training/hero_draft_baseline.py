import json
import math
import random
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from src.ai_balancer.schemas.match import Match


MODEL_VERSION = "hero-draft-logistic-v1"


def extract_hero_draft_features(match: Match) -> Dict[str, int]:
    features: Dict[str, int] = {}
    for player in match.players:
        value = 1 if player.team == 0 else -1
        key = str(player.hero_id)
        features[key] = features.get(key, 0) + value
    return features


def sigmoid(value: float) -> float:
    if value < -30:
        return 0.0
    if value > 30:
        return 1.0
    return 1 / (1 + math.exp(-value))


def predict_probability(features: Dict[str, int], weights: Dict[str, float], bias: float) -> float:
    score = bias
    for hero_id, value in features.items():
        score += weights.get(hero_id, 0.0) * value
    return sigmoid(score)


def train_hero_draft_model(
    matches: Iterable[Match],
    epochs: int = 25,
    learning_rate: float = 0.05,
    validation_fraction: float = 0.2,
    seed: int = 42,
) -> Tuple[Dict[str, object], Dict[str, float]]:
    training_rows = [
        (extract_hero_draft_features(match), 1.0 if match.radiant_win else 0.0)
        for match in matches
    ]
    if not training_rows:
        raise ValueError("No processed matches found for training")

    rng = random.Random(seed)
    rng.shuffle(training_rows)

    validation_size = int(len(training_rows) * validation_fraction)
    if len(training_rows) >= 5:
        validation_size = max(1, validation_size)
    validation_rows = training_rows[:validation_size]
    train_rows = training_rows[validation_size:]
    if not train_rows:
        train_rows = training_rows
        validation_rows = []

    weights: Dict[str, float] = {}
    bias = 0.0

    for _ in range(epochs):
        for features, label in train_rows:
            prediction = predict_probability(features, weights, bias)
            error = prediction - label
            bias -= learning_rate * error

            for hero_id, value in features.items():
                weights[hero_id] = weights.get(hero_id, 0.0) - learning_rate * error * value

    train_metrics = evaluate_rows(train_rows, weights, bias)
    validation_metrics = evaluate_rows(validation_rows, weights, bias) if validation_rows else {}

    metrics = flatten_metrics(train_metrics, validation_metrics)
    model = {
        "model_version": MODEL_VERSION,
        "trained_at": time.time(),
        "epochs": epochs,
        "learning_rate": learning_rate,
        "validation_fraction": validation_fraction,
        "seed": seed,
        "bias": bias,
        "weights": weights,
        "metrics": metrics,
    }
    return model, metrics


def evaluate_rows(rows: List[Tuple[Dict[str, int], float]], weights: Dict[str, float], bias: float) -> Dict[str, float]:
    if not rows:
        return {"samples": 0.0, "accuracy": 0.0, "log_loss": 0.0}

    correct = 0
    total_loss = 0.0
    for features, label in rows:
        prediction = predict_probability(features, weights, bias)
        predicted_label = 1.0 if prediction >= 0.5 else 0.0
        if predicted_label == label:
            correct += 1
        total_loss += -(label * math.log(max(prediction, 1e-12)) + (1 - label) * math.log(max(1 - prediction, 1e-12)))

    return {
        "samples": float(len(rows)),
        "accuracy": correct / len(rows),
        "log_loss": total_loss / len(rows),
    }


def flatten_metrics(train_metrics: Dict[str, float], validation_metrics: Dict[str, float]) -> Dict[str, float]:
    metrics = {
        "train_samples": train_metrics["samples"],
        "train_accuracy": train_metrics["accuracy"],
        "train_log_loss": train_metrics["log_loss"],
    }
    if validation_metrics:
        metrics.update(
            {
                "validation_samples": validation_metrics["samples"],
                "validation_accuracy": validation_metrics["accuracy"],
                "validation_log_loss": validation_metrics["log_loss"],
            }
        )
    return metrics


def load_processed_matches(processed_dir: str) -> List[Match]:
    matches = []
    for path in sorted(Path(processed_dir).rglob("*.json")):
        matches.append(Match.model_validate_json(path.read_text(encoding="utf-8")))
    return matches


def save_model(model: Dict[str, object], model_path: str) -> str:
    path = Path(model_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model, indent=2, sort_keys=True), encoding="utf-8")
    return str(path)
