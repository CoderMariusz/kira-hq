from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

import pytest

from kira_hq.cli import main as cli_main
from kira_hq.hermes_bridge import BridgeError, BridgeRequest, invoke_bridge, sanitized_env


pytestmark = pytest.mark.integration


def _seed_project(project_dir: Path) -> None:
    (project_dir / ".taskmaster" / "tasks").mkdir(parents=True)
    (project_dir / ".taskmaster" / "tasks" / "tasks.json").write_text(
        json.dumps(
            {
                "master": {
                    "tasks": [
                        {
                            "id": "36",
                            "title": "Bridge validation",
                            "description": "fixture",
                            "priority": "high",
                            "status": "pending",
                            "dependencies": [],
                            "subtasks": [],
                        }
                    ]
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (project_dir / ".taskmaster" / "state.json").write_text('{"currentTag": "master"}\n', encoding="utf-8")


def _write_fake_hermes(script_path: Path) -> None:
    script_path.write_text(
        textwrap.dedent(
            """#!/usr/bin/env python3
import json
import sys
payload = {
  "task_id": "36",
  "step": 1,
  "worker": "hermes-qwen-worker",
  "worktree": sys.argv[sys.argv.index('-q') + 1].split('worktree=')[1].split('. lane=')[0],
  "lane": "claude-hermes-qwen",
  "files": [{"path": "src/example.py", "intent": "implement delegated change"}],
  "tests": ["pytest tests/integration/test_claude_hermes_bridge.py -q"],
  "risks": ["bounded fixture"],
  "artifacts": [".hermes/artifacts/36/result.txt"],
  "next": "controller review",
  "status": "completed"
}
print(json.dumps(payload))
"""
        ),
        encoding="utf-8",
    )
    script_path.chmod(0o755)


def test_bridge_reuses_hermes_route_and_logs_to_shared_substrate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    _seed_project(project_dir)

    fake_hermes = tmp_path / "fake-hermes"
    _write_fake_hermes(fake_hermes)

    handoff_out = project_dir / ".hermes" / "artifacts" / "36" / "handoff.json"
    fixture_global_log = tmp_path / "global-pipeline.log.md"

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("CLAUDECODE", "1")
    env = sanitized_env()
    assert "CLAUDECODE" not in env
    assert env["OPENROUTER_API_KEY"] == "test-key"

    result = invoke_bridge(
        BridgeRequest(
            task_id="36",
            prompt="Implement the delegated fixture change",
            project_dir=project_dir,
            handoff_out=handoff_out,
            worker_command=str(fake_hermes),
            global_pipeline_log=fixture_global_log,
            log_to_default_global=False,
        )
    )

    assert result.command[0] == str(fake_hermes)
    assert "openrouter" in result.command
    assert "qwen/qwen3-coder-30b-a3b-instruct" in result.command
    assert handoff_out.exists()
    handoff = json.loads(handoff_out.read_text(encoding="utf-8"))
    assert handoff["task_id"] == "36"
    assert handoff["worker"] == "hermes-qwen-worker"
    assert handoff["lane"] == "claude-hermes-qwen"

    project_log = (project_dir / "pipeline.log.md").read_text(encoding="utf-8")
    assert "kira-hq-hermes-worker" in project_log
    assert "qwen3-coder" in project_log
    assert str(handoff_out) in project_log

    global_log = fixture_global_log.read_text(encoding="utf-8")
    assert "kira-hq-hermes-worker" in global_log
    assert "qwen3-coder" in global_log


def test_cli_task_mutation_and_delegate_worker_form_one_bounded_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    _seed_project(project_dir)

    assert cli_main.main(["list-tasks", "--project-dir", str(project_dir), "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["tasks"][0]["id"] == "36"

    assert cli_main.main(["set-status", "36", "in-progress", "--project-dir", str(project_dir), "--json"]) == 0
    updated = json.loads(capsys.readouterr().out)
    assert updated["task"]["status"] == "in-progress"

    fake_hermes = tmp_path / "fake-hermes"
    _write_fake_hermes(fake_hermes)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    handoff_out = project_dir / ".hermes" / "artifacts" / "36" / "handoff.json"
    fixture_global_log = tmp_path / "global-pipeline.log.md"
    assert (
        cli_main.main(
            [
                "delegate-worker",
                "--task-id",
                "36",
                "--prompt",
                "Do the bounded delegated step",
                "--project-dir",
                str(project_dir),
                "--handoff-out",
                str(handoff_out),
                "--worker-command",
                str(fake_hermes),
                "--global-pipeline-log",
                str(fixture_global_log),
                "--json",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["handoff"]["task_id"] == "36"
    assert handoff_out.exists()


def test_bridge_fails_loudly_when_openrouter_key_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    _seed_project(project_dir)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("kira_hq.hermes_bridge.load_secrets", lambda *args, **kwargs: {})

    with pytest.raises(BridgeError, match="OPENROUTER_API_KEY"):
        invoke_bridge(
            BridgeRequest(
                task_id="36",
                prompt="Should fail before worker invocation",
                project_dir=project_dir,
                handoff_out=project_dir / "handoff.json",
                worker_command="/does/not/matter",
                log_to_default_global=False,
            )
        )


def test_delegate_worker_cli_negative_path_reports_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    _seed_project(project_dir)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr("kira_hq.hermes_bridge.load_secrets", lambda *args, **kwargs: {})

    exit_code = cli_main.main(
        [
            "delegate-worker",
            "--task-id",
            "36",
            "--prompt",
            "fail loudly",
            "--project-dir",
            str(project_dir),
            "--handoff-out",
            str(project_dir / "handoff.json"),
            "--worker-command",
            "/missing/hermes",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "OPENROUTER_API_KEY" in captured.err


def test_delegate_worker_cli_reports_missing_worker_binary_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    project_dir = tmp_path / "repo"
    project_dir.mkdir()
    _seed_project(project_dir)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    exit_code = cli_main.main(
        [
            "delegate-worker",
            "--task-id",
            "36",
            "--prompt",
            "fail on missing worker",
            "--project-dir",
            str(project_dir),
            "--handoff-out",
            str(project_dir / "handoff.json"),
            "--worker-command",
            "/missing/hermes",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Hermes worker command not found" in captured.err


def test_delegate_worker_cli_rejects_non_directory_project_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    project_file = tmp_path / "not-a-dir.txt"
    project_file.write_text("x", encoding="utf-8")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    exit_code = cli_main.main(
        [
            "delegate-worker",
            "--task-id",
            "36",
            "--prompt",
            "fail on invalid project dir",
            "--project-dir",
            str(project_file),
            "--handoff-out",
            str(tmp_path / "handoff.json"),
            "--worker-command",
            "/missing/hermes",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "project_dir is not a directory" in captured.err
