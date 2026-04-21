"""Integration tests for kira_hq.skills.weekly_review — PRD §4.M4 + §6.18."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from kira_hq.skills.weekly_review import build_telegram_summary, run_weekly_review

pytestmark = pytest.mark.integration


def _write_tasks(project_dir: Path, tasks: list[dict]) -> None:
    tasks_path = project_dir / ".taskmaster" / "tasks"
    tasks_path.mkdir(parents=True, exist_ok=True)
    tasks_path.joinpath("tasks.json").write_text(
        __import__("json").dumps({"master": {"tasks": tasks}}, indent=2)
    )


def test_weekly_review_renders_all_7_sections_and_summary(
    tmp_path: Path,
    pipeline_log_tmp,
):
    alpha = tmp_path / "alpha"
    beta = tmp_path / "beta"
    stale = tmp_path / "stale"
    for path in (alpha, beta, stale):
        path.mkdir(parents=True)

    _write_tasks(
        alpha,
        [
            {
                "id": "1",
                "title": "Ship alpha",
                "status": "done",
                "priority": "high",
                "updated_at": "2026-04-17T10:00:00+00:00",
            },
            {
                "id": "2",
                "title": "Blocked alpha",
                "status": "blocked",
                "priority": "medium",
                "updated_at": "2026-04-15T08:00:00+00:00",
                "dependencies": ["DEP-1"],
            },
            {
                "id": "3",
                "title": "Need a human",
                "status": "needs-human",
                "priority": "high",
                "updated_at": "2026-04-18T08:00:00+00:00",
            },
        ],
    )
    _write_tasks(
        beta,
        [
            {
                "id": "1",
                "title": "Ship beta",
                "status": "done",
                "priority": "medium",
                "updated_at": "2026-04-18T10:00:00+00:00",
            }
        ],
    )
    _write_tasks(
        stale,
        [
            {
                "id": "1",
                "title": "Dormant",
                "status": "pending",
                "priority": "low",
                "updated_at": "2026-03-01T10:00:00+00:00",
            }
        ],
    )

    projects_yaml = tmp_path / "projects.yaml"
    projects_yaml.write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "projects": [
                    {
                        "name": "alpha",
                        "path": str(alpha),
                        "status": "active",
                        "priority": "high",
                        "cron": "0 * * * *",
                        "added_at": "2026-04-01",
                        "skills": ["kira-hq-render-kanban"],
                        "budget_tokens_monthly": 500_000,
                        "budget_tokens_per_run": 50_000,
                        "notes": "",
                    },
                    {
                        "name": "beta",
                        "path": str(beta),
                        "status": "active",
                        "priority": "medium",
                        "cron": "0 * * * *",
                        "added_at": "2026-04-01",
                        "skills": ["kira-hq-render-kanban"],
                        "budget_tokens_monthly": 500_000,
                        "budget_tokens_per_run": 50_000,
                        "notes": "",
                    },
                    {
                        "name": "stale-proj",
                        "path": str(stale),
                        "status": "stale",
                        "priority": "low",
                        "cron": "0 * * * *",
                        "added_at": "2026-03-01",
                        "skills": ["kira-hq-render-kanban"],
                        "budget_tokens_monthly": 500_000,
                        "budget_tokens_per_run": 50_000,
                        "notes": "",
                    },
                ],
            },
            sort_keys=False,
        )
    )

    # Previous ISO week for WoW delta.
    pipeline_log_tmp.append(
        timestamp="2026-04-07T09:00:00+00:00",
        project="alpha",
        skill="kira-hq-render-kanban",
        provider="sonnet",
        tokens_in=60,
        tokens_out=40,
        status="ok",
        notes="tasks_completed=1",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-08T09:00:00+00:00",
        project="beta",
        skill="kira-hq-render-kanban",
        provider="sonnet",
        tokens_in=30,
        tokens_out=20,
        status="ok",
        notes="tasks_completed=1",
    )

    # Current ISO week.
    pipeline_log_tmp.append(
        timestamp="2026-04-13T23:30:00+00:00",
        project="alpha",
        skill="kira-hq-render-kanban",
        provider="hermes",
        tokens_in=40,
        tokens_out=20,
        status="ok",
        notes="track=A tasks_completed=2 alerts=0",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-14T10:00:00+00:00",
        project="alpha",
        skill="kira-hq-render-kanban",
        provider="hermes",
        tokens_in=160,
        tokens_out=140,
        status="ok",
        notes="track=A tasks_completed=1 alerts=1",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-15T10:00:00+00:00",
        project="alpha",
        skill="kira-hq-render-kanban",
        provider="hermes",
        tokens_in=0,
        tokens_out=0,
        status="fail",
        notes="incident=INC-1 retry_exhausted",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-16T09:00:00+00:00",
        project="beta",
        skill="kira-hq-render-kanban",
        provider="claude-code",
        tokens_in=90,
        tokens_out=30,
        status="ok",
        notes="track=B tasks_completed=3 alerts=0",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-18T09:00:00+00:00",
        project="beta",
        skill="kira-hq-render-kanban",
        provider="claude-code",
        tokens_in=10,
        tokens_out=10,
        status="fail",
        notes="incident=INC-2 retry_exhausted",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-18T21:00:00+00:00",
        project="gamma",
        skill="other-skill",
        provider="kimi",
        tokens_in=20,
        tokens_out=5,
        status="ok",
        notes="tasks_completed=1",
    )

    snapshots_dir = tmp_path / "snaps"
    for d in [
        "2026-04-13",
        "2026-04-14",
        "2026-04-16",
        "2026-04-17",
        "2026-04-19",
    ]:
        (snapshots_dir / d).mkdir(parents=True)

    reviews = tmp_path / "reviews"
    artifacts = run_weekly_review(
        pipeline_log=pipeline_log_tmp.path,
        snapshots_dir=snapshots_dir,
        reviews_dir=reviews,
        now=datetime(2026, 4, 18, 9, 0, 0, tzinfo=timezone.utc),
        projects_yaml=projects_yaml,
    )

    out = artifacts.path
    assert out.exists()
    assert out.name == "2026-W16.md"
    text = out.read_text()

    assert "# Weekly review 2026-W16" in text
    assert "## 1) Tasks" in text
    assert "## 2) Tokens" in text
    assert "## 3) Cron" in text
    assert "## 4) Parallel track A vs B" in text
    assert "## 5) Snapshot health" in text
    assert "## 6) Stale projects + suggested action" in text
    assert "## 7) Hermes autolearn delta" in text

    assert "- alpha: completed=3, blockers=1, needs-human=1" in text
    assert "- beta: completed=3, blockers=0, needs-human=0" in text
    assert "- alpha: total=360 (Δ +260 vs 2026-W15)" in text
    assert "- beta: total=140 (Δ +90 vs 2026-W15)" in text
    assert "- Top-3: alpha=360, beta=140, gamma=25" in text
    assert "- alpha: 66.7% success (2/3), failed runs: 2026-04-15T10:00:00+00:00 kira-hq-render-kanban" in text
    assert "- beta: 50.0% success (1/2), failed runs: 2026-04-18T09:00:00+00:00 kira-hq-render-kanban" in text
    assert "- Track A: tasks=3, tokens=360, human_interventions=0, alerts=1, avg_latency_s=0.1" in text
    assert "- Track B: tasks=3, tokens=120, human_interventions=0, alerts=0, avg_latency_s=0.1" in text
    assert "- Present: 5/7 days" in text
    assert "- ALERT: missed 2 day(s): 2026-04-15, 2026-04-18" in text
    assert "- stale-proj: status=stale, last_activity=none, suggested_action=/unstale stale-proj after human review" in text
    assert "- unavailable (Hermes API absent)" in text
    assert f"Telegram summary artifact: {artifacts.telegram_summary_path}" in text

    assert artifacts.telegram_summary_path.exists()
    assert artifacts.telegram_summary_path.name == "2026-W16.telegram.txt"
    summary = build_telegram_summary(out)
    assert "Weekly review 2026-W16" in summary
    assert str(out) in summary
    assert "alpha: completed=3" in summary
    assert artifacts.telegram_summary == summary
    assert artifacts.telegram_summary_path.read_text() == summary


def test_weekly_review_uses_one_normalized_week_membership_rule(tmp_path: Path, pipeline_log_tmp):
    pipeline_log_tmp.append(
        timestamp="2026-04-20T00:30:00+02:00",
        project="boundary-offset",
        skill="offset-skill",
        provider="sonnet",
        tokens_in=900,
        tokens_out=900,
        status="ok",
        notes="raw date says Monday, UTC says prior ISO week",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-21T03:00:00+00:00",
        project="in-week",
        skill="current-week-skill",
        provider="sonnet",
        tokens_in=120,
        tokens_out=80,
        status="ok",
        notes="track=A tasks_completed=1 alerts=0",
    )

    snapshots_dir = tmp_path / "snaps"
    for d in [
        "2026-04-20",
        "2026-04-21",
        "2026-04-22",
    ]:
        (snapshots_dir / d).mkdir(parents=True)

    reviews = tmp_path / "reviews"
    artifacts = run_weekly_review(
        pipeline_log=pipeline_log_tmp.path,
        snapshots_dir=snapshots_dir,
        reviews_dir=reviews,
        now=datetime(2026, 4, 22, 9, 0, 0, tzinfo=timezone.utc),
        projects_yaml=None,
    )

    out = artifacts.path
    text = out.read_text()

    assert out.name == "2026-W17.md"
    assert "Reporting window: 2026-04-20 to 2026-04-26" in text
    assert "- in-week: completed=1, blockers=0, needs-human=0" in text
    assert "- in-week: total=200" in text
    assert "boundary-offset" not in text
    assert "Track A" in text


def test_weekly_review_marks_parallel_track_inactive_without_current_week_rows(
    tmp_path: Path,
    pipeline_log_tmp,
):
    pipeline_log_tmp.append(
        timestamp="2026-04-08T09:00:00+00:00",
        project="alpha",
        skill="skill",
        provider="hermes",
        tokens_in=20,
        tokens_out=20,
        status="ok",
        notes="track=A tasks_completed=1 alerts=0",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-15T09:00:00+00:00",
        project="alpha",
        skill="skill",
        provider="hermes",
        tokens_in=20,
        tokens_out=20,
        status="ok",
        notes="tasks_completed=1",
    )

    artifacts = run_weekly_review(
        pipeline_log=pipeline_log_tmp.path,
        snapshots_dir=tmp_path / "snaps",
        reviews_dir=tmp_path / "reviews",
        now=datetime(2026, 4, 15, 9, 0, 0, tzinfo=timezone.utc),
        projects_yaml=None,
    )

    assert "- inactive this week (no track=A/track=B evaluation rows)" in artifacts.path.read_text()


def test_weekly_review_excludes_synthetic_observability_rows(tmp_path: Path, pipeline_log_tmp):
    pipeline_log_tmp.append(
        timestamp="2026-04-15T09:00:00+00:00",
        project="alpha",
        skill="ship",
        provider="hermes",
        tokens_in=20,
        tokens_out=10,
        status="ok",
        notes="track=A tasks_completed=2 alerts=0",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-15T10:00:00+00:00",
        project="kira-hq",
        skill="kira-hq-report",
        provider="hermes",
        tokens_in=500,
        tokens_out=500,
        status="ok",
        notes="summary",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-15T11:00:00+00:00",
        project="kira-hq",
        skill="kira-weekly-review",
        provider="hermes",
        tokens_in=600,
        tokens_out=600,
        status="ok",
        notes="summary",
    )

    artifacts = run_weekly_review(
        pipeline_log=pipeline_log_tmp.path,
        snapshots_dir=tmp_path / "snaps",
        reviews_dir=tmp_path / "reviews",
        now=datetime(2026, 4, 15, 12, 0, 0, tzinfo=timezone.utc),
        projects_yaml=None,
    )

    text = artifacts.path.read_text()
    assert "- alpha: completed=2, blockers=0, needs-human=0" in text
    assert "- alpha: total=30" in text
    assert "kira-hq-report" not in text
    assert "kira-weekly-review" not in text
    assert "kira-hq: total=" not in text


def test_weekly_review_can_explicitly_disable_parallel_track_reporting(
    tmp_path: Path,
    pipeline_log_tmp,
):
    pipeline_log_tmp.append(
        timestamp="2026-04-15T09:00:00+00:00",
        project="alpha",
        skill="skill",
        provider="hermes",
        tokens_in=20,
        tokens_out=20,
        status="ok",
        notes="track=A tasks_completed=1 alerts=0",
    )

    artifacts = run_weekly_review(
        pipeline_log=pipeline_log_tmp.path,
        snapshots_dir=tmp_path / "snaps",
        reviews_dir=tmp_path / "reviews",
        now=datetime(2026, 4, 15, 9, 0, 0, tzinfo=timezone.utc),
        projects_yaml=None,
        parallel_tracks_enabled=False,
    )

    text = artifacts.path.read_text()
    assert "- disabled by config" in text
    assert "- Track A: tasks=1" not in text
