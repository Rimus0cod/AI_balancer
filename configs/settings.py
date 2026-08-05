import os
from typing import Optional

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    OPENDOTA_BASE_URL: str = "https://api.opendota.com/api"
    OPENDOTA_TIMEOUT_SECONDS: float = 30.0
    OPENDOTA_MAX_RETRIES: int = 3
    OPENDOTA_RETRY_BACKOFF_SECONDS: float = 5.0
    OPENDOTA_API_KEY: Optional[str] = None
    OPENDOTA_DAILY_REQUEST_BUDGET: int = 30000
    # Phase 1 quality gates. 0 disables the corresponding mandatory check.
    MIN_MATCH_DURATION_SECONDS: int = 1200  # 20 minutes: cuts Turbo, aborted and broken matches
    REQUIRED_LOBBY_TYPE: int = 7  # 7 = ranked
    REQUIRED_GAME_MODE: int = 22  # 22 = All Pick (classic ranked mode)
    MIN_MATCH_AVG_RANK_TIER: int = 0  # e.g. 70 to keep Ancient+ games only

    RAW_DATA_DIR: str = os.path.join("data", "raw")
    RANKED_PROCESSED_DATA_DIR: str = os.path.join("data", "processed", "ranked")
    UNRANKED_PROCESSED_DATA_DIR: str = os.path.join("data", "processed", "unranked")
    FILTERED_PROCESSED_DATA_DIR: str = os.path.join("data", "processed", "filtered")
    COLLECTOR_STATE_PATH: str = os.path.join("data", "collector_state.json")
    MODEL_DIR: str = "models"

    class Config:
        env_file = ".env"

settings = Settings()

# Ensure directories exist
os.makedirs(settings.RAW_DATA_DIR, exist_ok=True)
os.makedirs(settings.RANKED_PROCESSED_DATA_DIR, exist_ok=True)
os.makedirs(settings.UNRANKED_PROCESSED_DATA_DIR, exist_ok=True)
os.makedirs(settings.FILTERED_PROCESSED_DATA_DIR, exist_ok=True)
os.makedirs(settings.MODEL_DIR, exist_ok=True)
