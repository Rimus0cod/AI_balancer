from typing import List, Optional
from pydantic import BaseModel, Field

# Field values copied here for documentation/validation of known OpenDota codes.
# See https://docs.opendota.com/ for the canonical tables.
LOBBY_TYPE_RANKED = 7
GAME_MODE_ALL_PICK = 22

class ProvenanceMetadata(BaseModel):
    source: str
    endpoint: str
    match_id: int
    collection_timestamp: float
    status_code: int
    schema_version: str = "1.0.0"

class Player(BaseModel):
    account_id: Optional[int] = Field(default=None, description="Null for anonymous players")
    player_slot: int
    hero_id: int
    team: int = Field(description="0 for Radiant, 1 for Dire")
    kills: int
    deaths: int
    assists: int
    net_worth: Optional[int] = None
    gpm: Optional[int] = None
    xpm: Optional[int] = None

    # Missing/Delayed fields marked as optional for Phase 1
    role: Optional[int] = None
    lane: Optional[int] = None

class Match(BaseModel):
    match_id: int
    start_time: int
    duration: int = Field(gt=0, description="Match duration in seconds")
    radiant_win: bool
    game_mode: int
    lobby_type: int
    patch: Optional[int] = Field(default=None, description="Patch ID, if available from source")
    region: Optional[int] = None
    avg_rank_tier: Optional[int] = Field(default=None, description="Average rank tier; null if unknown")
    players: List[Player] = Field(min_length=10, max_length=10)