"""Tests for core.config model-list caching."""

from __future__ import annotations

import pytest

from stock_video_tool.core import config

_FULL_MODEL = {
    "id": "x/y",
    "name": "fancy",
    "pricing": {"prompt": "0", "completion": "0"},
    "architecture": {
        "input_modalities": ["text", "image"],
        "output_modalities": ["text"],
        "extra": "drop me",
    },
    "description": "long text we do not need",
}


def test_slim_models_keeps_only_needed_fields():
    slim = config.slim_models([_FULL_MODEL])
    assert slim == [{
        "id": "x/y",
        "pricing": {"prompt": "0"},
        "architecture": {
            "input_modalities": ["text", "image"],
            "output_modalities": ["text"],
        },
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


# ---- marketplace setting -------------------------------------------------

def test_settings_default_marketplace_is_envato():
    assert config.Settings().marketplace == "Envato"


def test_marketplace_round_trips_through_save_and_load(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(config, "APP_SUPPORT_DIR", tmp_path)
    monkeypatch.setattr(config, "SETTINGS_PATH", path)
    settings = config.Settings()
    settings.marketplace = "Shutterstock"
    settings.save()
    assert config.Settings.load().marketplace == "Shutterstock"


def test_settings_default_excluded_keywords_is_empty():
    assert config.Settings().excluded_keywords == []


def test_excluded_keywords_round_trip_through_save_and_load(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(config, "APP_SUPPORT_DIR", tmp_path)
    monkeypatch.setattr(config, "SETTINGS_PATH", path)
    settings = config.Settings()
    settings.excluded_keywords = ["4K", "UHD", "Stock Footage"]
    settings.save()
    assert config.Settings.load().excluded_keywords == ["4K", "UHD", "Stock Footage"]


# ---- resolve_section (scaffold — implement during refactor) --------------

@pytest.mark.skip(reason="scaffold — implement during refactor")
def test_resolve_section_errors_when_model_missing():
    """Empty model -> error mentioning the section, no model/key."""
    raise NotImplementedError


@pytest.mark.skip(reason="scaffold — implement during refactor")
def test_resolve_section_errors_when_key_missing():
    """Model set but chosen key blank -> error naming the key choice."""
    raise NotImplementedError


@pytest.mark.skip(reason="scaffold — implement during refactor")
def test_resolve_section_returns_model_and_key_when_valid():
    raise NotImplementedError
