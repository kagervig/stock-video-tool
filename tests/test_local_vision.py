"""Tests for the local-vision provider stub.

The comparison tests are placeholders (skipped) until a local backend lands;
they mark where we'll benchmark local vs cloud for quality and speed.
"""

from __future__ import annotations

import pytest

from stock_video_tool.core import local_vision


def test_describe_stub_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        local_vision.describe([])


def test_tags_stub_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        local_vision.tags([])


@pytest.mark.skip(reason="placeholder: benchmark local vs cloud once implemented")
def test_local_description_quality_vs_cloud():
    ...


@pytest.mark.skip(reason="placeholder: benchmark local vs cloud once implemented")
def test_local_tag_quality_vs_cloud():
    ...
