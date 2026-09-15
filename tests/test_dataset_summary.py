from tests.test_transformer import make_raw_match

from src.ai_balancer.processing.transformer import transform_opendota_match
from src.ai_balancer.quality.dataset_summary import summarize_matches


def test_summarize_matches_reports_core_dataset_stats():
    radiant_win = transform_opendota_match(make_raw_match())
    dire_win_raw = make_raw_match()
    dire_win_raw["match_id"] = 1234567891
    dire_win_raw["radiant_win"] = False
    dire_win = transform_opendota_match(dire_win_raw)

    summary = summarize_matches([radiant_win, dire_win])

    assert summary["processed_matches"] == 2
    assert summary["radiant_win_rate"] == 0.5
    assert summary["unique_heroes"] == 10
    assert summary["patches"] == {"57": 2}
    assert summary["duration_seconds"]["avg"] == 2400
    assert summary["game_modes"] == {"22": 2}
    assert summary["lobby_types"] == {"7": 2}
    assert summary["rank_buckets"] == {"legend": 2}
    assert summary["avg_rank_tier"] == 55


def test_summarize_matches_handles_empty_dataset():
    summary = summarize_matches([])

    assert summary["processed_matches"] == 0
    assert summary["radiant_win_rate"] is None
    assert summary["unique_heroes"] == 0
