"""Smoke tests for tokens — PRD §6.2."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from kira_hq.pipeline_log import HEADER, append_entry
from kira_hq.tokens import (
    _iso_week_days,
    parse_log,
    rollup_day,
    top_n_weekly,
    write_daily_rollup,
)

pytestmark = pytest.mark.smoke


def _seed(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER)
    for kw in rows:
        defaults = dict(
            provider="sonnet", expand_used=False, status="ok",
            duration_s=1.0, notes="",
        )
        defaults.update(kw)
        append_entry(path, **defaults)


def test_parse_log_returns_empty_on_missing(tmp_path):
    assert parse_log(tmp_path / "nope.md") == []


def test_parse_log_skips_header_and_separator(tmp_path):
    log = tmp_path / "p.log.md"
    _seed(log, [
        {"timestamp": "2026-04-17T03:00:00", "project": "kira-hq", "skill": "s",
         "tokens_in": 1, "tokens_out": 2},
    ])
    rows = parse_log(log)
    assert len(rows) == 1
    assert rows[0].project == "kira-hq"
    assert rows[0].tokens_in == 1
    assert rows[0].tokens_out == 2


def test_rollup_day_aggregates_by_project(tmp_path):
    log = tmp_path / "g.log.md"
    _seed(log, [
        {"timestamp": "2026-04-17T03:00:00", "project": "kira-hq",
         "skill": "render", "tokens_in": 10, "tokens_out": 5},
        {"timestamp": "2026-04-17T04:00:00", "project": "kira-hq",
         "skill": "report", "tokens_in": 20, "tokens_out": 10},
        {"timestamp": "2026-04-17T05:00:00", "project": "monopilot",
         "skill": "night", "tokens_in": 100, "tokens_out": 50},
        {"timestamp": "2026-04-18T03:00:00", "project": "kira-hq",
         "skill": "render", "tokens_in": 999, "tokens_out": 999},  # other day
    ])
    out = rollup_day("2026-04-17", log)
    assert out["kira-hq"] == {"tokens_in": 30, "tokens_out": 15}
    assert out["monopilot"] == {"tokens_in": 100, "tokens_out": 50}
    assert "other-day-only" not in out  # 18th not bucketed here


def test_write_daily_rollup_writes_json(tmp_path):
    log = tmp_path / "log.md"
    metrics = tmp_path / "metrics"
    _seed(log, [
        {"timestamp": "2026-04-17T03:00:00", "project": "kira-hq",
         "skill": "s", "tokens_in": 7, "tokens_out": 3},
    ])
    out = write_daily_rollup("2026-04-17", log, metrics_dir=metrics)
    assert out.exists()
    payload = json.loads(out.read_text())
    assert payload["date"] == "2026-04-17"
    assert payload["projects"]["kira-hq"] == {"tokens_in": 7, "tokens_out": 3}


def test_iso_week_days_monday_to_sunday():
    days = _iso_week_days("2026-W16")
    assert len(days) == 7
    # 2026 ISO week 16 → Mon 2026-04-13 .. Sun 2026-04-19
    assert days[0] == "2026-04-13"
    assert days[-1] == "2026-04-19"


def test_top_n_weekly_ranks_total_tokens(tmp_path):
    log = tmp_path / "w.log.md"
    _seed(log, [
        {"timestamp": "2026-04-17T03:00:00", "project": "kira-hq",
         "skill": "s", "tokens_in": 10, "tokens_out": 5},
        {"timestamp": "2026-04-17T04:00:00", "project": "monopilot",
         "skill": "s", "tokens_in": 200, "tokens_out": 100},
        {"timestamp": "2026-04-18T04:00:00", "project": "third",
         "skill": "s", "tokens_in": 50, "tokens_out": 50},
    ])
    top = top_n_weekly("2026-W16", log, n=3)
    assert top[0][0] == "monopilot"    # 300 total
    assert top[1][0] == "third"        # 100 total
    assert top[2][0] == "kira-hq"      # 15 total


def test_malformed_rows_skipped(tmp_path):
    log = tmp_path / "bad.log.md"
    log.write_text(HEADER + "| broken | row | only | three | cells |\n")
    assert parse_log(log) == []
