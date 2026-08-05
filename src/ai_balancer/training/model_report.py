import json
from pathlib import Path
from typing import Dict, List, Tuple


def load_model(model_path: str) -> Dict[str, object]:
    return json.loads(Path(model_path).read_text(encoding="utf-8"))


def top_weights(weights: Dict[str, float], limit: int = 10) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]]]:
    sorted_weights = sorted(weights.items(), key=lambda item: item[1], reverse=True)
    return sorted_weights[:limit], sorted_weights[-limit:]
