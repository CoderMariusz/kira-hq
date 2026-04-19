"""Integration tests for kira_hq.skills.weekly_review — PRD §4.M4 + §6.18 stub."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from kira_hq.skills.weekly_review import run_weekly_review

pytestmark = pytest.mark.integration


def test_weekly_review_writes_file(tmp_path: Path, pipeline_log_tmp):
    pipeline_log_tmp.append(
        timestamp="2026-04-09T03:00:00+00:00",
        project="old-week",
        skill="other-skill",
        provider="kimi",
        tokens_in=999,
        tokens_out=999,
        status="ok",
        notes="outside ISO week",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-14T03:00:00+00:00",
        project="p1",
        skill="kira-hq-render-kanban",
        provider="sonnet",
        tokens_in=100,
        tokens_out=200,
        status="ok",
        notes="a",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-15T03:00:00",
        project="p2",
        skill="other-skill",
        provider="kimi",
        tokens_in=500,
        tokens_out=400,
        status="fail",
        notes="b",
    )

    snapshots_dir = tmp_path / "snaps"
    for d in [
        "2026-04-13",
        "2026-04-14",
        "2026-04-15",
        "2026-04-16",
        "2026-04-17",
        "2026-04-18",
        "2026-04-19",
    ]:
        (snapshots_dir / d).mkdir(parents=True)

    reviews = tmp_path / "reviews"
    out = run_weekly_review(
        pipeline_log=pipeline_log_tmp.path,
        snapshots_dir=snapshots_dir,
        reviews_dir=reviews,
        now=datetime(2026, 4, 15, 9, 0, 0, tzinfo=timezone.utc),
        projects_yaml=None,
    )

    assert out.exists()
    text = out.read_text()
    assert out.name == "2026-W16.md"
    assert "Reporting window: 2026-04-13 to 2026-04-19" in text
    assert "Top-3 token consumers" in text
    assert "Snapshot health" in text
    assert "7/7" in text
    assert "p2" in text and "1 fail" in text
    assert "old-week" not in text
    assert "Parallel track" in text
