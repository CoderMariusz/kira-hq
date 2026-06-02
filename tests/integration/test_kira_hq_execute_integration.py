"""Integration tests for Task 25 execute wrapper."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
REPO_RUNNER = REPO_ROOT / "scripts" / "kira_hq_execute.py"


def _shared_runner_path(tmp_path: Path) -> Path:
    """Materialize a portable shared-wrapper path for CI and local runs.

    CI does not ship the user's real ~/.kira-hq/skills-shared tree, so these
    integration tests create the expected wrapper layout in a temp HOME and copy
    the thin repo runner there. This keeps the test faithful to the shared-skill
    invocation contract without depending on machine-local state.
    """
    fake_home = tmp_path / "home"
    runner = fake_home / ".kira-hq" / "skills-shared" / "kira-hq-execute" / "run.py"
    runner.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_RUNNER, runner)
    return runner


def _env() -> dict[str, str]:
    env = os.environ.copy()
    parts = [str(SRC)]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    return env


def _write_fake_task_master(path: Path) -> Path:
    script = path / "fake_task_master.py"
    script.write_text(textwrap.dedent(
        """
        #!/usr/bin/env python3
        from __future__ import annotations
        import json
        import os
        import sys
        from pathlib import Path

        cwd = Path.cwd()
        tasks_file = cwd / ".taskmaster" / "tasks" / "tasks.json"
        data = json.loads(tasks_file.read_text())
        tasks = data["master"]["tasks"]
        argv = sys.argv[1:]
        state_path_raw = os.environ.get("TASK_MASTER_STATE_PATH")
        state_path = Path(state_path_raw) if state_path_raw else None
        state = json.loads(state_path.read_text()) if state_path and state_path.exists() else {"calls": []}

        def save() -> None:
            tasks_file.write_text(json.dumps(data, indent=2))

        def record(command: str) -> None:
            if state_path is None:
                return
            state["calls"].append({"command": command, "argv": argv})
            state_path.write_text(json.dumps(state, indent=2))

        if argv[:1] == ["expand"]:
            record("expand")
            task_id = next(arg.split("=", 1)[1] for arg in argv if arg.startswith("--id="))
            parent = next(task for task in tasks if str(task["id"]) == str(task_id))
            existing = parent.setdefault("subtasks", [])
            if existing and os.environ.get("TASK_MASTER_FAIL_ON_REDUNDANT_EXPAND") == "1":
                raise SystemExit("expand should not run when subtasks already exist")
            if not existing:
                existing.extend([
                    {"id": f"{task_id}.1", "title": "placeholder 1", "description": "", "status": "pending"},
                    {"id": f"{task_id}.2", "title": "placeholder 2", "description": "", "status": "pending"},
                ])
            save()
            sys.exit(0)

        if argv[:1] == ["set-status"]:
            record("set-status")
            target_id = next(arg.split("=", 1)[1] for arg in argv if arg.startswith("--id="))
            status = next(arg.split("=", 1)[1] for arg in argv if arg.startswith("--status="))
            for task in tasks:
                if str(task["id"]) == target_id:
                    task["status"] = status
                    save()
                    sys.exit(0)
                for subtask in task.get("subtasks", []):
                    if str(subtask["id"]) == target_id:
                        subtask["status"] = status
                        save()
                        sys.exit(0)
            raise SystemExit(f"unknown task id {target_id}")

        raise SystemExit(f"unsupported command: {argv}")
        """
    ).strip() + "\n")
    script.chmod(0o755)
    return script


def _write_fake_executor(path: Path, *, fail_parent_twice: bool = False) -> Path:
    script = path / "fake_executor.py"
    script.write_text(textwrap.dedent(
        f"""
        #!/usr/bin/env python3
        from __future__ import annotations
        import json
        import os
        from pathlib import Path

        state_path = Path(os.environ["EXECUTOR_STATE_PATH"])
        if state_path.exists():
            state = json.loads(state_path.read_text())
        else:
            state = {{"calls": []}}

        entry = {{
            "target": os.environ["KIRA_HQ_EXECUTE_TARGET_ID"],
            "parent": os.environ["KIRA_HQ_EXECUTE_PARENT_ID"],
            "title": os.environ.get("KIRA_HQ_EXECUTE_TARGET_TITLE", ""),
            "details": os.environ.get("KIRA_HQ_EXECUTE_TARGET_DETAILS", ""),
            "provider": os.environ.get("KIRA_HQ_EXECUTE_PROVIDER", ""),
            "expand_used": os.environ.get("KIRA_HQ_EXECUTE_EXPAND_USED", ""),
        }}
        state["calls"].append(entry)
        state_path.write_text(json.dumps(state, indent=2))

        should_fail = {str(fail_parent_twice)} and entry["target"] == entry["parent"] and len([c for c in state["calls"] if c["target"] == entry["parent"]]) <= 2
        raise SystemExit(7 if should_fail else 0)
        """
    ).strip() + "\n")
    script.chmod(0o755)
    return script


def _write_project(path: Path, *, with_subtasks: bool = False) -> tuple[Path, Path, Path]:
    project = path / "project"
    tasks_dir = project / ".taskmaster" / "tasks"
    tasks_dir.mkdir(parents=True)
    tasks = {
        "master": {
            "tasks": [
                {
                    "id": "25",
                    "title": "Execute wrapper",
                    "description": "parent task details",
                    "status": "pending",
                    **({"subtasks": [
                        {"id": "25.1", "title": "Existing one", "description": "old", "status": "pending"},
                        {"id": "25.2", "title": "Existing two", "description": "old2", "status": "pending"},
                    ]} if with_subtasks else {}),
                }
            ]
        }
    }
    tasks_file = tasks_dir / "tasks.json"
    tasks_file.write_text(json.dumps(tasks, indent=2))
    plan = project / "plan.md"
    plan.write_text(textwrap.dedent(
        """
        # Plan

        - [ ] Step one
          extra detail

        - [ ] Step two
          ```bash
          echo hi
          ```
          final line
        """
    ).strip() + "\n")
    return project, tasks_file, plan


def test_subtask_provider_expands_once_populates_plan_steps_and_logs(tmp_path: Path):
    shared_runner = _shared_runner_path(tmp_path)
    project, tasks_file, plan = _write_project(tmp_path)
    task_master = _write_fake_task_master(tmp_path)
    executor = _write_fake_executor(tmp_path)
    state_path = tmp_path / "executor-state.json"
    global_log = tmp_path / "global-pipeline.log.md"

    env = _env()
    env["EXECUTOR_STATE_PATH"] = str(state_path)
    result = subprocess.run(
        [
            sys.executable,
            str(shared_runner),
            "--task-id",
            "25",
            "--project-dir",
            str(project),
            "--plan-path",
            str(plan),
            "--tasks-file",
            str(tasks_file),
            "--provider",
            "kimi-2.6",
            "--task-master",
            f"{sys.executable} {task_master}",
            "--executor",
            f"{sys.executable} {executor}",
            "--global-pipeline-log",
            str(global_log),
            "--project-name",
            "demo-project",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "subtasks"
    assert payload["expand_used"] is True
    assert payload["executed_ids"] == ["25.1", "25.2"]

    data = json.loads(tasks_file.read_text())
    subtasks = data["master"]["tasks"][0]["subtasks"]
    assert [item["title"] for item in subtasks] == ["Step one", "Step two"]
    assert subtasks[1]["description"] == "Step two\n```bash\necho hi\n```\nfinal line"
    assert all(item["status"] == "done" for item in subtasks)

    calls = json.loads(state_path.read_text())["calls"]
    assert [call["target"] for call in calls] == ["25.1", "25.2"]
    assert calls[1]["details"] == "Step two\n```bash\necho hi\n```\nfinal line"
    assert all(call["expand_used"] == "true" for call in calls)

    project_log = (project / "pipeline.log.md").read_text()
    assert "| demo-project | kira-hq-execute | kimi-2.6 | true |" in project_log
    assert global_log.read_text() == project_log


def test_subtask_provider_with_existing_subtasks_skips_expand(tmp_path: Path):
    shared_runner = _shared_runner_path(tmp_path)
    project, tasks_file, plan = _write_project(tmp_path, with_subtasks=True)
    task_master = _write_fake_task_master(tmp_path)
    executor = _write_fake_executor(tmp_path)
    state_path = tmp_path / "executor-state.json"
    task_master_state_path = tmp_path / "task-master-state.json"
    global_log = tmp_path / "global-pipeline.log.md"

    env = _env()
    env["EXECUTOR_STATE_PATH"] = str(state_path)
    env["TASK_MASTER_STATE_PATH"] = str(task_master_state_path)
    env["TASK_MASTER_FAIL_ON_REDUNDANT_EXPAND"] = "1"
    result = subprocess.run(
        [
            sys.executable,
            str(shared_runner),
            "--task-id",
            "25",
            "--project-dir",
            str(project),
            "--plan-path",
            str(plan),
            "--tasks-file",
            str(tasks_file),
            "--provider",
            "kimi-2.6",
            "--task-master",
            f"{sys.executable} {task_master}",
            "--executor",
            f"{sys.executable} {executor}",
            "--global-pipeline-log",
            str(global_log),
            "--project-name",
            "demo-project",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "subtasks"
    assert payload["expand_used"] is False
    assert payload["executed_ids"] == ["25.1", "25.2"]

    task_master_calls = json.loads(task_master_state_path.read_text())["calls"]
    assert [call["command"] for call in task_master_calls] == [
        "set-status",
        "set-status",
        "set-status",
        "set-status",
        "set-status",
    ]
    assert all(call["command"] != "expand" for call in task_master_calls)

    calls = json.loads(state_path.read_text())["calls"]
    assert [call["target"] for call in calls] == ["25.1", "25.2"]
    assert all(call["expand_used"] == "false" for call in calls)

    project_log = (project / "pipeline.log.md").read_text()
    assert "| demo-project | kira-hq-execute | kimi-2.6 | false |" in project_log
    assert global_log.read_text() == project_log



def test_parent_failure_twice_demotes_third_attempt_to_subtasks(tmp_path: Path):
    shared_runner = _shared_runner_path(tmp_path)
    project, tasks_file, plan = _write_project(tmp_path)
    task_master = _write_fake_task_master(tmp_path)
    executor = _write_fake_executor(tmp_path, fail_parent_twice=True)
    state_path = tmp_path / "executor-state.json"

    env = _env()
    env["EXECUTOR_STATE_PATH"] = str(state_path)
    result = subprocess.run(
        [
            sys.executable,
            str(shared_runner),
            "25",
            "--project-dir",
            str(project),
            "--plan-path",
            str(plan),
            "--tasks-file",
            str(tasks_file),
            "--provider",
            "sonnet-4.6",
            "--task-master",
            f"{sys.executable} {task_master}",
            "--executor",
            f"{sys.executable} {executor}",
            "--global-pipeline-log",
            str(tmp_path / 'global.log.md'),
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "parent"
    assert payload["demoted_after_failures"] is True
    assert payload["executed_ids"] == ["25", "25", "25.1", "25.2"]

    calls = json.loads(state_path.read_text())["calls"]
    assert [call["target"] for call in calls] == ["25", "25", "25.1", "25.2"]
    assert calls[2]["details"] == "Step one\nextra detail"

    data = json.loads(tasks_file.read_text())
    parent = data["master"]["tasks"][0]
    assert parent["status"] == "done"
    assert [subtask["status"] for subtask in parent["subtasks"]] == ["done", "done"]
