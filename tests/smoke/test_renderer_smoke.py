"""Smoke tests for scripts/render_kanban.py — PRD §4 M1, §6.17."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from render_kanban import (
    categorize,
    render_all,
    render_global,
    render_project_kanban,
)

pytestmark = pytest.mark.smoke


def _mk_yaml(path: Path, projects: list[dict]) -> None:
    path.write_text(yaml.safe_dump({"version": 2, "projects": projects}))


def _mk_project(root: Path, name: str, tasks: list[dict]) -> Path:
    p = root / name
    (p / ".taskmaster" / "tasks").mkdir(parents=True)
    (p / ".taskmaster" / "tasks" / "tasks.json").write_text(
        json.dumps({"master": {"tasks": tasks}}))
    return p


def test_categorize_buckets_statuses():
    tasks = [
        {"id": "1", "status": "pending", "priority": "high"},
        {"id": "2", "status": "needs-human"},
        {"id": "3", "status": "blocked"},
        {"id": "4", "status": "in-progress"},
        {"id": "5", "status": "done", "updated_at": "2020-01-01"},  # not today
    ]
    cats = categorize(tasks)
    assert [t["id"] for t in cats["needs_attention"]] == ["2"]
    assert [t["id"] for t in cats["blocked"]] == ["3"]
    assert [t["id"] for t in cats["in_progress"]] == ["4"]
    assert [t["id"] for t in cats["backlog"]] == ["1"]
    assert cats["done_today"] == []


def test_render_project_kanban_includes_all_sections(tmp_path):
    tasks = [
        {"id": "1", "title": "One", "status": "pending", "priority": "high"},
        {"id": "2", "title": "Two", "status": "blocked",
         "dependencies": ["1"]},
    ]
    result = render_project_kanban("demo", tmp_path, tasks)
    content = result["path"].read_text()
    assert "# demo — Kanban Board" in content
    assert "**Total tasks:** 2" in content
    assert "🔴 Wymaga" in content
    assert "⛔ Blocked" in content
    assert "🟡 In progress" in content
    assert "✅ Done today" in content
    assert "📥 Backlog" in content
    assert "🐛 Fixes" in content
    assert "📚 ADRs" in content  # section appears even without docs/ADR
    assert "One" in content and "Two" in content


def test_render_project_kanban_two_tasks_both_appear(tmp_path):
    tasks = [
        {"id": "a", "title": "Alpha", "status": "pending"},
        {"id": "b", "title": "Beta", "status": "pending"},
    ]
    result = render_project_kanban("p", tmp_path, tasks)
    content = result["path"].read_text()
    assert "Alpha" in content
    assert "Beta" in content


def test_adr_section_picks_up_seed_adrs(tmp_path):
    adr_dir = tmp_path / "docs" / "ADR"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-test.md").write_text(
        "# ADR 0001: Test\n- **Date:** 2026-04-18\n- **Status:** accepted\n"
    )
    render_project_kanban("p", tmp_path, [])
    content = (tmp_path / "kanban_board.md").read_text()
    assert "0001" in content
    assert "Test" in content
    assert "accepted" in content


def test_render_global_has_overview_table(tmp_path):
    per_project = {
        "alpha": {"total": 5, "done": 2,
                  "cats": {"needs_attention": [{"id": "1", "title": "A"}],
                           "blocked": [], "in_progress": [],
                           "done_today": [], "backlog": [], "fixes": []}},
        "beta": {"total": 3, "done": 3,
                 "cats": {"needs_attention": [], "blocked": [],
                          "in_progress": [], "done_today": [],
                          "backlog": [], "fixes": []}},
    }
    out = tmp_path / "global.md"
    render_global(per_project, out)
    content = out.read_text()
    assert "# Kira-HQ — Global Command Center" in content
    assert "## Overview" in content
    assert "| alpha |" in content and "| beta |" in content
    assert "alpha — attention items" in content
    assert "✅ No attention items" not in content  # alpha has attention


def test_render_all_missing_yaml_exits_3(tmp_path):
    res = render_all(projects_yaml=tmp_path / "nope.yaml",
                     global_out=tmp_path / "g.md",
                     write_pipeline_log=False)
    assert res["exit_code"] == 3


def test_render_all_end_to_end_with_mocked_tasks(tmp_path):
    project = _mk_project(tmp_path, "proj-a", [
        {"id": "1", "title": "Alpha", "status": "pending", "priority": "high"},
        {"id": "2", "title": "Beta", "status": "done",
         "updated_at": "2020-01-01"},
    ])
    yaml_path = tmp_path / "projects.yaml"
    _mk_yaml(yaml_path, [{
        "name": "proj-a", "path": str(project), "status": "active",
        "priority": "high", "cron": "0 */2 * * *", "added_at": "2026-04-18",
        "skills": ["kira-hq-render-kanban"],
        "budget_tokens_monthly": 500_000, "budget_tokens_per_run": 50_000,
    }])

    fake_tasks = [
        {"id": "1", "title": "Alpha", "status": "pending", "priority": "high"},
        {"id": "2", "title": "Beta", "status": "done",
         "updated_at": "2020-01-01"},
    ]

    with patch("render_kanban.fetch_tasks", return_value=fake_tasks):
        res = render_all(projects_yaml=yaml_path,
                         global_out=tmp_path / "global-kanban.md",
                         write_pipeline_log=False)

    assert res["exit_code"] == 0
    board = (project / "kanban_board.md").read_text()
    assert "Alpha" in board
    # Beta is done but NOT today → it counts in **Done:** 1 but no bullet
    assert "**Done:** 1" in board
    assert "**Total tasks:** 2" in board
    assert (tmp_path / "global-kanban.md").exists()


def test_render_all_task_master_failure_marks_fail(tmp_path):
    project = _mk_project(tmp_path, "bad", [])
    yaml_path = tmp_path / "projects.yaml"
    _mk_yaml(yaml_path, [{
        "name": "bad", "path": str(project), "status": "active",
        "priority": "medium", "cron": "0 */2 * * *", "added_at": "2026-04-18",
        "skills": ["kira-hq-render-kanban"],
        "budget_tokens_monthly": 500_000, "budget_tokens_per_run": 50_000,
    }])
    with patch("render_kanban.fetch_tasks", return_value=None):
        res = render_all(projects_yaml=yaml_path,
                         global_out=tmp_path / "g.md",
                         write_pipeline_log=False)
    assert res["exit_code"] == 2  # all projects failed
    assert res["per_project"] == {}


def test_render_all_skips_archived(tmp_path):
    project = _mk_project(tmp_path, "arc", [])
    yaml_path = tmp_path / "projects.yaml"
    _mk_yaml(yaml_path, [{
        "name": "arc", "path": str(project), "status": "archived",
        "priority": "low", "cron": "0 */2 * * *", "added_at": "2026-04-18",
        "skills": ["kira-hq-render-kanban"],
        "budget_tokens_monthly": 500_000, "budget_tokens_per_run": 50_000,
    }])
    res = render_all(projects_yaml=yaml_path,
                     global_out=tmp_path / "g.md",
                     write_pipeline_log=False)
    # archived skipped → no projects rendered, no failures either
    assert res["per_project"] == {}
    # render_global writes an empty-attention summary
    assert (tmp_path / "g.md").read_text().startswith("# Kira-HQ")
