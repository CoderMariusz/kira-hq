"""Shared pytest fixtures for Kira-HQ test suite — PRD §6.15.

Fixtures provided:
    fake_project(name="demo", tasks_n=10) → factory returning a tmp project dir
                                             with .taskmaster/tasks.json
    pipeline_log_tmp → (Path, append_row) — tmp pipeline.log.md + helper
    projects_yaml_tmp(entries=1) → factory returning a tmp projects.yaml v2
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

import pytest
import yaml


# ---------------------------------------------------------------------------
# fake_project
# ---------------------------------------------------------------------------

def _make_tasks(n: int) -> dict:
    tasks = []
    for i in range(1, n + 1):
        tasks.append({
            "id": str(i),
            "title": f"Task {i}",
            "description": f"fixture task {i}",
            "priority": ["high", "medium", "low"][i % 3],
            "status": ["pending", "in-progress", "done", "blocked"][i % 4],
            "dependencies": [],
        })
    return {"master": {"tasks": tasks, "metadata": {"tag": "master"}}}


@dataclass
class FakeProject:
    path: Path
    tasks_json: Path
    tasks_n: int


@pytest.fixture
def fake_project(tmp_path) -> Callable[..., FakeProject]:
    """Factory fixture. Call as `fake_project(name, tasks_n)`."""
    created: List[FakeProject] = []

    def _factory(name: str = "demo", tasks_n: int = 10) -> FakeProject:
        root = tmp_path / name
        tm = root / ".taskmaster" / "tasks"
        tm.mkdir(parents=True, exist_ok=True)
        tasks_file = tm / "tasks.json"
        tasks_file.write_text(json.dumps(_make_tasks(tasks_n), indent=2))
        # Minimal prd dir so kira-hq add-project later passes validation
        (root / "prd").mkdir(exist_ok=True)
        (root / "prd" / "master-prd.md").write_text(f"# {name} PRD\n")
        fp = FakeProject(path=root, tasks_json=tasks_file, tasks_n=tasks_n)
        created.append(fp)
        return fp

    return _factory


# ---------------------------------------------------------------------------
# pipeline_log_tmp
# ---------------------------------------------------------------------------

@dataclass
class PipelineLogTmp:
    path: Path
    append: Callable[..., None]


@pytest.fixture
def pipeline_log_tmp(tmp_path) -> PipelineLogTmp:
    """Tmp pipeline log + bound append helper (10-col v2 schema, PRD §6.1)."""
    from kira_hq.pipeline_log import append_entry  # late import (src/ on sys.path via pytest config)

    log_path = tmp_path / "pipeline.log.md"

    def _append(
        *,
        timestamp: str = "2026-04-18T00:00:00",
        project: str = "kira-hq",
        skill: str = "test-skill",
        provider: str = "sonnet",
        expand_used: bool = False,
        tokens_in: int = 0,
        tokens_out: int = 0,
        status: str = "ok",
        duration_s: float = 0.1,
        notes: str = "",
    ) -> None:
        append_entry(
            log_path,
            timestamp=timestamp, project=project, skill=skill,
            provider=provider, expand_used=expand_used,
            tokens_in=tokens_in, tokens_out=tokens_out,
            status=status, duration_s=duration_s, notes=notes,
        )

    return PipelineLogTmp(path=log_path, append=_append)


# ---------------------------------------------------------------------------
# projects_yaml_tmp
# ---------------------------------------------------------------------------

def _mk_entry(name: str, path: str) -> dict:
    return {
        "name": name,
        "path": path,
        "status": "active",
        "priority": "medium",
        "cron": "0 */2 * * *",
        "added_at": "2026-04-18",
        "skills": ["kira-hq-render-kanban"],
        "budget_tokens_monthly": 500_000,
        "budget_tokens_per_run": 50_000,
        "notes": "",
    }


@pytest.fixture
def projects_yaml_tmp(tmp_path) -> Callable[..., Path]:
    """Factory yielding a tmp projects.yaml v2 with N entries."""

    def _factory(entries: int = 1, base: Optional[Path] = None) -> Path:
        base = base or tmp_path
        projs = [_mk_entry(f"proj{i}", str(base / f"proj{i}")) for i in range(entries)]
        doc = {"version": 2, "projects": projs}
        out = base / "projects.yaml"
        out.write_text(yaml.safe_dump(doc, sort_keys=False))
        return out

    return _factory
