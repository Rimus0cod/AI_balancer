import json
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


RANK_BUCKETS: Dict[str, Tuple[int, int]] = {
    "herald": (10, 20),
    "guardian": (20, 30),
    "crusader": (30, 40),
    "archon": (40, 50),
    "legend": (50, 60),
    "ancient": (60, 70),
    "divine": (70, 80),
    "immortal": (80, 100),
}

DEFAULT_COLLECTION_ORDER = [
    "archon",
    "legend",
    "crusader",
    "ancient",
    "guardian",
    "herald",
    "divine",
    "immortal",
]


class CollectorState:
    def __init__(self, path: str):
        self.path = Path(path)
        self.data = self._load()
        self._ensure_today()

    def _load(self) -> Dict[str, object]:
        if not self.path.exists():
            return {
                "schema_version": 1,
                "daily": {"date": str(date.today()), "requests": 0},
                "buckets": {},
            }
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8")

    def _ensure_today(self) -> None:
        today = str(date.today())
        daily = self.data.setdefault("daily", {})
        if daily.get("date") != today:
            daily["date"] = today
            daily["requests"] = 0

    def requests_today(self) -> int:
        self._ensure_today()
        return int(self.data["daily"].get("requests", 0))

    def increment_requests(self, count: int = 1) -> None:
        self._ensure_today()
        self.data["daily"]["requests"] = self.requests_today() + count

    def remaining_requests(self, daily_budget: int) -> int:
        return max(0, daily_budget - self.requests_today())

    def budget_exhausted(self, daily_budget: int) -> bool:
        return self.requests_today() >= daily_budget

    def bucket(self, name: str) -> Dict[str, object]:
        buckets = self.data.setdefault("buckets", {})
        bucket = buckets.setdefault(
            name,
            {
                "ids": [],
                "frontier_match_id": None,
                "exhausted": False,
            },
        )
        bucket.setdefault("ids", [])
        bucket.setdefault("frontier_match_id", None)
        bucket.setdefault("exhausted", False)
        return bucket

    def ids(self, bucket_name: str) -> set[int]:
        return {int(match_id) for match_id in self.bucket(bucket_name).get("ids", [])}

    def count(self, bucket_name: str) -> int:
        bucket = self.bucket(bucket_name)
        explicit = bucket.get("count")
        if explicit is not None:
            return int(explicit)
        return len(bucket.get("ids", []))

    def record_match(self, bucket_name: str, match_id: int) -> None:
        bucket = self.bucket(bucket_name)
        ids = bucket.setdefault("ids", [])
        if match_id not in ids:
            ids.append(match_id)

    def frontier(self, bucket_name: str) -> Optional[int]:
        frontier = self.bucket(bucket_name).get("frontier_match_id")
        return int(frontier) if frontier is not None else None

    def set_frontier(self, bucket_name: str, match_id: Optional[int]) -> None:
        self.bucket(bucket_name)["frontier_match_id"] = match_id

    def exhausted(self, bucket_name: str) -> bool:
        return bool(self.bucket(bucket_name).get("exhausted", False))

    def set_exhausted(self, bucket_name: str, exhausted: bool = True) -> None:
        self.bucket(bucket_name)["exhausted"] = exhausted

    def summary(self, bucket_names: Iterable[str], target_per_bucket: int, daily_budget: int) -> List[str]:
        lines = [
            f"Requests today: {self.requests_today()}/{daily_budget} "
            f"(remaining={self.remaining_requests(daily_budget)})"
        ]
        for bucket_name in bucket_names:
            current = self.count(bucket_name)
            remaining = max(0, target_per_bucket - current)
            exhausted = " exhausted" if self.exhausted(bucket_name) else ""
            lines.append(f"{bucket_name}: {current}/{target_per_bucket} remaining={remaining}{exhausted}")
        return lines


def parse_bucket_order(value: str) -> List[str]:
    if value == "all":
        return list(DEFAULT_COLLECTION_ORDER)
    buckets = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [bucket for bucket in buckets if bucket not in RANK_BUCKETS]
    if unknown:
        raise ValueError(f"Unknown rank buckets: {', '.join(unknown)}")
    return buckets
