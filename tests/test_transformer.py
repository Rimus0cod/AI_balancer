from src.ai_balancer.processing.transformer import (
    determine_team,
    transform_opendota_match,
    validate_and_report,
)


def make_raw_match(player_count=10):
    players = []
    for index in range(player_count):
        is_dire = index >= 5
        players.append(
            {
                "account_id": 1000 + index,
                "player_slot": 128 + index - 5 if is_dire else index,
                "hero_id": index + 1,
                "kills": index,
                "deaths": 10 - index,
                "assists": index * 2,
                "net_worth": 5000 + index,
                "gold_per_min": 400 + index,
                "xp_per_min": 500 + index,
                "rank_tier": 55,
                "lane": 1,
                "lane_role": 2,
            }
        )

    return {
        "match_id": 1234567890,
        "start_time": 1700000000,
        "duration": 2400,
        "radiant_win": True,
        "game_mode": 22,
        "lobby_type": 7,
        "patch": 57,
        "region": 3,
        "avg_rank_tier": 55,
        "players": players,
    }


def test_determine_team_from_player_slot():
    assert determine_team(0) == 0
    assert determine_team(127) == 0
    assert determine_team(128) == 1


def test_transform_opendota_match_normalizes_core_fields():
    match = transform_opendota_match(make_raw_match())

    assert match.match_id == 1234567890
    assert match.duration == 2400
    assert match.radiant_win is True
    assert len(match.players) == 10
    assert [player.team for player in match.players[:5]] == [0, 0, 0, 0, 0]
    assert [player.team for player in match.players[5:]] == [1, 1, 1, 1, 1]
    assert match.players[0].gpm == 400
    assert match.players[0].xpm == 500
    assert match.players[0].role == 2
    assert match.avg_rank_tier == 55


def test_validate_and_report_passes_valid_match():
    match, report = validate_and_report(make_raw_match())

    assert match is not None
    assert report.startswith("PASS")


def test_validate_and_report_fails_invalid_player_count():
    match, report = validate_and_report(make_raw_match(player_count=9))

    assert match is None
    assert report.startswith("FAIL")
    assert "Validation error" in report


def test_validate_and_report_fails_missing_required_key():
    raw = make_raw_match()
    del raw["duration"]

    match, report = validate_and_report(raw)

    assert match is None
    assert report == "FAIL: Missing critical key in raw data: 'duration'"
