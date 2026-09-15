import json
from pathlib import Path
from typing import Dict

from configs.settings import settings
from src.ai_balancer.ingestion.opendota import OpenDotaClient

CONSTANTS_DIR = Path("data") / "constants"
CONSTANTS_DIR.mkdir(parents=True, exist_ok=True)


def fetch_constant(name: str, ttl_hours: int = 168) -> dict:
    """Fetch and cache an OpenDota constant endpoint (e.g. heroes, items)."""
    path = CONSTANTS_DIR / f"{name}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    client = OpenDotaClient()
    url = f"{settings.OPENDOTA_BASE_URL}/constants/{name}"
    data, _ = client._get_json(url)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return data


def hero_display_names() -> Dict[int, str]:
    raw = fetch_constant("heroes")
    out: Dict[int, str] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        hero_id = value.get("id", key)
        display = (
            value.get("localized_name")
            or value.get("dname")
            or value.get("displayName")
            or value.get("name")
            or str(key)
        )
        try:
            out[int(hero_id)] = str(display)
        except (TypeError, ValueError):
            continue
    return out


def item_display_names() -> Dict[str, str]:
    raw = fetch_constant("items")
    out: Dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        display = value.get("dname") or value.get("displayName") or str(key)
        out[str(key)] = str(display)
    return out
