"""Provider-aware Task Master execution wrapper for Task 25."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kira_hq.pipeline_log import append_entry

PARENT_PROVIDERS = {"opus", "sonnet", "sonnet-4.6", "haiku-4.5"}
SUBTASK_PROVIDERS = {"kimi-2.6", "sonnet-4.5", "openrouter-fallback"}
DEFAULT_TASKS_FILE = Path(".taskmaster") / "tasks" / "tasks.json"
DEFAULT_PLAN_PATH = Path("plan.md")
DEFAULT_PIPELINE_LOG = Path("pipeline.log.md")


@dataclass
class TaskTarget:
    id: str
    title: str
    details: str
    status: str = "pending"


def classify_provider(provider: str | None) -> str:
    normalized = (provider or "sonnet").strip().lower()
    if normalized in PARENT_PROVIDERS:
        return "parent"
    if normalized in SUBTASK_PROVIDERS:
        return "subtasks"
    return "subtasks"


def plan_steps_from_markdown(markdown: str) -> list[str]:
    steps: list[str] = []
    current_title: str | None = None
    current_lines: list[str] = []
    in_fence = False

    for raw_line in markdown.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence

        if not in_fence and stripped.startswith("- [") and len(stripped) >= 5 and stripped[3] in " xX":
            if current_title is not None:
                steps.append(_render_step(current_title, current_lines))
            marker_end = stripped.find("]")
            current_title = stripped[marker_end + 1 :].strip()
            current_lines = []
            if stripped[3] in "xX":
                current_title = None
                current_lines = []
            continue

        if current_title is None:
            continue

        if not stripped and not in_fence:
            if current_lines and current_lines[-1] != "":
                current_lines.append("")
            continue

        current_lines.append(stripped)

    if current_title is not None:
        steps.append(_render_step(current_title, current_lines))
    return steps


def _render_step(title: str, body_lines: list[str]) -> str:
    while body_lines and body_lines[-1] == "":
        body_lines.pop()
    if not body_lines:
        return title
    return title + "\n" + "\n".join(body_lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provider-aware Task Master execution wrapper")
    parser.add_argument("task_id", nargs="?", help="Task ID to execute")
    parser.add_argument("--task-id", dest="task_id_flag", help="Task ID to execute")
    parser.add_argument("--project-dir", default=".")
    parser.add_argument("--plan-path")
    parser.add_argument("--tasks-file")
    parser.add_argument("--provider")
    parser.add_argument("--executor")
    parser.add_argument("--task-master")
    parser.add_argument("--global-pipeline-log")
    parser.add_argument("--project-name")
    return parser.parse_args(argv)


def _resolve_task_id(args: argparse.Namespace) -> str:
    task_id = args.task_id_flag or args.task_id
    if not task_id:
        raise SystemExit("task id required via --task-id or positional arg")
    return str(task_id)


def _provider(args: argparse.Namespace) -> str:
    return (args.provider or os.environ.get("KIRA_HQ_PROVIDER") or "sonnet").strip()


def _task_master_command(args: argparse.Namespace) -> str:
    return args.task_master or os.environ.get("KIRA_HQ_TASK_MASTER") or "task-master"


def _executor_command(args: argparse.Namespace) -> str:
    return args.executor or os.environ.get("KIRA_HQ_EXECUTOR") or sys.executable


def _project_dir(args: argparse.Namespace) -> Path:
    return Path(args.project_dir).expanduser().resolve()


def _tasks_file(args: argparse.Namespace, project_dir: Path) -> Path:
    raw = Path(args.tasks_file) if args.tasks_file else DEFAULT_TASKS_FILE
    return (project_dir / raw).resolve() if not raw.is_absolute() else raw


def _plan_path(args: argparse.Namespace, project_dir: Path) -> Path:
    raw = Path(args.plan_path) if args.plan_path else DEFAULT_PLAN_PATH
    return (project_dir / raw).resolve() if not raw.is_absolute() else raw


def _project_name(args: argparse.Namespace, project_dir: Path) -> str:
    return args.project_name or project_dir.name


def _global_pipeline_log(args: argparse.Namespace) -> Path | None:
    if not args.global_pipeline_log:
        return None
    return Path(args.global_pipeline_log).expanduser().resolve()


def _load_tasks(tasks_file: Path) -> dict[str, Any]:
    return json.loads(tasks_file.read_text())


def _save_tasks(tasks_file: Path, data: dict[str, Any]) -> None:
    tasks_file.write_text(json.dumps(data, indent=2) + "\n")


def _find_parent(data: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in data.get("master", {}).get("tasks", []):
        if str(task.get("id")) == str(task_id):
            return task
    raise KeyError(f"task {task_id} not found")


def _subtasks_from_parent(parent: dict[str, Any]) -> list[dict[str, Any]]:
    subtasks = parent.setdefault("subtasks", [])
    if not isinstance(subtasks, list):
        raise ValueError("parent subtasks must be a list")
    return subtasks


def _run_command(command: str, args: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    cmd = [*shlex.split(command), *args]
    return subprocess.run(cmd, cwd=str(cwd), env=env, text=True, capture_output=True, check=False)


def _set_status(task_master: str, cwd: Path, task_id: str, status: str) -> None:
    result = _run_command(task_master, ["set-status", f"--id={task_id}", f"--status={status}"], cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"set-status failed for {task_id}")


def _expand_if_needed(task_master: str, cwd: Path, task_id: str, parent: dict[str, Any]) -> bool:
    if _subtasks_from_parent(parent):
        return False
    result = _run_command(task_master, ["expand", f"--id={task_id}", "--num=auto"], cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"expand failed for {task_id}")
    return True


def _populate_subtasks_from_plan(tasks_file: Path, task_id: str, plan_path: Path) -> list[TaskTarget]:
    steps = plan_steps_from_markdown(plan_path.read_text())
    if not steps:
        raise ValueError(f"no unchecked checkbox steps found in {plan_path}")
    data = _load_tasks(tasks_file)
    parent = _find_parent(data, task_id)
    subtasks = _subtasks_from_parent(parent)

    if len(subtasks) < len(steps):
        for index in range(len(subtasks) + 1, len(steps) + 1):
            subtasks.append({"id": f"{task_id}.{index}", "title": f"Subtask {index}", "description": "", "status": "pending"})
    elif len(subtasks) > len(steps):
        del subtasks[len(steps) :]

    targets: list[TaskTarget] = []
    for index, step in enumerate(steps, start=1):
        title = step.splitlines()[0].strip()
        subtask = subtasks[index - 1]
        subtask["id"] = str(subtask.get("id") or f"{task_id}.{index}")
        subtask["title"] = title
        subtask["description"] = step
        subtask.setdefault("status", "pending")
        targets.append(TaskTarget(id=str(subtask["id"]), title=title, details=step, status=str(subtask.get("status", "pending"))))

    _save_tasks(tasks_file, data)
    return targets


def _parent_target(tasks_file: Path, task_id: str) -> TaskTarget:
    parent = _find_parent(_load_tasks(tasks_file), task_id)
    return TaskTarget(
        id=str(parent.get("id")),
        title=str(parent.get("title", "")),
        details=str(parent.get("description", "")),
        status=str(parent.get("status", "pending")),
    )


def _update_json_status(tasks_file: Path, task_id: str, status: str) -> None:
    data = _load_tasks(tasks_file)
    for task in data.get("master", {}).get("tasks", []):
        if str(task.get("id")) == task_id:
            task["status"] = status
            _save_tasks(tasks_file, data)
            return
        for subtask in task.get("subtasks", []):
            if str(subtask.get("id")) == task_id:
                subtask["status"] = status
                _save_tasks(tasks_file, data)
                return


def _log_run(project_dir: Path, project_name: str, provider: str, expand_used: bool, status: str, duration_s: float, notes: str, global_log: Path | None) -> None:
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    kwargs = dict(
        timestamp=timestamp,
        project=project_name,
        skill="kira-hq-execute",
        provider=provider,
        expand_used=expand_used,
        tokens_in=0,
        tokens_out=0,
        status=status,
        duration_s=duration_s,
        notes=notes,
    )
    append_entry(project_dir / DEFAULT_PIPELINE_LOG, **kwargs)
    if global_log is not None:
        append_entry(global_log, **kwargs)


def _execute_target(target: TaskTarget, *, parent_id: str, provider: str, expand_used: bool, executor: str, project_dir: Path, task_master: str, tasks_file: Path, project_name: str, global_log: Path | None) -> tuple[bool, int]:
    started = time.monotonic()
    _set_status(task_master, project_dir, target.id, "in-progress")
    _update_json_status(tasks_file, target.id, "in-progress")

    env = os.environ.copy()
    env.update(
        {
            "KIRA_HQ_EXECUTE_TARGET_ID": target.id,
            "KIRA_HQ_EXECUTE_PARENT_ID": parent_id,
            "KIRA_HQ_EXECUTE_TARGET_TITLE": target.title,
            "KIRA_HQ_EXECUTE_TARGET_DETAILS": target.details,
            "KIRA_HQ_EXECUTE_PROVIDER": provider,
            "KIRA_HQ_EXECUTE_EXPAND_USED": "true" if expand_used else "false",
        }
    )
    result = _run_command(executor, [], cwd=project_dir, env=env)
    duration = round(time.monotonic() - started, 3)

    if result.returncode == 0:
        _set_status(task_master, project_dir, target.id, "done")
        _update_json_status(tasks_file, target.id, "done")
        _log_run(project_dir, project_name, provider, expand_used, "ok", duration, f"executed {target.id}", global_log)
        return True, 0

    _set_status(task_master, project_dir, target.id, "pending")
    _update_json_status(tasks_file, target.id, "pending")
    notes = result.stderr.strip() or result.stdout.strip() or f"executor failed for {target.id}"
    _log_run(project_dir, project_name, provider, expand_used, "fail", duration, notes, global_log)
    return False, result.returncode


def _execute_subtasks(task_id: str, *, provider: str, executor: str, project_dir: Path, plan_path: Path, tasks_file: Path, task_master: str, project_name: str, global_log: Path | None) -> tuple[list[str], bool]:
    data = _load_tasks(tasks_file)
    parent = _find_parent(data, task_id)
    expand_used = _expand_if_needed(task_master, project_dir, task_id, parent)
    targets = _populate_subtasks_from_plan(tasks_file, task_id, plan_path)
    executed: list[str] = []
    for target in targets:
        ok, code = _execute_target(target, parent_id=task_id, provider=provider, expand_used=expand_used, executor=executor, project_dir=project_dir, task_master=task_master, tasks_file=tasks_file, project_name=project_name, global_log=global_log)
        executed.append(target.id)
        if not ok:
            raise SystemExit(code)
    _set_status(task_master, project_dir, task_id, "done")
    _update_json_status(tasks_file, task_id, "done")
    return executed, expand_used


def run(argv: list[str] | None = None) -> dict[str, Any]:
    args = _parse_args(argv)
    project_dir = _project_dir(args)
    task_id = _resolve_task_id(args)
    provider = _provider(args)
    mode = classify_provider(provider)
    task_master = _task_master_command(args)
    executor = _executor_command(args)
    tasks_file = _tasks_file(args, project_dir)
    plan_path = _plan_path(args, project_dir)
    project_name = _project_name(args, project_dir)
    global_log = _global_pipeline_log(args)

    if mode == "subtasks":
        executed_ids, expand_used = _execute_subtasks(task_id, provider=provider, executor=executor, project_dir=project_dir, plan_path=plan_path, tasks_file=tasks_file, task_master=task_master, project_name=project_name, global_log=global_log)
        return {"task_id": task_id, "provider": provider, "mode": mode, "expand_used": expand_used, "executed_ids": executed_ids, "demoted_after_failures": False}

    parent = _parent_target(tasks_file, task_id)
    executed_ids: list[str] = []
    for attempt in range(1, 3):
        ok, _code = _execute_target(parent, parent_id=task_id, provider=provider, expand_used=False, executor=executor, project_dir=project_dir, task_master=task_master, tasks_file=tasks_file, project_name=project_name, global_log=global_log)
        executed_ids.append(task_id)
        if ok:
            return {"task_id": task_id, "provider": provider, "mode": mode, "expand_used": False, "executed_ids": executed_ids, "demoted_after_failures": False}

    subtask_ids, expand_used = _execute_subtasks(task_id, provider=provider, executor=executor, project_dir=project_dir, plan_path=plan_path, tasks_file=tasks_file, task_master=task_master, project_name=project_name, global_log=global_log)
    executed_ids.extend(subtask_ids)
    return {"task_id": task_id, "provider": provider, "mode": mode, "expand_used": expand_used, "executed_ids": executed_ids, "demoted_after_failures": True}


def main(argv: list[str] | None = None) -> int:
    payload = run(argv)
    sys.stdout.write(json.dumps(payload) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
