from src.ai_balancer.ingestion.opendota import looks_like_ranked, rank_bucket


def test_rank_bucket_maps_rank_tiers():
    assert rank_bucket(12) == "herald"
    assert rank_bucket(24) == "guardian"
    assert rank_bucket(55) == "legend"
    assert rank_bucket(72) == "divine"
    assert rank_bucket(82) == "immortal"
    assert rank_bucket(None) == "unknown"


def test_looks_like_ranked_requires_ranked_mode_and_duration():
    match = {"lobby_type": 7, "game_mode": 22, "duration": 2400}

    assert looks_like_ranked(match) is True
    assert looks_like_ranked({**match, "game_mode": 23}) is False
    assert looks_like_ranked({**match, "lobby_type": 0}) is False
    assert looks_like_ranked({**match, "duration": 600}) is False
