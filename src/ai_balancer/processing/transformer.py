from pydantic import ValidationError
from src.ai_balancer.schemas.match import Match, Player


def determine_team(player_slot: int) -> int:
    """OpenDota player_slot: 0-127 are Radiant, 128-255 are Dire"""
    return 0 if player_slot < 128 else 1


def derive_avg_rank_tier(raw: dict):
    if raw.get("avg_rank_tier") is not None:
        return raw.get("avg_rank_tier")

    rank_tiers = [
        player.get("rank_tier")
        for player in raw.get("players", [])
        if isinstance(player.get("rank_tier"), int)
    ]
    if not rank_tiers:
        return None
    return round(sum(rank_tiers) / len(rank_tiers))


def transform_opendota_match(raw: dict) -> Match:
    """Transforms raw OpenDota JSON into our normalized Match schema."""
    players = []
    for p in raw.get("players", []):
        players.append(Player(
            account_id=p.get("account_id"),
            player_slot=p.get("player_slot"),
            hero_id=p.get("hero_id", 0),
            team=determine_team(p.get("player_slot", 0)),
            kills=p.get("kills", 0),
            deaths=p.get("deaths", 0),
            assists=p.get("assists", 0),
            net_worth=p.get("net_worth"),
            gpm=p.get("gold_per_min"),
            xpm=p.get("xp_per_min"),
            lane=p.get("lane"),
            role=p.get("lane_role")
        ))

    return Match(
        match_id=raw["match_id"],
        start_time=raw["start_time"],
        duration=raw["duration"],
        radiant_win=raw["radiant_win"],
        game_mode=raw["game_mode"],
        lobby_type=raw["lobby_type"],
        patch=raw.get("patch"),
        region=raw.get("region"),
        avg_rank_tier=derive_avg_rank_tier(raw),
        players=players
    )

def validate_and_report(raw_data: dict):
    """Validates data and returns (Match_object, Error_Report)."""
    try:
        match_obj = transform_opendota_match(raw_data)
        return match_obj, "PASS: All schema validations passed."
    except ValidationError as e:
        return None, f"FAIL: Validation error. Details:\n{e.json()}"
    except KeyError as e:
        return None, f"FAIL: Missing critical key in raw data: {e}"
