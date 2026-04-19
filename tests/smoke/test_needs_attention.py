"""Smoke tests for needs-attention (PRD §6.10).

One test per trigger condition + render smoke.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from kira_hq.needs_attention import (
    NeedsAttentionReport,
    compute,
    render,
    write,
)

pytestmark = pytest.mark.smoke


NOW = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)


def _write_projects_yaml(path: Path, project_path: Path, *, budget: int = 500_000) -> None:
    doc = {
        "version": 2,
        "projects": [
            {
                "name": "demo",
                "path": str(project_path),
                "status": "active",
                "priority": "medium",
                "cron": "0 */2 * * *",
                "added_at": "2026-04-01",
                "skills": ["kira-hq-render-kanban"],
                "budget_tokens_monthly": budget,
                "budget_tokens_per_run": 50_000,
                "notes": "",
            }
        ],
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def _loader(tasks):
    def _inner(_path):
        return tasks
    return _inner


def test_trigger1_blocked_over_48h(tmp_path):
    yaml_path = tmp_path / "projects.yaml"
    _write_projects_yaml(yaml_path, tmp_path / "demo")
    log = tmp_path / "pipeline.log.md"
    log.write_text("")

    tasks = [{
        "id": "12",
        "title": "Setup Stripe webhook",
        "status": "blocked",
        "priority": "medium",
        "updated_at": (NOW - timedelta(hours=67)).isoformat(),
        "dependencies": ["08"],
    }]
    report = compute(NOW, yaml_path, log, tasks_loader=_loader(tasks))
    assert len(report.blocked) == 1
    assert report.blocked[0].hours >= 67
    assert report.blocked[0].blocked_by == "08"


def test_trigger1_blocked_under_48h_skipped(tmp_path):
    yaml_path = tmp_path / "projects.yaml"
    _write_projects_yaml(yaml_path, tmp_path / "demo")
    log = tmp_path / "pipeline.log.md"
    log.write_text("")

    tasks = [{
        "id": "3",
        "title": "Still blocked, but fresh",
        "status": "blocked",
        "priority": "low",
        "updated_at": (NOW - timedelta(hours=10)).isoformat(),
        "dependencies": [],
    }]
    report = compute(NOW, yaml_path, log, tasks_loader=_loader(tasks))
    assert report.blocked == []


def test_trigger2_high_prio_pending_over_72h(tmp_path):
    yaml_path = tmp_path / "projects.yaml"
    _write_projects_yaml(yaml_path, tmp_path / "demo")
    log = tmp_path / "pipeline.log.md"
    log.write_text("")

    tasks = [{
        "id": "7",
        "title": "Urgent review",
        "status": "pending",
        "priority": "high",
        "updated_at": (NOW - timedelta(hours=80)).isoformat(),
    }]
    report = compute(NOW, yaml_path, log, tasks_loader=_loader(tasks))
    assert len(report.high_prio_stale) == 1
    assert report.high_prio_stale[0].task_id == "7"


def test_trigger3_needs_human(tmp_path):
    yaml_path = tmp_path / "projects.yaml"
    _write_projects_yaml(yaml_path, tmp_path / "demo")
    log = tmp_path / "pipeline.log.md"
    log.write_text("")

    tasks = [{
        "id": "2",
        "title": "Retries exhausted",
        "status": "needs-human",
        "priority": "medium",
        "updated_at": (NOW - timedelta(hours=2)).isoformat(),
    }]
    report = compute(NOW, yaml_path, log, tasks_loader=_loader(tasks))
    assert len(report.needs_human) == 1
    assert report.needs_human[0].task_id == "2"


def test_trigger4_failed_cron_last_24h(tmp_path, pipeline_log_tmp):
    yaml_path = tmp_path / "projects.yaml"
    _write_projects_yaml(yaml_path, tmp_path / "demo")

    # 2h ago → within 24h window
    pipeline_log_tmp.append(
        timestamp=(NOW - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S"),
        project="demo",
        skill="night-crew",
        status="FAIL",
        notes="incident 2026-04-18T100012",
    )
    # 30h ago → should be ignored
    pipeline_log_tmp.append(
        timestamp=(NOW - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%S"),
        project="demo",
        skill="old-crew",
        status="FAIL",
        notes="old incident",
    )

    report = compute(NOW, yaml_path, pipeline_log_tmp.path, tasks_loader=_loader([]))
    assert len(report.failed_crons) == 1
    assert report.failed_crons[0].skill == "night-crew"


def test_trigger5_budget_exceeded(tmp_path, pipeline_log_tmp):
    yaml_path = tmp_path / "projects.yaml"
    _write_projects_yaml(yaml_path, tmp_path / "demo", budget=100_000)

    # two rows within 30d whose sum exceeds the budget
    pipeline_log_tmp.append(
        timestamp=(NOW - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S"),
        project="demo",
        skill="s",
        tokens_in=60_000,
        tokens_out=20_000,
        status="ok",
    )
    pipeline_log_tmp.append(
        timestamp=(NOW - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S"),
        project="demo",
        skill="s",
        tokens_in=30_000,
        tokens_out=10_000,
        status="ok",
    )
    report = compute(NOW, yaml_path, pipeline_log_tmp.path, tasks_loader=_loader([]))
    assert len(report.budget_exceeded) == 1
    bi = report.budget_exceeded[0]
    assert bi.tokens_used == 120_000
    assert bi.budget == 100_000


def test_trigger5_under_budget_not_flagged(tmp_path, pipeline_log_tmp):
    yaml_path = tmp_path / "projects.yaml"
    _write_projects_yaml(yaml_path, tmp_path / "demo", budget=500_000)
    pipeline_log_tmp.append(
        timestamp=(NOW - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S"),
        project="demo",
        tokens_in=10_000, tokens_out=5_000, status="ok",
    )
    report = compute(NOW, yaml_path, pipeline_log_tmp.path, tasks_loader=_loader([]))
    assert report.budget_exceeded == []


def test_render_all_sections(tmp_path):
    r = NeedsAttentionReport(generated_at="2026-04-18T12:00:00")
    from kira_hq.needs_attention import (
        BlockedItem, StaleHighItem, NeedsHumanItem, FailedCronItem, BudgetItem,
    )
    r.blocked.append(BlockedItem("demo", "12", "Setup Stripe webhook", "08", 67))
    r.high_prio_stale.append(StaleHighItem("demo", "7", "Urgent", 80))
    r.needs_human.append(NeedsHumanItem("demo", "2", "Retries exhausted"))
    r.failed_crons.append(FailedCronItem("demo", "night-crew", "2026-04-18T10:00", "incident X"))
    r.budget_exceeded.append(BudgetItem("demo", 120_000, 100_000))
    md = render(r)
    assert "🔴 Blocked >48h (1)" in md
    assert "🟠 High-prio stale >72h (1)" in md
    assert "🔥 Needs-human (1)" in md
    assert "🚨 Failed crons (1)" in md
    assert "💰 Budget exceeded (1)" in md
    assert 'demo/T-12 "Setup Stripe webhook" — blocked by 08, 67h' in md


def test_render_empty_report():
    r = NeedsAttentionReport(generated_at="2026-04-18T12:00:00")
    md = render(r)
    assert "No items" in md


def test_write_creates_file(tmp_path):
    r = NeedsAttentionReport(generated_at="2026-04-18T12:00:00")
    out = write(r, path=tmp_path / "needs-attention.md")
    assert out.exists()
    assert out.read_text().startswith("# Needs Attention")
