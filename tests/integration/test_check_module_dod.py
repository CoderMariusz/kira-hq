"""Integration tests for check_module_dod.py — PRD §6.17."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import check_module_dod

pytestmark = pytest.mark.integration


class StubCompletedProcess:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _write_tasks_json(path: Path, statuses: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tasks = [
        {"id": task_id, "title": f"Task {task_id}", "status": status}
        for task_id, status in statuses.items()
    ]
    path.write_text(json.dumps({"master": {"tasks": tasks}}))


def _write_pipeline_log(path: Path, timestamp: datetime) -> None:
    path.write_text(
        "\n".join(
            [
                "| timestamp | project | skill | provider | expand_used | tokens_in | tokens_out | status | duration_s | notes |",
                "|-----------|---------|-------|----------|-------------|-----------|------------|--------|------------|-------|",
                f"| {timestamp.replace(microsecond=0).isoformat()} | kira-hq | smoke | sonnet | false | 0 | 0 | ok | 0.1 | recent |",
            ]
        )
        + "\n"
    )


def test_module_checker_reports_done_only_when_all_criteria_pass(tmp_path, monkeypatch, capsys):
    tasks_path = tmp_path / ".taskmaster" / "tasks" / "tasks.json"
    _write_tasks_json(tasks_path, {"8": "done"})

    readme_path = tmp_path / "README.md"
    readme_path.write_text("# README\n\ninputs outputs error modes\n")

    pipeline_log = tmp_path / "pipeline.log.md"
    now = datetime(2026, 4, 20, 20, 0, tzinfo=timezone.utc)
    _write_pipeline_log(pipeline_log, now - timedelta(hours=2))

    commands = {
        tuple(check_module_dod.MODULE_SPECS["module-1"].smoke_command): StubCompletedProcess(0, "smoke ok"),
        tuple(check_module_dod.MODULE_SPECS["module-1"].integration_command): StubCompletedProcess(0, "integration ok"),
        tuple(check_module_dod.MODULE_SPECS["module-1"].e2e_command): StubCompletedProcess(0, "e2e ok"),
    }

    def fake_run(command, *, cwd, capture_output, text):
        result = commands.get(tuple(command))
        if result is None:
            raise AssertionError(f"unexpected command: {command}")
        return result

    monkeypatch.setattr(check_module_dod, "_utcnow", lambda: now)
    monkeypatch.setattr(check_module_dod.subprocess, "run", fake_run)

    exit_code = check_module_dod.main(
        [
            "module-1",
            "--repo-root",
            str(tmp_path),
            "--tasks-path",
            str(tasks_path),
            "--pipeline-log",
            str(pipeline_log),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "\n".join(
        [
            "MODULE module-1: done",
            "[PASS] features_implemented",
            "[PASS] smoke_pass",
            "[PASS] integration_pass",
            "[PASS] e2e_pass",
            "[PASS] readme_present",
            "[PASS] pipeline_log_fresh",
            "FINAL: done",
        ]
    ) + "\n"


def test_module_checker_refuses_partial_done_and_prints_failures(tmp_path, monkeypatch, capsys):
    tasks_path = tmp_path / ".taskmaster" / "tasks" / "tasks.json"
    _write_tasks_json(tasks_path, {"16": "done", "17": "pending"})

    readme_path = tmp_path / "docs" / "MODULE_2_API.md"
    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text("# Module 2\n")

    pipeline_log = tmp_path / "pipeline.log.md"
    now = datetime(2026, 4, 20, 20, 0, tzinfo=timezone.utc)
    _write_pipeline_log(pipeline_log, now - timedelta(days=2))

    commands = {
        tuple(check_module_dod.MODULE_SPECS["module-2"].smoke_command): StubCompletedProcess(0, "smoke ok"),
        tuple(check_module_dod.MODULE_SPECS["module-2"].integration_command): StubCompletedProcess(1, "", "integration failed"),
        tuple(check_module_dod.MODULE_SPECS["module-2"].e2e_command): StubCompletedProcess(0, "e2e ok"),
    }

    def fake_run(command, *, cwd, capture_output, text):
        result = commands.get(tuple(command))
        if result is None:
            raise AssertionError(f"unexpected command: {command}")
        return result

    monkeypatch.setattr(check_module_dod, "_utcnow", lambda: now)
    monkeypatch.setattr(check_module_dod.subprocess, "run", fake_run)

    exit_code = check_module_dod.main(
        [
            "module-2",
            "--repo-root",
            str(tmp_path),
            "--tasks-path",
            str(tasks_path),
            "--pipeline-log",
            str(pipeline_log),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == "\n".join(
        [
            "MODULE module-2: in-progress",
            "[FAIL] features_implemented",
            "[PASS] smoke_pass",
            "[FAIL] integration_pass",
            "[PASS] e2e_pass",
            "[PASS] readme_present",
            "[FAIL] pipeline_log_fresh",
            "FINAL: in-progress",
            "REASON: no partial-done",
        ]
    ) + "\n"
    assert captured.err == ""
