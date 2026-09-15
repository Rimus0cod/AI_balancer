import pytest

from src.ai_balancer.ingestion.collector_state import CollectorState, parse_bucket_order


def test_collector_state_persists_bucket_progress(tmp_path):
    state_path = tmp_path / "collector_state.json"
    state = CollectorState(str(state_path))

    state.record_match("archon", 123)
    state.set_frontier("archon", 100)
    state.increment_requests(2)
    state.save()

    reloaded = CollectorState(str(state_path))

    assert reloaded.count("archon") == 1
    assert reloaded.ids("archon") == {123}
    assert reloaded.frontier("archon") == 100
    assert reloaded.requests_today() == 2
    assert reloaded.remaining_requests(10) == 8


def test_parse_bucket_order_accepts_all_and_rejects_unknown():
    assert parse_bucket_order("archon,legend") == ["archon", "legend"]
    assert "archon" in parse_bucket_order("all")

    with pytest.raises(ValueError):
        parse_bucket_order("archon,bad")
