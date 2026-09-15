import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- network ---
    OPENDOTA_BASE_URL: str = "https://api.opendota.com/api"
    OPENDOTA_TIMEOUT_SECONDS: float = 30.0
    OPENDOTA_MAX_RETRIES: int = 6
    OPENDOTA_RETRY_BACKOFF_SECONDS: float = 5.0
    OPENDOTA_API_KEY: Optional[str] = None
    OPENDOTA_DAILY_REQUEST_BUDGET: int = 30000

    # --- quality gates ---
    MIN_MATCH_DURATION_SECONDS: int = 1200   # 20 min
    REQUIRED_LOBBY_TYPE: int = 7             # ranked
    REQUIRED_GAME_MODE: int = 22             # all pick
    MIN_MATCH_AVG_RANK_TIER: int = 0

    # --- paths ---
    RAW_DATA_DIR: str = os.path.join("data", "raw")
    RANKED_PROCESSED_DATA_DIR: str = os.path.join("data", "processed", "ranked")
    UNRANKED_PROCESSED_DATA_DIR: str = os.path.join("data", "processed", "unranked")
    FILTERED_PROCESSED_DATA_DIR: str = os.path.join("data", "processed", "filtered")
    COLLECTOR_STATE_PATH: str = os.path.join("data", "collector_state.json")
    MODEL_DIR: str = "models"

    class Config:
        env_file = ".env"


settings = Settings()

# create dirs once
for _path in (
    settings.RAW_DATA_DIR,
    settings.RANKED_PROCESSED_DATA_DIR,
    settings.UNRANKED_PROCESSED_DATA_DIR,
    settings.FILTERED_PROCESSED_DATA_DIR,
    settings.MODEL_DIR,
):
    os.makedirs(_path, exist_ok=True)
