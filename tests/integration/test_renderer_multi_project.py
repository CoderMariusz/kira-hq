"""Integration test for Module 1 renderer — PRD §4 M1, §6.17.

Multi-project scenario: 3 fixture projects with 10/6/3 tasks each, assert
per-project boards exist with correct totals, plus global overview with
the summed count and pipeline-log rows written.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from kira_hq.pipeline_log import GLOBAL_LOG
from render_kanban import render_all

pytestmark = pytest.mark.integration


def _mk_tasks(n: int) -> list[dict]:
    return [
        {"id": str(i), "title": f"Task {i}", "status": "pending",
         "priority": ["high", "medium", "low"][i % 3]}
        for i in range(1, n + 1)
    ]


def _mk_project(root: Path, name: str, n: int) -> Path:
    p = root / name
    (p / ".taskmaster" / "tasks").mkdir(parents=True)
    (p / ".taskmaster" / "tasks" / "tasks.json").write_text(
        json.dumps({"master": {"tasks": _mk_tasks(n)}}))
    # Seed one ADR so the board includes the ADR section non-empty
    adr = p / "docs" / "ADR"
    adr.mkdir(parents=True)
    (adr / "0001-test-decision.md").write_text(
        "# ADR 0001: Test Decision\n"
        "- **Date:** 2026-04-18\n- **Status:** accepted\n\n"
        "## Context\nfixture\n## Decision\nfixture\n## Consequences\nfixture\n"
    )
    return p


def test_three_projects_render_to_expected_totals(tmp_path, monkeypatch):
    # Redirect global pipeline log into tmp so we don't touch ~/.kira-hq/
    fake_global_log = tmp_path / "global-pipeline.log.md"
    monkeypatch.setattr("kira_hq.pipeline_log.GLOBAL_LOG", fake_global_log)

    sizes = {"alpha": 10, "beta": 6, "gamma": 3}
    projects = []
    for name, n in sizes.items():
        pp = _mk_project(tmp_path, name, n)
        projects.append({
            "name": name, "path": str(pp), "status": "active",
            "priority": "high", "cron": "0 */2 * * *",
            "added_at": "2026-04-18",
            "skills": ["kira-hq-render-kanban"],
            "budget_tokens_monthly": 500_000,
            "budget_tokens_per_run": 50_000,
        })
    yaml_path = tmp_path / "projects.yaml"
    yaml_path.write_text(yaml.safe_dump({"version": 2, "projects": projects}))

    # fetch_tasks → return the fixture tasks directly (avoid task-master CLI)
    def fake_fetch(project_path: Path, *, timeout: int = 30):
        tf = project_path / ".taskmaster" / "tasks" / "tasks.json"
        data = json.loads(tf.read_text())
        return data["master"]["tasks"]

    with patch("render_kanban.fetch_tasks", side_effect=fake_fetch):
        res = render_all(
            projects_yaml=yaml_path,
            global_out=tmp_path / "global-kanban.md",
        )

    assert res["exit_code"] == 0
    assert set(res["per_project"].keys()) == set(sizes.keys())

    # Per-project boards
    for name, n in sizes.items():
        board = (tmp_path / name / "kanban_board.md").read_text()
        assert f"**Total tasks:** {n}" in board
        assert f"# {name} — Kanban Board" in board
        assert "0001" in board  # ADR section populated
        # Per-project pipeline log row written
        per_log = (tmp_path / name / "pipeline.log.md").read_text()
        assert name in per_log
        assert f"{n} tasks rendered" in per_log

    # Global board — table row per project
    global_board = (tmp_path / "global-kanban.md").read_text()
    for name, n in sizes.items():
        assert f"| {name} | {n} |" in global_board

    # Global pipeline log — 3 rows, one per project
    assert fake_global_log.exists()
    gl = fake_global_log.read_text()
    for name in sizes:
        assert name in gl


def test_missing_project_path_logs_skip(tmp_path, monkeypatch):
    fake_global_log = tmp_path / "global-pipeline.log.md"
    monkeypatch.setattr("kira_hq.pipeline_log.GLOBAL_LOG", fake_global_log)

    yaml_path = tmp_path / "projects.yaml"
    yaml_path.write_text(yaml.safe_dump({
        "version": 2,
        "projects": [{
            "name": "ghost", "path": str(tmp_path / "does-not-exist"),
            "status": "active", "priority": "low", "cron": "0 */6 * * *",
            "added_at": "2026-04-18",
            "skills": ["kira-hq-render-kanban"],
            "budget_tokens_monthly": 500_000, "budget_tokens_per_run": 50_000,
        }],
    }))
    res = render_all(projects_yaml=yaml_path,
                     global_out=tmp_path / "g.md")
    assert res["exit_code"] == 2  # all failed (the only project failed)
    # pipeline log has 'skip' status for missing path
    assert "skip" in fake_global_log.read_text()


def test_pipeline_log_row_uses_10col_v2_schema(tmp_path, monkeypatch):
    fake_global_log = tmp_path / "gpl.md"
    monkeypatch.setattr("kira_hq.pipeline_log.GLOBAL_LOG", fake_global_log)
    project = _mk_project(tmp_path, "solo", 2)
    yaml_path = tmp_path / "p.yaml"
    yaml_path.write_text(yaml.safe_dump({
        "version": 2,
        "projects": [{
            "name": "solo", "path": str(project), "status": "active",
            "priority": "medium", "cron": "0 */2 * * *",
            "added_at": "2026-04-18",
            "skills": ["kira-hq-render-kanban"],
            "budget_tokens_monthly": 500_000, "budget_tokens_per_run": 50_000,
        }],
    }))
    with patch("render_kanban.fetch_tasks",
               return_value=[{"id": "1", "title": "T", "status": "pending"}]):
        render_all(projects_yaml=yaml_path,
                   global_out=tmp_path / "g.md")

    header_line = fake_global_log.read_text().splitlines()[0]
    # 10 columns per PRD §6.1 / §6.19
    for col in ("timestamp", "project", "skill", "provider", "expand_used",
                "tokens_in", "tokens_out", "status", "duration_s", "notes"):
        assert col in header_line
