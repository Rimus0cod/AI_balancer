from tests.test_transformer import make_raw_match

from src.ai_balancer.processing.transformer import transform_opendota_match
from src.ai_balancer.training.hero_draft_baseline import (
    extract_hero_draft_features,
    predict_probability,
    train_hero_draft_model,
)


def test_extract_hero_draft_features_marks_radiant_and_dire():
    match = transform_opendota_match(make_raw_match())

    features = extract_hero_draft_features(match)

    assert features["1"] == 1
    assert features["5"] == 1
    assert features["6"] == -1
    assert features["10"] == -1


def test_train_hero_draft_model_returns_metrics_and_weights():
    radiant_win = transform_opendota_match(make_raw_match())
    dire_win_raw = make_raw_match()
    dire_win_raw["radiant_win"] = False
    dire_win = transform_opendota_match(dire_win_raw)

    model, metrics = train_hero_draft_model([radiant_win, dire_win], epochs=2, learning_rate=0.01)

    assert model["model_version"] == "hero-draft-logistic-v1"
    assert metrics["train_samples"] == 2.0
    assert 0.0 <= metrics["train_accuracy"] <= 1.0
    assert isinstance(model["weights"], dict)


def test_predict_probability_is_bounded():
    probability = predict_probability({"1": 1}, {"1": 100.0}, 0.0)

    assert 0.0 <= probability <= 1.0
