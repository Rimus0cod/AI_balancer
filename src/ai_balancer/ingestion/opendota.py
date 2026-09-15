import time
import requests
from typing import Tuple, Dict, Any, List
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse, quote

from configs.settings import settings
from src.ai_balancer.schemas.match import ProvenanceMetadata

class OpenDotaClient:
    def __init__(self):
        self.base_url = settings.OPENDOTA_BASE_URL

    def _with_api_key(self, url: str) -> str:
        if not settings.OPENDOTA_API_KEY:
            return url

        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query))
        query.setdefault("api_key", settings.OPENDOTA_API_KEY)
        return urlunparse(parsed._replace(query=urlencode(query)))

    def _get_json(self, url: str):
        url = self._with_api_key(url)
        last_exc = None

        for attempt in range(settings.OPENDOTA_MAX_RETRIES + 1):
            try:
                response = requests.get(url, timeout=settings.OPENDOTA_TIMEOUT_SECONDS)
            except requests.RequestException as exc:
                # Timeouts, connection resets, DNS blips, etc.
                last_exc = exc
                if attempt == settings.OPENDOTA_MAX_RETRIES:
                    raise
                delay = settings.OPENDOTA_RETRY_BACKOFF_SECONDS * (attempt + 1)
                time.sleep(delay)
                continue

            # 429 = rate limit; 5xx = OpenDota/Cloudflare server errors — both retryable.
            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt == settings.OPENDOTA_MAX_RETRIES:
                    response.raise_for_status()
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    delay = float(retry_after)
                else:
                    delay = settings.OPENDOTA_RETRY_BACKOFF_SECONDS * (attempt + 1)
                time.sleep(delay)
                continue

            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                body = response.text[:4000] if response.text else ""
                raise requests.HTTPError(
                    f"{response.status_code} {response.reason} for url: {response.url} | body: {body}",
                    response=response,
                ) from exc
            return response.json(), response.status_code

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("OpenDota request failed after retries")

    def fetch_match(self, match_id: int) -> Tuple[Dict[str, Any], ProvenanceMetadata]:
        endpoint = f"/matches/{match_id}"
        url = f"{self.base_url}{endpoint}"

        raw_data, status_code = self._get_json(url)

        provenance = ProvenanceMetadata(
            source="OpenDota",
            endpoint=url,
            match_id=match_id,
            collection_timestamp=time.time(),
            status_code=status_code
        )

        return raw_data, provenance

    def fetch_public_matches(self, max_limit: int = 2000, min_rank_tier: int = 0) -> List[Dict[str, Any]]:
        """Returns recent public matches with listing metadata (rank tier, mode, duration)."""
        return self.fetch_public_matches_page(
            min_rank_tier=min_rank_tier,
            max_rank_tier=100,
            before_match_id=None,
            limit=max_limit,
        )

    def fetch_public_matches_page(
        self,
        min_rank_tier: int,
        max_rank_tier: int,
        before_match_id: int | None,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Returns one descending page of ranked public matches from OpenDota Explorer."""

        sql = (
            "SELECT match_id, start_time, duration, radiant_win, avg_rank_tier, "
            "game_mode, lobby_type FROM public_matches"
        )
        clauses = [
            f"lobby_type = {int(settings.REQUIRED_LOBBY_TYPE)}",
            f"game_mode = {int(settings.REQUIRED_GAME_MODE)}",
            f"duration >= {int(settings.MIN_MATCH_DURATION_SECONDS)}",
            "avg_rank_tier IS NOT NULL",
            f"avg_rank_tier >= {int(min_rank_tier)}",
            f"avg_rank_tier < {int(max_rank_tier)}",
        ]
        if before_match_id is not None:
            clauses.append(f"match_id < {int(before_match_id)}")
        sql += " WHERE " + " AND ".join(clauses)
        sql += f" ORDER BY match_id DESC LIMIT {int(limit)}"

        endpoint = f"/explorer?sql={quote(sql)}"
        url = f"{self.base_url}{endpoint}"
        data, _ = self._get_json(url)
        return data.get("rows", [])

    def fetch_draft_page(
        self,
        min_rank_tier: int,
        max_rank_tier: int,
        before_match_id: int | None,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Bulk draft rows: one explorer request returns up to `limit` player rows
        (limit/10 matches) with heroes, side and result. No purchase logs here."""
        sql = (
            "SELECT pm.match_id, pm.start_time, pm.duration, pm.radiant_win, "
            "pm.avg_rank_tier, ppm.hero_id, ppm.player_slot "
            "FROM public_matches pm "
            "JOIN public_player_matches ppm ON pm.match_id = ppm.match_id"
        )
        clauses = [
            f"pm.lobby_type = {int(settings.REQUIRED_LOBBY_TYPE)}",
            f"pm.game_mode = {int(settings.REQUIRED_GAME_MODE)}",
            f"pm.duration >= {int(settings.MIN_MATCH_DURATION_SECONDS)}",
            "pm.avg_rank_tier IS NOT NULL",
            f"pm.avg_rank_tier >= {int(min_rank_tier)}",
            f"pm.avg_rank_tier < {int(max_rank_tier)}",
        ]
        if before_match_id is not None:
            clauses.append(f"pm.match_id < {int(before_match_id)}")
        sql += " WHERE " + " AND ".join(clauses)
        sql += f" ORDER BY pm.match_id DESC LIMIT {int(limit)}"

        endpoint = f"/explorer?sql={quote(sql)}"
        url = f"{self.base_url}{endpoint}"
        data, _ = self._get_json(url)
        return data.get("rows", [])

    def fetch_heroes_for_matches(self, match_ids: List[int]) -> List[Dict[str, Any]]:
        """Fetch hero_id/player_slot for a chunk of match_ids via public_player_matches.
        Used as fallback when JOIN is rejected by Explorer (400)."""
        if not match_ids:
            return []
        ids_str = ",".join(str(int(mid)) for mid in match_ids)
        sql = f"SELECT match_id, hero_id, player_slot FROM public_player_matches WHERE match_id IN ({ids_str})"
        endpoint = f"/explorer?sql={quote(sql)}"
        url = f"{self.base_url}{endpoint}"
        data, _ = self._get_json(url)
        return data.get("rows", [])


RANK_BRACKETS = [
    (80, "immortal"),
    (70, "divine"),
    (60, "ancient"),
    (50, "legend"),
    (40, "archon"),
    (30, "crusader"),
    (20, "guardian"),
    (10, "herald"),
]


def rank_bucket(avg_rank_tier) -> str:
    """Maps avg_rank_tier (11..84) to a readable rank bracket; 'unknown' if missing."""
    if not isinstance(avg_rank_tier, (int, float)) or avg_rank_tier <= 0:
        return "unknown"
    tier = int(avg_rank_tier)
    for threshold, name in RANK_BRACKETS:
        if tier >= threshold:
            return name
    return "unknown"


def looks_like_ranked(match: Dict[str, Any]) -> bool:
    """Detail-level check: ranked lobby, classic all-pick mode, reasonable duration."""
    return (
        match.get("lobby_type") == settings.REQUIRED_LOBBY_TYPE
        and match.get("game_mode") == settings.REQUIRED_GAME_MODE
        and (match.get("duration") or 0) >= settings.MIN_MATCH_DURATION_SECONDS
    )
