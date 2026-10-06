"""Tests for core.stats — per-model, per-query-type cost/time averages."""

from __future__ import annotations

from stock_video_tool.core.stats import Stats


def _stats(tmp_path):
    return Stats(path=tmp_path / "stats.json")


def test_summary_none_when_no_data(tmp_path):
    assert _stats(tmp_path).summary("a/b", "tags") is None


def test_record_then_summary_averages(tmp_path):
    s = _stats(tmp_path)
    s.record("a/b", "tags", cost=0.002, seconds=3.0)
    s.record("a/b", "tags", cost=0.004, seconds=5.0)
    summary = s.summary("a/b", "tags")
    assert summary["count"] == 2
    assert summary["avg_cost"] == 0.003
    assert summary["avg_time"] == 4.0


def test_query_types_are_tracked_separately(tmp_path):
    s = _stats(tmp_path)
    s.record("a/b", "tags", 0.001, 1.0)
    s.record("a/b", "titles", 0.009, 9.0)
    assert s.summary("a/b", "tags")["avg_cost"] == 0.001
    assert s.summary("a/b", "titles")["avg_cost"] == 0.009


def test_all_summaries_lists_every_model_and_type(tmp_path):
    s = _stats(tmp_path)
    s.record("z/model", "tags", 0.001, 1.0)
    s.record("a/model", "description", 0.002, 2.0)
    rows = s.all_summaries()
    assert [(r["model"], r["query_type"]) for r in rows] == [
        ("a/model", "description"), ("z/model", "tags"),
    ]


def test_record_rating_counts_good_and_bad(tmp_path):
    s = _stats(tmp_path)
    s.record("a/b", "tags", 0.001, 1.0)
    s.record_rating("a/b", "tags", good=True)
    s.record_rating("a/b", "tags", good=True)
    s.record_rating("a/b", "tags", good=False)
    summary = s.summary("a/b", "tags")
    assert summary["good"] == 2
    assert summary["bad"] == 1


def test_stats_persist_across_instances(tmp_path):
    path = tmp_path / "stats.json"
    Stats(path=path).record("a/b", "tags", 0.002, 2.0)
    assert Stats(path=path).summary("a/b", "tags")["count"] == 1
