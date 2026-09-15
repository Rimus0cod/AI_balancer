from typing import List, Optional
from pydantic import BaseModel, Field

LOBBY_TYPE_RANKED = 7
GAME_MODE_ALL_PICK = 22


class ProvenanceMetadata(BaseModel):
    source: str
    endpoint: str
    match_id: int
    collection_timestamp: float
    status_code: int
    schema_version: str = "1.1.0"


class Purchase(BaseModel):
    time: int = Field(description="Seconds from match start; negative values mean pre-game purchases")
    item_name: str = Field(description="OpenDota item key, e.g. black_king_bar")


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
    early_gpm: Optional[float] = Field(
        default=None,
        description="Gold earned per minute by minute 10, from gold_t[10]; pre-purchase farm context",
    )

    # Missing/Delayed fields marked as optional for Phase 1
    role: Optional[int] = None
    lane: Optional[int] = None
    purchases: List[Purchase] = Field(default_factory=list)


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

