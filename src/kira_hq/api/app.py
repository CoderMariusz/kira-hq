"""Kira-HQ FastAPI app — PRD §4 Module 2.

App factory with dependency-injectable seams (`make_app(...)`) so tests can
substitute fake loaders / fake `task-master list --json` runners without
monkey-patching globals or hitting real disk.

Defaults wire up the production loaders against the user's real
`~/.kira-hq/projects.yaml`. Routers always read their dependencies from
`app.state` so a single FastAPI instance never closes over module-level
state — important for parallel test sessions.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from fastapi import FastAPI

from kira_hq.api.auth import make_auth_dependency
from kira_hq.api.routers import metrics, projects, views
from kira_hq.task_store import add_task as shared_add_task

# ---------------------------------------------------------------------------
# Default loaders / runners (real I/O — overridden in tests)
# ---------------------------------------------------------------------------

DEFAULT_PROJECTS_YAML = Path.home() / ".kira-hq" / "projects.yaml"
DEFAULT_GLOBAL_PIPELINE_LOG = Path.home() / ".kira-hq" / "global-pipeline.log.md"
DEFAULT_TOKENS_DIR = Path.home() / ".kira-hq" / "metrics"


def default_projects_yaml_loader() -> Dict[str, Any]:
    """Load v2 projects.yaml as a dict.

    Returns {'version': 2, 'projects': []} if the file is missing so the API
    stays available for fresh installs.
    """
    from kira_hq.projects_yaml import load  # late import (avoids circulars)

    if not DEFAULT_PROJECTS_YAML.exists():
        return {"version": 2, "projects": []}
    doc = load(DEFAULT_PROJECTS_YAML)
    return doc.model_dump()


def _extract_tasks(data: Any) -> List[dict]:
    if isinstance(data, dict):
        for tag in ("master", *list(data.keys())):
            section = data.get(tag)
            if isinstance(section, dict) and isinstance(section.get("tasks"), list):
                return section["tasks"]
        if isinstance(data.get("tasks"), list):
            return data["tasks"]
    if isinstance(data, list):
        return data
    return []


def _discover_task_section(data: Any) -> tuple[str, dict[str, Any]]:
    if not isinstance(data, dict):
        raise ValueError("tasks.json must contain an object at the top level")
    if isinstance(data.get("tasks"), list):
        return "tasks", data
    if isinstance(data.get("master"), dict):
        return "master", data["master"]

    candidates: list[tuple[str, dict[str, Any]]] = []
    for tag, section in data.items():
        if isinstance(section, dict) and isinstance(section.get("tasks"), list):
            candidates.append((str(tag), section))

    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError("tasks.json does not contain a task section")
    raise ValueError("tasks.json contains multiple task sections; refusing to guess")


def default_taskmaster_runner(project_path: Path) -> List[dict]:
    """Run `task-master list --json` in <project_path> and return tasks list.

    Uses the env-stripping wrapper (PRD §6.4) inline so this works from any
    shell, not just zsh. Returns [] on any expected failure — the API surface is
    read-mostly and a single broken project must not 500 the whole endpoint.
    """
    if not (Path(project_path) / ".taskmaster").exists():
        return []
    env = {
        k: v
        for k, v in os.environ.items()
        if k
        not in {
            "CLAUDECODE",
            "CLAUDE_CODE_ENTRYPOINT",
            "CLAUDE_CODE_EXECPATH",
            "ANTHROPIC_API_KEY",
        }
    }
    try:
        out = subprocess.run(
            ["task-master", "list", "--json"],
            cwd=str(project_path),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        ).stdout
        return _extract_tasks(json.loads(out))
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        FileNotFoundError,
        json.JSONDecodeError,
    ):
        pass

    tasks_file = Path(project_path) / ".taskmaster" / "tasks" / "tasks.json"
    if tasks_file.exists():
        try:
            return _extract_tasks(json.loads(tasks_file.read_text()))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def default_taskmaster_add_task(
    project_path: Path,
    *,
    title: str,
    description: str,
    priority: str,
    parent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a task through the shared local task-store writer."""
    mutation = shared_add_task(
        project_path,
        title=title,
        description=description,
        priority=priority,
        dependencies=[parent_id] if parent_id else [],
    )
    return mutation.task


def default_pipeline_log_loader() -> Path:
    return DEFAULT_GLOBAL_PIPELINE_LOG


def default_tokens_dir_loader() -> Path:
    return DEFAULT_TOKENS_DIR


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def make_app(
    *,
    projects_loader: Optional[Callable[[], Dict[str, Any]]] = None,
    projects_yaml_path: Optional[Path] = None,
    taskmaster_runner: Optional[Callable[[Path], List[dict]]] = None,
    taskmaster_add_task: Optional[Callable[..., Dict[str, Any]]] = None,
    pipeline_log_loader: Optional[Callable[[], Path]] = None,
    tokens_dir_loader: Optional[Callable[[], Path]] = None,
    needs_attention_compute: Optional[Callable[..., Any]] = None,
    auth_secrets_loader: Optional[Callable[[], Dict[str, str]]] = None,
    auth_exposed_probe: Optional[Callable[[], bool]] = None,
) -> FastAPI:
    """Build a FastAPI app with injectable dependencies.

    All seams default to the production loaders. Tests pass fakes to avoid
    real disk / subprocess.

    Auth (T-17): `/health` stays open (liveness probe). All business
    endpoints go behind `make_auth_dependency`, which no-ops unless
    `KIRA_HQ_EXPOSED=true`.
    """
    app = FastAPI(
        title="Kira-HQ API",
        version="0.2.0",
        description="REST API over project state (PRD §4 Module 2).",
    )
    app.state.projects_loader = projects_loader or default_projects_yaml_loader
    app.state.projects_yaml_path = projects_yaml_path or DEFAULT_PROJECTS_YAML
    app.state.taskmaster_runner = taskmaster_runner or default_taskmaster_runner
    app.state.taskmaster_add_task = taskmaster_add_task or default_taskmaster_add_task
    app.state.pipeline_log_loader = pipeline_log_loader or default_pipeline_log_loader
    app.state.tokens_dir_loader = tokens_dir_loader or default_tokens_dir_loader

    if needs_attention_compute is None:
        from kira_hq.needs_attention import compute as _na_compute

        needs_attention_compute = _na_compute
    app.state.needs_attention_compute = needs_attention_compute

    auth_dep = make_auth_dependency(
        secrets_loader=auth_secrets_loader,
        exposed_probe=auth_exposed_probe,
    )
    app.state.auth_dependency = auth_dep

    from fastapi import Depends

    app.include_router(projects.router, dependencies=[Depends(auth_dep)])
    app.include_router(views.router, dependencies=[Depends(auth_dep)])
    app.include_router(metrics.router, dependencies=[Depends(auth_dep)])

    @app.get("/health", tags=["meta"])
    def health() -> Dict[str, str]:
        return {"status": "ok", "service": "kira-hq", "version": app.version}

    return app


app = make_app()
