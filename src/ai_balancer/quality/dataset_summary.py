import json
from collections import Counter
from pathlib import Path
from typing import Dict, List

from src.ai_balancer.ingestion.opendota import rank_bucket
from src.ai_balancer.schemas.match import Match


def load_processed_matches(processed_dir: str) -> List[Match]:
    return [
        Match.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(Path(processed_dir).rglob("*.json"))
    ]


def summarize_matches(matches: List[Match]) -> Dict[str, object]:
    if not matches:
        return {
            "processed_matches": 0,
            "radiant_win_rate": None,
            "unique_heroes": 0,
            "patches": {},
            "game_modes": {},
            "lobby_types": {},
            "rank_buckets": {},
            "duration_seconds": {},
            "avg_rank_tier": None,
        }

    durations = [match.duration for match in matches]
    patches = Counter(str(match.patch) if match.patch is not None else "unknown" for match in matches)
    game_modes = Counter(str(match.game_mode) for match in matches)
    lobby_types = Counter(str(match.lobby_type) for match in matches)
    rank_buckets = Counter(rank_bucket(match.avg_rank_tier) for match in matches)
    known_rank_tiers = [match.avg_rank_tier for match in matches if match.avg_rank_tier is not None]
    heroes = {player.hero_id for match in matches for player in match.players}
    radiant_wins = sum(1 for match in matches if match.radiant_win)

    return {
        "processed_matches": len(matches),
        "radiant_win_rate": radiant_wins / len(matches),
        "unique_heroes": len(heroes),
        "patches": dict(sorted(patches.items())),
        "game_modes": dict(sorted(game_modes.items())),
        "lobby_types": dict(sorted(lobby_types.items())),
        "rank_buckets": dict(sorted(rank_buckets.items())),
        "duration_seconds": {
            "min": min(durations),
            "avg": sum(durations) / len(durations),
            "max": max(durations),
        },
        "avg_rank_tier": sum(known_rank_tiers) / len(known_rank_tiers) if known_rank_tiers else None,
    }


def summarize_raw_quality(raw_dir: str, processed_dir: str) -> Dict[str, object]:
    raw_paths = sorted(Path(raw_dir).glob("*.json"))
    processed_ids = {path.stem for path in Path(processed_dir).rglob("*.json")}
    invalid_duration_zero = 0
    raw_without_processed = 0

    for path in raw_paths:
        if path.stem in processed_ids:
            continue

        raw_without_processed += 1
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_data = payload.get("raw_data", {})
        if raw_data.get("duration") == 0:
            invalid_duration_zero += 1

    return {
        "raw_matches": len(raw_paths),
        "raw_without_processed": raw_without_processed,
        "raw_duration_zero": invalid_duration_zero,
    }
