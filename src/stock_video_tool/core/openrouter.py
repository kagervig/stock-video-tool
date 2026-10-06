"""OpenRouter client: model listing + describe / titles / tags / category calls.

Prompt builders and response parsers are pure functions so they can be tested
without the network. The HTTP boundary lives in `Client`, which accepts an
injected httpx client for testing.
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path

import httpx

BASE_URL = "https://openrouter.ai/api/v1"
APP_TITLE = "Stock Video Tool"

TITLE_COUNT = 3
TAG_COUNT = 45    # soft target: how many keywords we ask the model for
TAG_LIMIT = 50    # hard maximum the stock platform allows

_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class OpenRouterError(RuntimeError):
    """Raised on auth, HTTP, or response-shape problems."""


@dataclass
class ChatResult:
    text: str
    cost: float
    model: str


# --- encoding + prompt builders (pure) ------------------------------------

def encode_image(path: Path) -> str:
    """Read an image file into a base64 data URL."""
    mime = _MIME_BY_SUFFIX.get(path.suffix.lower(), "image/png")
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


# Default prompt templates. Each is editable in Settings; the {placeholders}
# are filled in at call time. An empty/omitted custom prompt falls back to these.
DEFAULT_DESCRIBE_PROMPT = (
    "These are four frames sampled across a short stock video clip. "
    "Write a concise, factual description (1-3 sentences) of the subject, "
    "setting, action, and mood, suitable for a stock footage listing. "
    "Describe only what is visible. Do not mention that these are frames."
)
DEFAULT_TITLES_PROMPT = (
    "Based on this stock video description, generate exactly {count} distinct, "
    "marketable titles for the clip. Return only a JSON array of {count} "
    "strings, nothing else.\n\nDescription: {description}"
)
DEFAULT_TAGS_PROMPT = (
    "Generate exactly {count} keywords to help sell this clip on Envato stock "
    "video. Return only the keywords as a single comma-separated line, no "
    "numbering, no quotes.\n\nTitle: {title}\nDescription: {description}"
)


def _fill(template: str, **values: object) -> str:
    """Substitute {name} placeholders, leaving any stray braces untouched."""
    text = template
    for name, value in values.items():
        text = text.replace("{" + name + "}", str(value))
    return text


def build_describe_messages(
    image_data_urls: list[str], prompt: str | None = None
) -> list[dict]:
    instruction = prompt or DEFAULT_DESCRIBE_PROMPT
    content: list[dict] = [{"type": "text", "text": instruction}]
    for url in image_data_urls:
        content.append({"type": "image_url", "image_url": {"url": url}})
    return [{"role": "user", "content": content}]


def build_titles_messages(
    description: str, count: int = TITLE_COUNT, prompt: str | None = None
) -> list[dict]:
    text = _fill(prompt or DEFAULT_TITLES_PROMPT, count=count, description=description)
    return [{"role": "user", "content": text}]


def build_tags_messages(
    title: str, description: str, count: int = TAG_COUNT, prompt: str | None = None
) -> list[dict]:
    text = _fill(
        prompt or DEFAULT_TAGS_PROMPT,
        count=count, title=title, description=description,
    )
    return [{"role": "user", "content": text}]


def build_category_messages(description: str, categories: list[str]) -> list[dict]:
    prompt = (
        "Choose the single best category for this stock video from the list "
        "below. Return only the category name exactly as written, nothing "
        f"else.\n\nCategories: {', '.join(categories)}\n\nDescription: {description}"
    )
    return [{"role": "user", "content": prompt}]


# --- response parsers (pure) ----------------------------------------------

def parse_titles(text: str) -> list[str]:
    """Parse a JSON array, or fall back to numbered/bulleted lines."""
    text = text.strip()
    try:
        data = json.loads(_strip_code_fence(text))
        if isinstance(data, list):
            return [str(t).strip() for t in data if str(t).strip()]
    except json.JSONDecodeError:
        pass

    titles = []
    for line in text.splitlines():
        cleaned = re.sub(r'^\s*(?:\d+[.)]|[-*•])\s*', "", line).strip().strip('"')
        if cleaned:
            titles.append(cleaned)
    return titles


def parse_tags(text: str) -> list[str]:
    """Split a comma-separated line into trimmed, de-duplicated keywords."""
    seen: set[str] = set()
    tags: list[str] = []
    for raw in _strip_code_fence(text.strip()).split(","):
        tag = raw.strip().strip('"').strip()
        key = tag.lower()
        if tag and key not in seen:
            seen.add(key)
            tags.append(tag)
    return tags


def tags_over_limit(count: int) -> int:
    """How many keywords exceed the hard limit (0 if within it)."""
    return max(0, count - TAG_LIMIT)


def parse_category(text: str, categories: list[str]) -> str:
    """Match the model's answer to one of the allowed categories."""
    answer = text.strip().strip('".').lower()
    by_lower = {c.lower(): c for c in categories}
    if answer in by_lower:
        return by_lower[answer]
    # Model may wrap the name in a sentence; find the first category mentioned.
    for lower, original in by_lower.items():
        if re.search(rf"\b{re.escape(lower)}\b", answer):
            return original
    raise OpenRouterError(f"model returned an unknown category: {text!r}")


def _strip_code_fence(text: str) -> str:
    """Remove a surrounding ```json ... ``` fence if present."""
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return match.group(1) if match else text


# --- model-list filtering (pure) ------------------------------------------

def is_free_model(model: dict) -> bool:
    return str((model.get("pricing") or {}).get("prompt", "")) in ("0", "0.0")


def supports_vision(model: dict) -> bool:
    modalities = (model.get("architecture") or {}).get("input_modalities") or []
    return "image" in modalities


def filter_models(
    models: list[dict], which: str = "all", vision_only: bool = False
) -> list[dict]:
    """Filter by free/paid/all and, optionally, vision capability."""
    out = []
    for model in models:
        if vision_only and not supports_vision(model):
            continue
        if which == "free" and not is_free_model(model):
            continue
        if which == "paid" and is_free_model(model):
            continue
        out.append(model)
    return out


# --- HTTP boundary --------------------------------------------------------

class Client:
    def __init__(
        self, api_key: str, http: httpx.Client | None = None,
        base_url: str = BASE_URL,
    ) -> None:
        self._key = api_key
        self._base = base_url
        self._http = http or httpx.Client(timeout=120)

    def _headers(self) -> dict[str, str]:
        if not self._key:
            raise OpenRouterError("no API key set for this request")
        return {
            "Authorization": f"Bearer {self._key}",
            "X-Title": APP_TITLE,
        }

    def list_models(self) -> list[dict]:
        try:
            resp = self._http.get(f"{self._base}/models")
        except httpx.RequestError as exc:
            raise OpenRouterError(f"could not reach OpenRouter: {exc}") from exc
        if resp.status_code != 200:
            raise OpenRouterError(f"model list failed ({resp.status_code})")
        return resp.json().get("data", [])

    def chat(self, model: str, messages: list[dict]) -> ChatResult:
        body = {"model": model, "messages": messages}
        try:
            resp = self._http.post(
                f"{self._base}/chat/completions",
                headers=self._headers(),
                json=body,
            )
        except httpx.RequestError as exc:
            raise OpenRouterError(f"could not reach OpenRouter: {exc}") from exc
        if resp.status_code != 200:
            raise OpenRouterError(self._error_message(resp))

        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OpenRouterError("unexpected response shape") from exc
        cost = float((data.get("usage") or {}).get("cost") or 0.0)
        return ChatResult(text=text, cost=cost, model=model)

    @staticmethod
    def _error_message(resp: httpx.Response) -> str:
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except (json.JSONDecodeError, ValueError):
            detail = resp.text[:200]
        return f"OpenRouter error ({resp.status_code}): {detail}".strip()

    # --- high-level prompt calls -----------------------------------------

    def describe(
        self, image_paths: list[Path], model: str, prompt: str | None = None
    ) -> ChatResult:
        urls = [encode_image(p) for p in image_paths]
        return self.chat(model, build_describe_messages(urls, prompt))

    def titles(
        self, description: str, model: str, prompt: str | None = None
    ) -> tuple[list[str], ChatResult]:
        result = self.chat(model, build_titles_messages(description, prompt=prompt))
        return parse_titles(result.text), result

    def tags(
        self, title: str, description: str, model: str, prompt: str | None = None
    ) -> tuple[list[str], ChatResult]:
        result = self.chat(
            model, build_tags_messages(title, description, prompt=prompt)
        )
        return parse_tags(result.text), result

    def categorize(
        self, description: str, categories: list[str], model: str
    ) -> tuple[str, ChatResult]:
        result = self.chat(model, build_category_messages(description, categories))
        return parse_category(result.text, categories), result
