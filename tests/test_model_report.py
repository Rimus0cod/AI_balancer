from src.ai_balancer.training.model_report import top_weights


def test_top_weights_returns_positive_and_negative_extremes():
    positive, negative = top_weights({"1": 0.5, "2": -0.2, "3": 1.0}, limit=1)

    assert positive == [("3", 1.0)]
    assert negative == [("2", -0.2)]
