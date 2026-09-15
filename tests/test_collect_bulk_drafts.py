import json

from collect_bulk_drafts import rows_to_matches
from src.ai_balancer.training.hero_draft_baseline import extract_hero_draft_features, load_bulk_matches


def make_rows(match_id=1000):
    rows = []
    for slot in range(10):
        rows.append({
            "match_id": match_id,
            "start_time": 1700000000,
            "duration": 2400,
            "radiant_win": True,
            "avg_rank_tier": 45,
            "hero_id": slot + 1,
            "player_slot": slot if slot < 5 else 123 + slot,
        })
    return rows


def test_rows_to_matches_groups_and_validates():
    matches = rows_to_matches(make_rows())

    assert len(matches) == 1
    assert matches[0]["match_id"] == 1000
    assert len(matches[0]["radiant"]) == 5
    assert len(matches[0]["dire"]) == 5
    assert "players" not in matches[0]

    # Broken match (only 9 players) is dropped.
    broken = make_rows(match_id=2000)[:-1]
    assert rows_to_matches(broken) == []


def test_load_bulk_matches_roundtrip(tmp_path):
    path = tmp_path / "drafts_archon.jsonl"
    match = rows_to_matches(make_rows())[0]
    path.write_text(json.dumps(match) + "\n", encoding="utf-8")

    matches = load_bulk_matches(str(tmp_path))

    assert len(matches) == 1
    loaded = matches[0]
    assert loaded.match_id == 1000
    assert loaded.avg_rank_tier == 45
    assert len(loaded.players) == 10
    features = extract_hero_draft_features(loaded)
    assert sum(v for v in features.values()) == 0  # 5 radiant (+1) and 5 dire (-1)
