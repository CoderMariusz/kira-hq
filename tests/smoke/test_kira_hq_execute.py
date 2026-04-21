"""Smoke tests for Task 25 execute wrapper."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "kira_hq_execute.py"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kira_hq.execute_wrapper import classify_provider, plan_steps_from_markdown  # noqa: E402


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return env


def _write_fake_task_master(path: Path) -> Path:
    script = path / "fake_task_master.py"
    script.write_text(textwrap.dedent(
        """
        #!/usr/bin/env python3
        from __future__ import annotations
        import json
        import sys
        from pathlib import Path

        cwd = Path.cwd()
        tasks_file = cwd / ".taskmaster" / "tasks" / "tasks.json"
        data = json.loads(tasks_file.read_text())
        tasks = data["master"]["tasks"]
        argv = sys.argv[1:]

        def save() -> None:
            tasks_file.write_text(json.dumps(data, indent=2))

        if argv[:1] == ["expand"]:
            task_id = next(arg.split("=", 1)[1] for arg in argv if arg.startswith("--id="))
            parent = next(task for task in tasks if str(task["id"]) == str(task_id))
            existing = parent.setdefault("subtasks", [])
            if not existing:
                existing.extend([
                    {"id": f"{task_id}.1", "title": "placeholder 1", "description": "", "status": "pending"},
                    {"id": f"{task_id}.2", "title": "placeholder 2", "description": "", "status": "pending"},
                ])
            save()
            sys.exit(0)

        if argv[:1] == ["set-status"]:
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


def _write_fake_executor(path: Path) -> Path:
    script = path / "fake_executor.py"
    script.write_text(textwrap.dedent(
        """
        #!/usr/bin/env python3
        from __future__ import annotations
        import json
        import os
        from pathlib import Path

        state_path = Path(os.environ["EXECUTOR_STATE_PATH"])
        if state_path.exists():
            state = json.loads(state_path.read_text())
        else:
            state = {"calls": []}

        state["calls"].append(
            {
                "target": os.environ["KIRA_HQ_EXECUTE_TARGET_ID"],
                "parent": os.environ["KIRA_HQ_EXECUTE_PARENT_ID"],
                "title": os.environ["KIRA_HQ_EXECUTE_TARGET_TITLE"],
                "details": os.environ["KIRA_HQ_EXECUTE_TARGET_DETAILS"],
                "expand_used": os.environ["KIRA_HQ_EXECUTE_EXPAND_USED"],
            }
        )
        state_path.write_text(json.dumps(state, indent=2))
        raise SystemExit(0)
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


def test_classify_provider_routes_parent_and_subtask_models():
    assert classify_provider("opus") == "parent"
    assert classify_provider("sonnet-4.6") == "parent"
    assert classify_provider("haiku-4.5") == "parent"
    assert classify_provider("kimi-2.6") == "subtasks"
    assert classify_provider("sonnet-4.5") == "subtasks"
    assert classify_provider("openrouter-fallback") == "subtasks"
    assert classify_provider("some-unknown-provider") == "subtasks"


def test_plan_steps_preserve_fenced_code_blocks_within_checkbox_step():
    plan = """
# Plan

- [ ] First step
  Continue the explanation.

- [ ] Add migration
  ```python
  print('hello')
  ```
  Final note.

- [x] done already
""".strip()

    steps = plan_steps_from_markdown(plan)

    assert steps == [
        "First step\nContinue the explanation.",
        "Add migration\n```python\nprint('hello')\n```\nFinal note.",
    ]


def test_script_runs_directly_from_repo_root_for_parent_path(tmp_path: Path):
    project, tasks_file, plan = _write_project(tmp_path)
    task_master = _write_fake_task_master(tmp_path)
    executor = _write_fake_executor(tmp_path)
    state_path = tmp_path / "executor-state.json"

    env = _env()
    env["EXECUTOR_STATE_PATH"] = str(state_path)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "25",
            "--project-dir",
            str(project),
            "--plan-path",
            str(plan),
            "--tasks-file",
            str(tasks_file),
            "--provider",
            "opus",
            "--task-master",
            f"{sys.executable} {task_master}",
            "--executor",
            f"{sys.executable} {executor}",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "parent"
    assert payload["expand_used"] is False
    assert payload["executed_ids"] == ["25"]

    calls = json.loads(state_path.read_text())["calls"]
    assert calls == [
        {
            "target": "25",
            "parent": "25",
            "title": "Execute wrapper",
            "details": "parent task details",
            "expand_used": "false",
        }
    ]


def test_script_runs_directly_from_repo_root_for_subtask_path(tmp_path: Path):
    project, tasks_file, plan = _write_project(tmp_path, with_subtasks=True)
    task_master = _write_fake_task_master(tmp_path)
    executor = _write_fake_executor(tmp_path)
    state_path = tmp_path / "executor-state.json"

    env = _env()
    env["EXECUTOR_STATE_PATH"] = str(state_path)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
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
        ],
        cwd=REPO_ROOT,
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

    calls = json.loads(state_path.read_text())["calls"]
    assert [call["target"] for call in calls] == ["25.1", "25.2"]
    assert all(call["expand_used"] == "false" for call in calls)
    assert calls[1]["details"] == "Step two\n```bash\necho hi\n```\nfinal line"
