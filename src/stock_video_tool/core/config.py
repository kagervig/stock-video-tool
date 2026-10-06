"""Load and save persisted settings.

Keys are managed centrally: one free key and one paid key. Each prompt section
chooses a model and which of the two keys to send it with, so it is always
clear which key a given request uses.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")


def _build(cls: type[T], data: dict[str, Any]) -> T:
    """Construct a dataclass, ignoring unknown keys from older settings files."""
    allowed = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in allowed})

APP_SUPPORT_DIR = (
    Path.home() / "Library" / "Application Support" / "StockVideoTool"
)
SETTINGS_PATH = APP_SUPPORT_DIR / "settings.json"
MODELS_CACHE_PATH = APP_SUPPORT_DIR / "models_cache.json"

KEY_FREE = "free"
KEY_PAID = "paid"


@dataclass
class Keys:
    """The two OpenRouter keys the user pastes in once."""

    free: str = ""
    paid: str = ""

    def get(self, choice: str) -> str:
        return self.paid if choice == KEY_PAID else self.free


@dataclass
class SectionConfig:
    """Per-prompt-stage model choice and which key to use for it."""

    model: str = ""
    model_filter: str = "free"  # free | paid | all (dropdown filter only)
    key_choice: str = KEY_FREE  # free | paid
    prompt: str = ""  # custom prompt template; empty = built-in default


@dataclass
class Settings:
    keys: Keys = field(default_factory=Keys)
    description: SectionConfig = field(default_factory=SectionConfig)
    titles: SectionConfig = field(default_factory=SectionConfig)
    tags: SectionConfig = field(default_factory=SectionConfig)
    export_path: str = str(Path.home() / "Desktop")

    @classmethod
    def load(cls) -> "Settings":
        if not SETTINGS_PATH.exists():
            return cls()
        data = json.loads(SETTINGS_PATH.read_text())
        return cls(
            keys=_build(Keys, data.get("keys", {})),
            description=_build(SectionConfig, data.get("description", {})),
            titles=_build(SectionConfig, data.get("titles", {})),
            tags=_build(SectionConfig, data.get("tags", {})),
            export_path=data.get("export_path", str(Path.home() / "Desktop")),
        )

    def save(self) -> None:
        APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(asdict(self), indent=2))


def slim_models(models: list[dict]) -> list[dict]:
    """Keep only the fields the dropdowns and filters need, to cache compactly."""
    slim = []
    for model in models:
        if not model.get("id"):
            continue
        architecture = model.get("architecture") or {}
        slim.append({
            "id": model["id"],
            "pricing": {"prompt": (model.get("pricing") or {}).get("prompt")},
            "architecture": {
                "input_modalities": architecture.get("input_modalities") or [],
                "output_modalities": architecture.get("output_modalities") or [],
            },
        })
    return slim


def load_cached_models(path: Path = MODELS_CACHE_PATH) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return []


def save_cached_models(models: list[dict], path: Path = MODELS_CACHE_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(slim_models(models)))
