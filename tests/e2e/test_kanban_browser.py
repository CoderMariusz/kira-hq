"""E2E placeholder — Module 1 kanban_board.md browser verification (T-8).

Real implementation requires Playwright + a markdown renderer. Per PRD
§6.15, run with `pytest -m e2e`. Defers to T-18 (Next.js) for a full UI
pipeline; this file keeps the E2E tier declared and verifies the two
most important DoD invariants without needing a browser:

    (1) a rendered kanban_board.md contains exactly `N` task-entry lines
        when tasks.json has N tasks (no items silently lost)
    (2) re-rendering after mutation reflects the new count

This covers the PRD §4 M1 E2E acceptance ("10 tasks in JSON → 10 entries
rendered; add 11th → 11 entries") in a headless, deterministic way.
When T-18 lands, replace/augment with real Playwright assertions.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

pytestmark = pytest.mark.e2e


def _task_entry_count(kanban_text: str) -> int:
    """Count markdown bullet lines that look like task entries.

    Renderer emits `- **<id>** — <title> …` for each task row. ADR
    bullets use `- **NNNN** — [Title](docs/ADR/...)` — distinguish by
    checking that the bullet id cell is not 4-digit + bracketed link.
    """
    entries = 0
    for raw in kanban_text.splitlines():
        m = re.match(r"^- \*\*([^*]+)\*\* — (.+)$", raw)
        if not m:
            continue
        tid, rest = m.group(1), m.group(2)
        # Skip ADR bullets: 4-digit id + bracketed title + docs/ADR link
        if re.fullmatch(r"\d{4}", tid) and "docs/ADR/" in rest:
            continue
        entries += 1
    return entries


def _setup(tmp_path: Path, tasks: list[dict]) -> tuple[Path, Path]:
    project = tmp_path / "proj"
    (project / ".taskmaster" / "tasks").mkdir(parents=True)
    (project / ".taskmaster" / "tasks" / "tasks.json").write_text(
        json.dumps({"master": {"tasks": tasks}}))
    yaml_path = tmp_path / "projects.yaml"
    yaml_path.write_text(yaml.safe_dump({
        "version": 2,
        "projects": [{
            "name": "proj", "path": str(project), "status": "active",
            "priority": "high", "cron": "0 */2 * * *",
            "added_at": "2026-04-18",
            "skills": ["kira-hq-render-kanban"],
            "budget_tokens_monthly": 500_000, "budget_tokens_per_run": 50_000,
        }],
    }))
    return project, yaml_path


def test_rendered_entries_match_task_count(tmp_path, monkeypatch):
    from render_kanban import render_all
    monkeypatch.setattr("kira_hq.pipeline_log.GLOBAL_LOG",
                        tmp_path / "gpl.md")

    tasks_10 = [{"id": str(i), "title": f"Task {i}",
                 "status": "pending", "priority": "medium"}
                for i in range(1, 11)]
    project, yaml_path = _setup(tmp_path, tasks_10)

    with patch("render_kanban.fetch_tasks", return_value=tasks_10):
        render_all(projects_yaml=yaml_path,
                   global_out=tmp_path / "g.md",
                   write_pipeline_log=False)

    content = (project / "kanban_board.md").read_text()
    assert _task_entry_count(content) == 10

    # Mutate: add 11th task, re-render
    tasks_11 = tasks_10 + [{"id": "11", "title": "Task 11",
                            "status": "pending", "priority": "low"}]
    with patch("render_kanban.fetch_tasks", return_value=tasks_11):
        render_all(projects_yaml=yaml_path,
                   global_out=tmp_path / "g.md",
                   write_pipeline_log=False)
    content2 = (project / "kanban_board.md").read_text()
    assert _task_entry_count(content2) == 11
