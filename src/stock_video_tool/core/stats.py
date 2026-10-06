"""Persistent usage stats: average cost and response time per model + query type.

Recorded every time an OpenRouter query returns, so you can compare the value
and speed of different models/services over time, even across sessions.
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import APP_SUPPORT_DIR

STATS_PATH = APP_SUPPORT_DIR / "stats.json"

# Query types tracked separately, since they vary in size and cost.
QUERY_TYPES = ("description", "titles", "tags", "category")


def _key(model: str, query_type: str) -> str:
    return f"{model}|{query_type}"


class Stats:
    def __init__(self, path: Path | str = STATS_PATH) -> None:
        self.path = Path(path)
        self._data: dict[str, dict] = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except json.JSONDecodeError:
                self._data = {}

    def _entry(self, model: str, query_type: str) -> dict:
        return self._data.setdefault(
            _key(model, query_type),
            {"count": 0, "total_cost": 0.0, "total_time": 0.0, "good": 0, "bad": 0},
        )

    def record(self, model: str, query_type: str, cost: float, seconds: float) -> None:
        entry = self._entry(model, query_type)
        entry["count"] += 1
        entry["total_cost"] += cost
        entry["total_time"] += seconds
        self.save()

    def record_rating(self, model: str, query_type: str, good: bool) -> None:
        entry = self._entry(model, query_type)
        entry["good" if good else "bad"] = entry.get("good" if good else "bad", 0) + 1
        self.save()

    def summary(self, model: str, query_type: str) -> dict | None:
        entry = self._data.get(_key(model, query_type))
        if not entry or (entry["count"] == 0 and not entry.get("good")
                         and not entry.get("bad")):
            return None
        return _summarize(model, query_type, entry)

    def all_summaries(self) -> list[dict]:
        out = []
        for key, entry in self._data.items():
            if entry["count"] == 0 and not entry.get("good") and not entry.get("bad"):
                continue
            model, query_type = key.rsplit("|", 1)
            out.append(_summarize(model, query_type, entry))
        out.sort(key=lambda s: (s["model"], s["query_type"]))
        return out

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))


def _summarize(model: str, query_type: str, entry: dict) -> dict:
    count = entry["count"]
    return {
        "model": model,
        "query_type": query_type,
        "count": count,
        "avg_cost": entry["total_cost"] / count if count else 0.0,
        "avg_time": entry["total_time"] / count if count else 0.0,
        "good": entry.get("good", 0),
        "bad": entry.get("bad", 0),
    }
