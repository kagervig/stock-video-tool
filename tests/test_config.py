"""Tests for core.config model-list caching."""

from __future__ import annotations

from stock_video_tool.core import config

_FULL_MODEL = {
    "id": "x/y",
    "name": "fancy",
    "pricing": {"prompt": "0", "completion": "0"},
    "architecture": {"input_modalities": ["text", "image"], "extra": "drop me"},
    "description": "long text we do not need",
}


def test_slim_models_keeps_only_needed_fields():
    slim = config.slim_models([_FULL_MODEL])
    assert slim == [{
        "id": "x/y",
        "pricing": {"prompt": "0"},
        "architecture": {"input_modalities": ["text", "image"]},
    }]


def test_slim_models_skips_entries_without_id():
    assert config.slim_models([{"name": "no id"}]) == []


def test_cache_round_trips(tmp_path):
    path = tmp_path / "models_cache.json"
    config.save_cached_models([_FULL_MODEL], path=path)
    loaded = config.load_cached_models(path=path)
    assert loaded[0]["id"] == "x/y"


def test_load_cached_models_returns_empty_when_missing(tmp_path):
    assert config.load_cached_models(path=tmp_path / "nope.json") == []
