from __future__ import annotations

import json
from pathlib import Path

import pytest

from kira_hq.cli import main as cli_main


pytestmark = pytest.mark.smoke


def _seed_task_store(project_dir: Path) -> None:
    (project_dir / ".taskmaster" / "tasks").mkdir(parents=True)
    (project_dir / ".taskmaster" / "tasks" / "tasks.json").write_text(
        json.dumps(
            {
                "master": {
                    "tasks": [
                        {
                            "id": "1",
                            "title": "Existing",
                            "description": "",
                            "priority": "medium",
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


def test_dispatcher_shows_help_for_root_command(capsys):
    exit_code = cli_main.main(["--help"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "add-project" in captured.out
    assert "archive-project" in captured.out
    assert "list-tasks" in captured.out
    assert "add-task" in captured.out
    assert "set-status" in captured.out
    assert "doctor" in captured.out
    assert "delegate-worker" in captured.out
    assert "telegram-serve" in captured.out


def test_dispatcher_invokes_add_project_help(capsys):
    exit_code = cli_main.main(["add-project", "--help"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "project root" in captured.out


def test_dispatcher_uses_sys_argv_when_invoked_as_console_script(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["kira-hq", "add-project", "--help"])

    exit_code = cli_main.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "project root" in captured.out


def test_shared_task_commands_mutate_same_store(tmp_path: Path, capsys):
    _seed_task_store(tmp_path)

    assert cli_main.main(["list-tasks", "--project-dir", str(tmp_path), "--json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed["tag"] == "master"
    assert len(listed["tasks"]) == 1

    assert (
        cli_main.main(
            [
                "add-task",
                "New task",
                "--description",
                "via cli",
                "--project-dir",
                str(tmp_path),
                "--json",
            ]
        )
        == 0
    )
    added = json.loads(capsys.readouterr().out)
    assert added["task"]["id"] == "2"

    assert cli_main.main(["set-status", "2", "done", "--project-dir", str(tmp_path), "--json"]) == 0
    updated = json.loads(capsys.readouterr().out)
    assert updated["task"]["status"] == "done"

    task_doc = json.loads((tmp_path / ".taskmaster" / "tasks" / "tasks.json").read_text(encoding="utf-8"))
    tasks = task_doc["master"]["tasks"]
    assert [task["id"] for task in tasks] == ["1", "2"]
    assert tasks[1]["status"] == "done"


def test_telegram_serve_cli_runs_single_iteration(monkeypatch, tmp_path: Path):
    calls: dict[str, object] = {}

    class FakeBridge:
        def __init__(self, config, *, telegram_client, project_dir=None):
            calls["config"] = config
            calls["telegram_client"] = telegram_client
            calls["project_dir"] = project_dir

        def serve_forever(self, *, max_iterations=None, drain_outbox_first=True):
            calls["max_iterations"] = max_iterations
            calls["drain_outbox_first"] = drain_outbox_first

    class FakeConfig:
        bot_token = "secret-token"

    fake_config = FakeConfig()
    fake_client = object()

    def fake_from_sources(**kwargs):
        calls["from_sources"] = kwargs
        return fake_config

    def fake_bot_client(token):
        calls["bot_token"] = token
        return fake_client

    monkeypatch.setattr(cli_main.TelegramBridgeConfig, "from_sources", fake_from_sources)
    monkeypatch.setattr(cli_main, "TelegramBotClient", fake_bot_client)
    monkeypatch.setattr(cli_main, "TelegramBridge", FakeBridge)

    exit_code = cli_main.main(
        [
            "telegram-serve",
            "--project-dir",
            str(tmp_path / "repo"),
            "--once",
            "--inbox-dir",
            str(tmp_path / "inbox"),
            "--outbox-dir",
            str(tmp_path / "outbox"),
            "--offset-path",
            str(tmp_path / "offset.json"),
            "--poll-timeout",
            "9",
            "--message-max-chars",
            "123",
            "--outbox-ttl-seconds",
            "17",
        ]
    )

    assert exit_code == 0
    assert calls["from_sources"] == {
        "project_dir": (tmp_path / "repo").resolve(),
        "inbox_dir": tmp_path / "inbox",
        "outbox_dir": tmp_path / "outbox",
        "offset_path": tmp_path / "offset.json",
        "poll_timeout_s": 9,
        "message_max_chars": 123,
        "outbox_ttl_seconds": 17,
    }
    assert calls["bot_token"] == "secret-token"
    assert calls["config"] is fake_config
    assert calls["telegram_client"] is fake_client
    assert calls["project_dir"] == (tmp_path / "repo").resolve()
    assert calls["max_iterations"] == 1
    assert calls["drain_outbox_first"] is True
