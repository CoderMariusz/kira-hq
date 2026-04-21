#!/usr/bin/env python3
"""Definition-of-Done checker for Kira-HQ modules — PRD §6.17."""
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ModuleSpec:
    name: str
    feature_task_ids: tuple[str, ...]
    smoke_command: tuple[str, ...]
    integration_command: tuple[str, ...]
    e2e_command: tuple[str, ...]
    readme_path: Path


MODULE_SPECS: dict[str, ModuleSpec] = {
    "module-1": ModuleSpec(
        name="module-1",
        feature_task_ids=("8",),
        smoke_command=("uv", "run", "pytest", "tests/smoke/test_renderer_smoke.py", "-q"),
        integration_command=("uv", "run", "pytest", "tests/integration/test_renderer_multi_project.py", "-q"),
        e2e_command=("uv", "run", "pytest", "tests/e2e/test_kanban_browser.py", "-q", "-m", "e2e"),
        readme_path=Path("README.md"),
    ),
    "module-2": ModuleSpec(
        name="module-2",
        feature_task_ids=("16", "17"),
        smoke_command=("uv", "run", "pytest", "tests/smoke/test_api_endpoints.py", "-q"),
        integration_command=("uv", "run", "pytest", "tests/integration/test_api_real_yaml.py", "-q"),
        e2e_command=("uv", "run", "pytest", "tests/e2e/test_e2e_placeholder.py", "-q", "-m", "e2e"),
        readme_path=Path("docs/MODULE_2_API.md"),
    ),
    "module-3": ModuleSpec(
        name="module-3",
        feature_task_ids=("18", "19"),
        smoke_command=("uv", "run", "pytest", "frontend/app/src/lib/__tests__", "-q"),
        integration_command=("uv", "run", "pytest", "tests/integration/test_frontend_with_mock_api.py", "-q"),
        e2e_command=("uv", "run", "pytest", "tests/e2e/test_e2e_placeholder.py", "-q", "-m", "e2e"),
        readme_path=Path("frontend/app/README.md"),
    ),
    "module-4": ModuleSpec(
        name="module-4",
        feature_task_ids=("20", "21", "22", "24", "25"),
        smoke_command=("uv", "run", "pytest", "tests/smoke/test_report.py", "-q"),
        integration_command=("uv", "run", "pytest", "tests/integration/test_telegram_commands.py", "-q"),
        e2e_command=("uv", "run", "pytest", "tests/integration/test_rollout_end_to_end_integration.py", "-q"),
        readme_path=Path("README.md"),
    ),
}

ALIASES = {
    "1": "module-1",
    "2": "module-2",
    "3": "module-3",
    "4": "module-4",
    **{name: name for name in MODULE_SPECS},
}


@dataclass(frozen=True)
class CriterionResult:
    name: str
    passed: bool


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _load_tasks(tasks_path: Path) -> dict[str, dict]:
    payload = json.loads(tasks_path.read_text())
    tasks = payload.get("master", {}).get("tasks", [])
    return {str(task.get("id")): task for task in tasks}


def _features_implemented(spec: ModuleSpec, tasks_path: Path) -> bool:
    tasks = _load_tasks(tasks_path)
    for task_id in spec.feature_task_ids:
        if tasks.get(task_id, {}).get("status") != "done":
            return False
    return True


def _run_command(command: Iterable[str], repo_root: Path) -> bool:
    completed = subprocess.run(
        list(command),
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def _readme_present(repo_root: Path, spec: ModuleSpec) -> bool:
    return (repo_root / spec.readme_path).exists()


def _parse_timestamp(raw: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _pipeline_log_fresh(pipeline_log: Path, *, now: datetime) -> bool:
    if not pipeline_log.exists():
        return False
    cutoff = now - timedelta(hours=24)
    for raw_line in pipeline_log.read_text().splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or line.startswith("| timestamp") or line.startswith("|---"):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if not cells:
            continue
        parsed = _parse_timestamp(cells[0])
        if parsed is not None and parsed >= cutoff:
            return True
    return False


def evaluate_module(
    module_name: str,
    *,
    repo_root: Path,
    tasks_path: Path,
    pipeline_log: Path,
) -> list[CriterionResult]:
    canonical = ALIASES[module_name]
    spec = MODULE_SPECS[canonical]
    return [
        CriterionResult("features_implemented", _features_implemented(spec, tasks_path)),
        CriterionResult("smoke_pass", _run_command(spec.smoke_command, repo_root)),
        CriterionResult("integration_pass", _run_command(spec.integration_command, repo_root)),
        CriterionResult("e2e_pass", _run_command(spec.e2e_command, repo_root)),
        CriterionResult("readme_present", _readme_present(repo_root, spec)),
        CriterionResult("pipeline_log_fresh", _pipeline_log_fresh(pipeline_log, now=_utcnow())),
    ]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("module", choices=sorted(ALIASES))
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--tasks-path", type=Path, default=Path(".taskmaster/tasks/tasks.json"))
    parser.add_argument("--pipeline-log", type=Path, default=Path("pipeline.log.md"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    tasks_path = args.tasks_path if args.tasks_path.is_absolute() else repo_root / args.tasks_path
    pipeline_log = args.pipeline_log if args.pipeline_log.is_absolute() else repo_root / args.pipeline_log

    canonical = ALIASES[args.module]
    results = evaluate_module(
        canonical,
        repo_root=repo_root,
        tasks_path=tasks_path,
        pipeline_log=pipeline_log,
    )
    all_passed = all(result.passed for result in results)
    status = "done" if all_passed else "in-progress"

    print(f"MODULE {canonical}: {status}")
    for result in results:
        marker = "PASS" if result.passed else "FAIL"
        print(f"[{marker}] {result.name}")
    print(f"FINAL: {status}")
    if not all_passed:
        print("REASON: no partial-done")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
