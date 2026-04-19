"""Integration tests for needs-attention — end-to-end against real fixtures
(fake_project + real projects.yaml v2 + real pipeline_log appender)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import json
import pytest
import yaml

from kira_hq.needs_attention import compute, write, DEFAULT_OUTPUT

pytestmark = pytest.mark.integration


NOW = datetime(2026, 4, 18, 12, 0, 0, tzinfo=timezone.utc)


def _projects_yaml_from_fakeproject(yaml_path: Path, fake_project_obj, *, budget=500_000) -> None:
    doc = {
        "version": 2,
        "projects": [
            {
                "name": fake_project_obj.path.name,
                "path": str(fake_project_obj.path),
                "status": "active",
                "priority": "high",
                "cron": "0 */1 * * *",
                "added_at": "2026-04-01",
                "skills": ["kira-hq-render-kanban"],
                "budget_tokens_monthly": budget,
                "budget_tokens_per_run": 50_000,
                "notes": "",
            }
        ],
    }
    yaml_path.write_text(yaml.safe_dump(doc, sort_keys=False))


def _patch_task(project, task_id: str, **fields) -> None:
    """Edit one task inside the project's tasks.json in-place."""
    data = json.loads(project.tasks_json.read_text())
    tasks = data["master"]["tasks"]
    for t in tasks:
        if t["id"] == task_id:
            t.update(fields)
            break
    project.tasks_json.write_text(json.dumps(data, indent=2))


def test_end_to_end_all_triggers(tmp_path, fake_project, pipeline_log_tmp):
    """One project hitting 4 of 5 triggers at once (blocked, high-stale,
    needs-human, failed-cron). Budget trigger covered separately to keep numbers clean."""
    fp = fake_project(name="demo", tasks_n=5)
    # Ensure the 3 tasks we care about have precise status+age.
    _patch_task(fp, "1",
                status="blocked",
                priority="medium",
                updated_at=(NOW - timedelta(hours=60)).isoformat(),
                dependencies=["08"],
                title="Blocked task")
    _patch_task(fp, "2",
                status="pending",
                priority="high",
                updated_at=(NOW - timedelta(hours=80)).isoformat(),
                title="Stale high-prio")
    _patch_task(fp, "3",
                status="needs-human",
                priority="medium",
                updated_at=(NOW - timedelta(hours=1)).isoformat(),
                title="Retry exhausted")
    # Make tasks 4+5 recent pending so they don't trip anything.
    for tid in ("4", "5"):
        _patch_task(fp, tid,
                    status="pending",
                    priority="low",
                    updated_at=(NOW - timedelta(hours=1)).isoformat())

    yaml_path = tmp_path / "projects.yaml"
    _projects_yaml_from_fakeproject(yaml_path, fp)

    pipeline_log_tmp.append(
        timestamp=(NOW - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S"),
        project="demo",
        skill="night-crew",
        status="FAIL",
        notes="timeout",
    )

    report = compute(NOW, yaml_path, pipeline_log_tmp.path)
    assert len(report.blocked) == 1 and report.blocked[0].task_id == "1"
    assert len(report.high_prio_stale) == 1 and report.high_prio_stale[0].task_id == "2"
    assert len(report.needs_human) == 1 and report.needs_human[0].task_id == "3"
    assert len(report.failed_crons) == 1
    assert report.budget_exceeded == []


def test_archived_project_ignored(tmp_path, fake_project, pipeline_log_tmp):
    fp = fake_project(name="oldie", tasks_n=3)
    _patch_task(fp, "1",
                status="blocked",
                updated_at=(NOW - timedelta(hours=100)).isoformat())

    yaml_path = tmp_path / "projects.yaml"
    doc = {
        "version": 2,
        "projects": [{
            "name": "oldie",
            "path": str(fp.path),
            "status": "archived",
            "priority": "low",
            "cron": "0 */2 * * *",
            "added_at": "2025-01-01",
            "skills": [],
            "budget_tokens_monthly": 100_000,
            "budget_tokens_per_run": 10_000,
            "notes": "",
        }],
    }
    yaml_path.write_text(yaml.safe_dump(doc))
    report = compute(NOW, yaml_path, pipeline_log_tmp.path)
    assert report.is_empty


def test_write_output_is_parseable_markdown(tmp_path, fake_project, pipeline_log_tmp):
    fp = fake_project(name="demo", tasks_n=2)
    _patch_task(fp, "1",
                status="blocked",
                updated_at=(NOW - timedelta(hours=72)).isoformat(),
                dependencies=["X"],
                title="Blocker")

    yaml_path = tmp_path / "projects.yaml"
    _projects_yaml_from_fakeproject(yaml_path, fp)

    report = compute(NOW, yaml_path, pipeline_log_tmp.path)
    out_path = tmp_path / "needs-attention.md"
    write(report, path=out_path)
    text = out_path.read_text()
    assert text.startswith("# Needs Attention — generated ")
    assert "🔴 Blocked >48h" in text
    # Must not leak the default path when a custom path is provided
    assert str(DEFAULT_OUTPUT) not in text


def test_ok_status_not_flagged(tmp_path, fake_project, pipeline_log_tmp):
    """Only FAIL-status rows from last 24h count as failed crons."""
    fp = fake_project(name="demo", tasks_n=1)
    yaml_path = tmp_path / "projects.yaml"
    _projects_yaml_from_fakeproject(yaml_path, fp)
    # Mark the only task as done so no task trigger fires.
    _patch_task(fp, "1", status="done", updated_at=NOW.isoformat())

    pipeline_log_tmp.append(
        timestamp=(NOW - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S"),
        project="demo", skill="s", status="ok",
    )
    report = compute(NOW, yaml_path, pipeline_log_tmp.path)
    assert report.failed_crons == []
