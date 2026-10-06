"""Tests for core.openrouter — pure parsers/builders + the HTTP boundary."""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from stock_video_tool.core import openrouter as orc

CATEGORIES = ["Nature", "People", "Time Lapse", "Slow Motion", "City"]


# --- prompt builders (pure) -----------------------------------------------

def test_describe_messages_include_each_image_as_image_url():
    urls = ["data:image/png;base64,AAA", "data:image/png;base64,BBB"]
    content = orc.build_describe_messages(urls)[0]["content"]
    image_items = [c for c in content if c["type"] == "image_url"]
    assert [c["image_url"]["url"] for c in image_items] == urls


def test_describe_messages_lead_with_a_text_instruction():
    content = orc.build_describe_messages(["data:image/png;base64,AAA"])[0]["content"]
    assert content[0]["type"] == "text"
    assert content[0]["text"]


def test_titles_messages_request_the_configured_count():
    msg = orc.build_titles_messages("a sunset", count=3)[0]["content"]
    assert "3" in msg and "sunset" in msg


def test_tags_messages_request_the_configured_count():
    msg = orc.build_tags_messages("Sunset", "a sunset", count=45)[0]["content"]
    assert "45" in msg


def test_category_messages_list_the_allowed_categories():
    msg = orc.build_category_messages("a sunset", CATEGORIES)[0]["content"]
    assert "Nature" in msg and "Time Lapse" in msg


def test_titles_messages_use_custom_prompt_with_placeholders():
    tmpl = "Give {count} names for: {description}"
    msg = orc.build_titles_messages("a sunset", count=3, prompt=tmpl)[0]["content"]
    assert msg == "Give 3 names for: a sunset"


def test_tags_messages_use_custom_prompt_with_placeholders():
    tmpl = "{count} tags for {title} / {description}"
    msg = orc.build_tags_messages("Sunset", "a sunset", count=45, prompt=tmpl)[0]["content"]
    assert msg == "45 tags for Sunset / a sunset"


def test_describe_messages_use_custom_instruction():
    content = orc.build_describe_messages(
        ["data:image/png;base64,AAA"], prompt="Describe it plainly."
    )[0]["content"]
    assert content[0]["text"] == "Describe it plainly."


def test_custom_prompt_with_stray_braces_does_not_crash():
    msg = orc.build_titles_messages("x", prompt="use {emoji} and {description}")[0]["content"]
    assert "{emoji}" in msg and msg.endswith("and x")


# --- parse_titles ---------------------------------------------------------

def test_parse_titles_reads_a_json_array():
    assert orc.parse_titles('["One", "Two", "Three"]') == ["One", "Two", "Three"]


def test_parse_titles_reads_a_fenced_json_array():
    text = '```json\n["One", "Two"]\n```'
    assert orc.parse_titles(text) == ["One", "Two"]


def test_parse_titles_falls_back_to_numbered_lines():
    text = "1. First title\n2. Second title\n3. Third title"
    assert orc.parse_titles(text) == ["First title", "Second title", "Third title"]


def test_parse_titles_strips_bullets_and_quotes():
    assert orc.parse_titles('- "Nice clip"') == ["Nice clip"]


# --- parse_tags -----------------------------------------------------------

def test_parse_tags_splits_and_trims():
    assert orc.parse_tags("sunset, ocean , waves") == ["sunset", "ocean", "waves"]


def test_parse_tags_removes_duplicates_case_insensitively():
    assert orc.parse_tags("Sun, sun, SUN, sky") == ["Sun", "sky"]


def test_parse_tags_strips_a_code_fence():
    assert orc.parse_tags("```\nsunset, ocean\n```") == ["sunset", "ocean"]


# --- parse_category -------------------------------------------------------

def test_parse_category_exact_match():
    assert orc.parse_category("Nature", CATEGORIES) == "Nature"


def test_parse_category_is_case_insensitive():
    assert orc.parse_category("nature", CATEGORIES) == "Nature"


def test_parse_category_finds_name_inside_a_sentence():
    assert orc.parse_category("The best fit is Time Lapse.", CATEGORIES) == "Time Lapse"


def test_parse_category_raises_on_unknown():
    with pytest.raises(orc.OpenRouterError):
        orc.parse_category("Underwater", CATEGORIES)


# --- encode_image ---------------------------------------------------------

def test_encode_image_produces_a_png_data_url(tmp_path):
    img = tmp_path / "frame.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n fake bytes")
    url = orc.encode_image(img)
    assert url.startswith("data:image/png;base64,")
    payload = url.split(",", 1)[1]
    assert base64.b64decode(payload) == b"\x89PNG\r\n\x1a\n fake bytes"


# --- HTTP boundary (httpx MockTransport, no network) ----------------------

def _client(handler) -> orc.Client:
    transport = httpx.MockTransport(handler)
    return orc.Client("test-key", http=httpx.Client(transport=transport))


def test_chat_returns_text_and_cost():
    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "hello"}}],
            "usage": {"cost": 0.0021},
        })

    result = _client(handler).chat("some/model", [{"role": "user", "content": "hi"}])
    assert result.text == "hello"
    assert result.cost == pytest.approx(0.0021)


def test_chat_sends_bearer_auth_header():
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "x"}}], "usage": {"cost": 0},
        })

    _client(handler).chat("m", [{"role": "user", "content": "hi"}])
    assert captured["auth"] == "Bearer test-key"


def test_chat_raises_on_error_status():
    def handler(request):
        return httpx.Response(401, json={"error": {"message": "no credits"}})

    with pytest.raises(orc.OpenRouterError, match="no credits"):
        _client(handler).chat("m", [{"role": "user", "content": "hi"}])


def test_chat_without_key_raises_before_request():
    client = orc.Client("", http=httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={}))))
    with pytest.raises(orc.OpenRouterError, match="no API key"):
        client.chat("m", [{"role": "user", "content": "hi"}])


def test_list_models_returns_the_data_array():
    def handler(request):
        return httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}]})

    assert _client(handler).list_models() == [{"id": "a"}, {"id": "b"}]


def test_titles_call_parses_json_array_from_response():
    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '["A", "B", "C"]'}}],
            "usage": {"cost": 0.001},
        })

    titles, result = _client(handler).titles("a clip", "some/model")
    assert titles == ["A", "B", "C"]
    assert result.cost == pytest.approx(0.001)


def test_tags_call_parses_comma_list_from_response():
    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "sun, sea, sand"}}],
            "usage": {"cost": 0.0005},
        })

    tags, _ = _client(handler).tags("Beach", "a beach", "some/model")
    assert tags == ["sun", "sea", "sand"]


def test_tags_over_limit_zero_within_limit():
    assert orc.tags_over_limit(45) == 0
    assert orc.tags_over_limit(orc.TAG_LIMIT) == 0


def test_tags_over_limit_counts_excess_above_fifty():
    assert orc.tags_over_limit(53) == 3


def test_is_free_model_by_zero_prompt_price():
    assert orc.is_free_model({"pricing": {"prompt": "0"}}) is True
    assert orc.is_free_model({"pricing": {"prompt": "0.0000012"}}) is False


def test_supports_vision_needs_image_in_and_text_out():
    assert orc.supports_vision({"architecture": {
        "input_modalities": ["text", "image"], "output_modalities": ["text"]}}) is True
    assert orc.supports_vision({"architecture": {
        "input_modalities": ["text"], "output_modalities": ["text"]}}) is False


def test_supports_vision_excludes_image_generators():
    # takes an image but outputs an image -> a generator, not recognition
    assert orc.supports_vision({"architecture": {
        "input_modalities": ["text", "image"],
        "output_modalities": ["image", "text"]}}) is False


def test_supports_text_excludes_generators():
    assert orc.supports_text({"architecture": {"output_modalities": ["text"]}}) is True
    assert orc.supports_text({"architecture": {
        "output_modalities": ["image", "text"]}}) is False
    assert orc.supports_text({"architecture": {
        "output_modalities": ["audio", "text"]}}) is False


_MODELS = [
    {"id": "free-text", "pricing": {"prompt": "0"},
     "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]}},
    {"id": "free-vision", "pricing": {"prompt": "0"},
     "architecture": {"input_modalities": ["text", "image"],
                      "output_modalities": ["text"]}},
    {"id": "paid-vision", "pricing": {"prompt": "0.001"},
     "architecture": {"input_modalities": ["text", "image"],
                      "output_modalities": ["text"]}},
    {"id": "image-gen", "pricing": {"prompt": "0.002"},
     "architecture": {"input_modalities": ["text", "image"],
                      "output_modalities": ["image", "text"]}},
]


def test_filter_models_free_only():
    ids = [m["id"] for m in orc.filter_models(_MODELS, which="free")]
    assert ids == ["free-text", "free-vision"]


def test_filter_models_paid_only():
    ids = [m["id"] for m in orc.filter_models(_MODELS, which="paid")]
    assert ids == ["paid-vision", "image-gen"]


def test_filter_models_vision_keeps_both_prices_excludes_generators():
    ids = [m["id"] for m in orc.filter_models(_MODELS, capability="vision")]
    assert ids == ["free-vision", "paid-vision"]


def test_filter_models_text_excludes_image_generators():
    ids = [m["id"] for m in orc.filter_models(_MODELS, capability="text")]
    assert ids == ["free-text", "free-vision", "paid-vision"]


def test_categorize_call_matches_allowed_category():
    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "Nature"}}],
            "usage": {"cost": 0.0002},
        })

    category, _ = _client(handler).categorize("a forest", CATEGORIES, "some/model")
    assert category == "Nature"
