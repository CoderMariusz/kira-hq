"""Integration tests for tokens — PRD §6.2.

Exercises the real flow: pipeline_log.append_entry writes rows,
tokens.rollup_day + write_daily_rollup + check_run_budget consume them,
against a projects.yaml v2 produced by the shared fixture.
"""
from __future__ import annotations

import json

import pytest

from kira_hq.pipeline_log import append_entry
from kira_hq.tokens import (
    check_run_budget,
    rollup_day,
    top_n_weekly,
    write_daily_rollup,
)

pytestmark = pytest.mark.integration


def _row(log, **kw):
    defaults = dict(
        provider="sonnet", expand_used=False, status="ok",
        duration_s=1.0, notes="",
    )
    defaults.update(kw)
    append_entry(log, **defaults)


def test_daily_rollup_from_real_pipeline_log_writes(tmp_path):
    log = tmp_path / "global-pipeline.log.md"
    metrics = tmp_path / ".kira-hq" / "metrics"

    _row(log, timestamp="2026-04-17T03:00:00", project="kira-hq",
         skill="render", tokens_in=12, tokens_out=4)
    _row(log, timestamp="2026-04-17T04:00:00", project="kira-hq",
         skill="report", tokens_in=300, tokens_out=120)
    _row(log, timestamp="2026-04-17T05:00:00", project="monopilot",
         skill="night-crew", tokens_in=12450, tokens_out=3201)

    out_path = write_daily_rollup("2026-04-17", log, metrics_dir=metrics)
    payload = json.loads(out_path.read_text())

    assert payload["date"] == "2026-04-17"
    assert payload["projects"]["kira-hq"] == {"tokens_in": 312, "tokens_out": 124}
    assert payload["projects"]["monopilot"] == {
        "tokens_in": 12450, "tokens_out": 3201,
    }


def test_weekly_top_n_across_multiple_days(tmp_path):
    log = tmp_path / "log.md"
    # Week 16 of 2026: 2026-04-13 .. 2026-04-19
    _row(log, timestamp="2026-04-13T09:00:00", project="kira-hq",
         skill="a", tokens_in=10, tokens_out=5)
    _row(log, timestamp="2026-04-15T09:00:00", project="monopilot",
         skill="b", tokens_in=500, tokens_out=100)
    _row(log, timestamp="2026-04-16T09:00:00", project="third",
         skill="c", tokens_in=70, tokens_out=30)
    # Out-of-week row must not count
    _row(log, timestamp="2026-04-20T09:00:00", project="kira-hq",
         skill="a", tokens_in=9999, tokens_out=9999)

    top = top_n_weekly("2026-W16", log, n=3)
    names = [t[0] for t in top]
    assert names == ["monopilot", "third", "kira-hq"]
    assert top[0][1] == 500 and top[0][2] == 100


def test_check_run_budget_uses_projects_yaml(tmp_path, projects_yaml_tmp):
    yaml_path = projects_yaml_tmp(entries=1)
    # Default entry has budget_tokens_per_run=50_000 (see conftest)
    assert check_run_budget("proj0", 1_000, yaml_path) is True
    assert check_run_budget("proj0", 50_000, yaml_path) is True
    assert check_run_budget("proj0", 50_001, yaml_path) is False


def test_check_run_budget_unknown_project_passes(tmp_path, projects_yaml_tmp):
    yaml_path = projects_yaml_tmp(entries=1)
    # Unknown project → no enforcement (returns True).
    assert check_run_budget("ghost", 10**9, yaml_path) is True
