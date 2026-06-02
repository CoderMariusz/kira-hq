"""Shared task-store substrate helpers for Claude/Hermes/Kira-HQ.

These helpers centralize all local task mutations so the repo has one write path
for `.taskmaster/tasks/tasks.json` and `.taskmaster/state.json`.
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

DEFAULT_TASKS_FILE = Path(".taskmaster") / "tasks" / "tasks.json"
DEFAULT_STATE_FILE = Path(".taskmaster") / "state.json"
VALID_STATUSES = {
    "pending",
    "in-progress",
    "done",
    "blocked",
    "needs-human",
    "review",
    "cancelled",
}


@dataclass(frozen=True)
class TaskStorePaths:
    project_dir: Path
    tasks_file: Path
    state_file: Path


@dataclass(frozen=True)
class TaskMutationResult:
    tag: str
    task: dict[str, Any]


class TaskStoreError(RuntimeError):
    """Base exception for task store operations."""


class TaskNotFoundError(TaskStoreError):
    pass


class TaskValidationError(TaskStoreError):
    pass


class TaskTagError(TaskStoreError):
    pass


def resolve_paths(
    project_dir: str | Path = ".",
    *,
    tasks_file: str | Path | None = None,
    state_file: str | Path | None = None,
) -> TaskStorePaths:
    root = Path(project_dir).expanduser().resolve()
    raw_tasks = Path(tasks_file) if tasks_file is not None else DEFAULT_TASKS_FILE
    raw_state = Path(state_file) if state_file is not None else DEFAULT_STATE_FILE
    return TaskStorePaths(
        project_dir=root,
        tasks_file=(root / raw_tasks).resolve() if not raw_tasks.is_absolute() else raw_tasks,
        state_file=(root / raw_state).resolve() if not raw_state.is_absolute() else raw_state,
    )


@contextmanager
def _locked_file(target: Path) -> Iterator[None]:
    lock_path = target.with_suffix(target.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f"{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as tmp_file:
        json.dump(payload, tmp_file, indent=2)
        tmp_file.write("\n")
        tmp_file.flush()
        os.fsync(tmp_file.fileno())
        tmp_name = tmp_file.name
    Path(tmp_name).replace(path)


def load_state(paths: TaskStorePaths) -> dict[str, Any]:
    if not paths.state_file.exists():
        return {"currentTag": "master"}
    data = _read_json(paths.state_file)
    if not isinstance(data, dict):
        raise TaskValidationError("state.json must contain an object")
    return data


def current_tag(paths: TaskStorePaths) -> str:
    state = load_state(paths)
    tag = str(state.get("currentTag") or "master").strip()
    if not tag:
        raise TaskTagError("state.json currentTag is empty")
    return tag


def load_tasks_document(paths: TaskStorePaths) -> dict[str, Any]:
    if not paths.tasks_file.exists():
        raise FileNotFoundError(f"task store missing: {paths.tasks_file}")
    data = _read_json(paths.tasks_file)
    if not isinstance(data, dict):
        raise TaskValidationError("tasks.json must contain an object")
    return data


def _resolve_section(data: dict[str, Any], *, preferred_tag: str) -> tuple[str, dict[str, Any]]:
    if preferred_tag in data and isinstance(data.get(preferred_tag), dict):
        section = data[preferred_tag]
        if isinstance(section.get("tasks"), list):
            return preferred_tag, section
        raise TaskValidationError(f"tag {preferred_tag!r} exists but does not contain a task list")
    if isinstance(data.get("tasks"), list):
        return "tasks", data
    candidates = [
        (str(tag), section)
        for tag, section in data.items()
        if isinstance(section, dict) and isinstance(section.get("tasks"), list)
    ]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise TaskValidationError("tasks.json does not contain any task section")
    raise TaskTagError(
        f"currentTag={preferred_tag!r} missing and multiple task sections exist; refusing to guess"
    )


def list_tasks(
    project_dir: str | Path = ".",
    *,
    tasks_file: str | Path | None = None,
    state_file: str | Path | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    paths = resolve_paths(project_dir, tasks_file=tasks_file, state_file=state_file)
    data = load_tasks_document(paths)
    tag, section = _resolve_section(data, preferred_tag=current_tag(paths))
    tasks = section.get("tasks", [])
    if not isinstance(tasks, list):
        raise TaskValidationError(f"task list under tag {tag!r} is not a list")
    return tag, tasks


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ensure_status(status: str) -> str:
    normalized = status.strip()
    if normalized not in VALID_STATUSES:
        raise TaskValidationError(
            f"invalid status {status!r}; expected one of {sorted(VALID_STATUSES)}"
        )
    return normalized


def _refresh_section_metadata(section: dict[str, Any]) -> None:
    tasks = section.get("tasks", [])
    if not isinstance(tasks, list):
        return
    metadata = section.setdefault("metadata", {})
    if not isinstance(metadata, dict):
        return
    metadata["lastModified"] = _now_iso()
    metadata["taskCount"] = len(tasks)
    metadata["completedCount"] = sum(1 for task in tasks if str(task.get("status")) == "done")


def add_task(
    project_dir: str | Path = ".",
    *,
    title: str,
    description: str = "",
    priority: str = "medium",
    dependencies: list[str] | None = None,
    tasks_file: str | Path | None = None,
    state_file: str | Path | None = None,
) -> TaskMutationResult:
    clean_title = title.strip()
    if not clean_title:
        raise TaskValidationError("title must not be empty")
    clean_priority = priority.strip() or "medium"
    clean_description = description.strip()
    clean_dependencies = [str(item).strip() for item in (dependencies or []) if str(item).strip()]

    paths = resolve_paths(project_dir, tasks_file=tasks_file, state_file=state_file)
    with _locked_file(paths.tasks_file):
        data = load_tasks_document(paths)
        tag, section = _resolve_section(data, preferred_tag=current_tag(paths))
        tasks = section.setdefault("tasks", [])
        if not isinstance(tasks, list):
            raise TaskValidationError(f"tag {tag!r} has non-list tasks")
        existing_ids = {str(task.get("id")) for task in tasks}
        next_id = 1
        while str(next_id) in existing_ids:
            next_id += 1
        task = {
            "id": str(next_id),
            "title": clean_title,
            "description": clean_description,
            "priority": clean_priority,
            "dependencies": clean_dependencies,
            "status": "pending",
            "subtasks": [],
            "updatedAt": _now_iso(),
        }
        tasks.append(task)
        _refresh_section_metadata(section)
        _atomic_write_json(paths.tasks_file, data)
        return TaskMutationResult(tag=tag, task=task)


def set_status(
    project_dir: str | Path = ".",
    *,
    task_id: str,
    status: str,
    tasks_file: str | Path | None = None,
    state_file: str | Path | None = None,
) -> TaskMutationResult:
    wanted = _ensure_status(status)
    wanted_id = str(task_id).strip()
    if not wanted_id:
        raise TaskValidationError("task_id must not be empty")

    paths = resolve_paths(project_dir, tasks_file=tasks_file, state_file=state_file)
    with _locked_file(paths.tasks_file):
        data = load_tasks_document(paths)
        tag, section = _resolve_section(data, preferred_tag=current_tag(paths))
        tasks = section.get("tasks", [])
        if not isinstance(tasks, list):
            raise TaskValidationError(f"tag {tag!r} has non-list tasks")
        for task in tasks:
            if str(task.get("id")) == wanted_id:
                task["status"] = wanted
                task["updatedAt"] = _now_iso()
                _refresh_section_metadata(section)
                _atomic_write_json(paths.tasks_file, data)
                return TaskMutationResult(tag=tag, task=task)
        raise TaskNotFoundError(f"task {wanted_id} not found under tag {tag}")
