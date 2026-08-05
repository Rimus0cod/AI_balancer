import json
import os
from src.ai_balancer.schemas.match import ProvenanceMetadata, Match
from configs.settings import settings

class LocalStorage:
    @staticmethod
    def save_raw(match_id: int, raw_data: dict, provenance: ProvenanceMetadata):
        """Stores raw API payload alongside its provenance metadata."""
        filepath = os.path.join(settings.RAW_DATA_DIR, f"{match_id}.json")
        payload = {
            "_provenance": provenance.model_dump(),
            "raw_data": raw_data
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        return filepath

    @staticmethod
    def save_processed(match_id: int, match_data: Match):
        """Default sink for backward compatibility; prefer save_processed_to(category...)."""
        filepath = os.path.join(settings.RANKED_PROCESSED_DATA_DIR, f"{match_id}.json")
        return LocalStorage.save_processed_to(filepath, match_data)

    @staticmethod
    def save_processed_ranked(match_id: int, match_data: Match):
        return LocalStorage.save_processed_to(
            os.path.join(settings.RANKED_PROCESSED_DATA_DIR, f"{match_id}.json"), match_data
        )

    @staticmethod
    def save_processed_unranked(match_id: int, match_data: Match):
        return LocalStorage.save_processed_to(
            os.path.join(settings.UNRANKED_PROCESSED_DATA_DIR, f"{match_id}.json"), match_data
        )

    @staticmethod
    def save_processed_filtered(match_id: int, match_data: Match):
        return LocalStorage.save_processed_to(
            os.path.join(settings.FILTERED_PROCESSED_DATA_DIR, f"{match_id}.json"), match_data
        )

    @staticmethod
    def save_processed_to(filepath: str, match_data: Match):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(match_data.model_dump_json(indent=2))
        return filepath
