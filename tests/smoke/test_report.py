"""Smoke tests for kira_hq.skills.report — PRD §4.M4."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from kira_hq.pipeline_log import HEADER
from kira_hq.skills.report import generate_report_json

pytestmark = pytest.mark.smoke


def test_report_includes_changes_failures_and_token_delta(pipeline_log_tmp):
    pipeline_log_tmp.append(
        timestamp="2026-04-17T03:00:00+00:00",
        project="p1",
        skill="x",
        provider="sonnet",
        tokens_in=10,
        tokens_out=20,
        status="ok",
        notes="a",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-17T04:00:00+00:00",
        project="p2",
        skill="y",
        provider="kimi",
        tokens_in=5,
        tokens_out=8,
        status="fail",
        notes="b",
    )

    since = datetime(2026, 4, 17, 2, 0, 0, tzinfo=timezone.utc)
    out = generate_report_json(pipeline_log_tmp.path, since=since)

    assert out["changes_since"] == since.isoformat()
    assert out["runs"] == 2
    assert out["failures"] == 1
    assert out["token_delta"] == {"tokens_in": 15, "tokens_out": 28}
    assert out["projects"] == ["p1", "p2"]
    assert any(item["project"] == "p2" and item["status"] == "fail" for item in out["items"])


def test_report_handles_missing_log_gracefully(tmp_path):
    since = datetime(2026, 4, 17, 2, 0, 0, tzinfo=timezone.utc)
    out = generate_report_json(tmp_path / "missing.md", since=since)

    assert out["runs"] == 0
    assert out["failures"] == 0
    assert out["items"] == []
