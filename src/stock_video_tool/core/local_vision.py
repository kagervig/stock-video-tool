"""Placeholder for a local image-recognition provider.

Stubbed so we can later benchmark local approaches against the cloud
(OpenRouter) path on description quality, tag quality, speed, and cost.

Candidate backends to compare when this is implemented:
  - Ollama-served VLMs (qwen2.5-vl, llava, moondream, llama3.2-vision)
  - Small local VLMs via transformers (Florence-2, BLIP / BLIP-2)
  - Local taggers for the keywords step (RAM, CLIP, macOS Vision framework)

Nothing here is wired into the app yet; see core/openrouter.py for the live
cloud path this will be compared against.
"""

from __future__ import annotations

from pathlib import Path


class LocalVisionNotAvailable(RuntimeError):
    """Raised when a local backend is requested but not available."""


def describe(image_paths: list[Path], model: str = "") -> str:
    """Return a description for the given frames using a local model.

    STUB: not implemented. Matches openrouter.Client.describe's inputs so the
    two paths can be swapped and benchmarked side by side later.
    """
    raise NotImplementedError("local vision provider is not implemented yet")


def tags(image_paths: list[Path], model: str = "") -> list[str]:
    """Return keywords for the given frames using a local tagger.

    STUB: not implemented. A local tagger (e.g. RAM/CLIP) is the most promising
    local replacement for the keywords step.
    """
    raise NotImplementedError("local tagger is not implemented yet")
