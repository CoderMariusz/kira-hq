from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from kira_hq import doctor
from kira_hq.hermes_bridge import BridgeRequest, _load_bridge_secret

pytestmark = pytest.mark.smoke


def test_doctor_report_includes_telegram_readiness_checks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tasks_file = tmp_path / ".taskmaster" / "tasks" / "tasks.json"
    state_file = tmp_path / ".taskmaster" / "state.json"
    tasks_file.parent.mkdir(parents=True)
    tasks_file.write_text("{}\n", encoding="utf-8")
    state_file.write_text('{"currentTag": "master"}\n', encoding="utf-8")

    monkeypatch.setattr(doctor, "resolve_paths", lambda root: SimpleNamespace(tasks_file=tasks_file, state_file=state_file))
    monkeypatch.setattr(doctor, "current_tag", lambda paths: "master")
    monkeypatch.setattr(doctor, "_run", lambda command, cwd=None: SimpleNamespace(returncode=0, stdout="ok", stderr=""))
    seen: dict[str, object] = {}

    def fake_load_secrets(project_name=None, *, global_env=None, projects_root=None, check_perms=True):
        seen["project_name"] = project_name
        seen["projects_root"] = str(projects_root)
        seen["check_perms"] = check_perms
        return {
            "TELEGRAM_BOT_TOKEN": "secret",
            "TELEGRAM_ALLOWED_CHATS": "111",
            "OPENROUTER_API_KEY": "from-secret-file",
        }

    monkeypatch.setattr(doctor, "load_secrets", fake_load_secrets)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(
        doctor.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="1\n", stderr=""),
    )

    report = doctor.doctor_report(tmp_path)
    checks = {check["name"]: check for check in report["checks"]}

    assert report["ok"] is True
    assert checks["openrouter_key"]["ok"] is True
    assert checks["telegram_bot_token"]["ok"] is True
    assert checks["telegram_paired_chat"]["ok"] is True
    assert checks["telegram_inbox_dir"]["ok"] is True
    assert checks["telegram_outbox_dir"]["ok"] is True
    assert checks["telegram_offset_parent"]["ok"] is True
    assert seen["project_name"] == tmp_path.name
    assert seen["projects_root"] == str(tmp_path.parent)
    assert seen["check_perms"] is True


def test_bridge_secret_loader_uses_project_scoped_secret_before_failing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}

    def fake_load_secrets(project_name=None, *, global_env=None, projects_root=None, check_perms=True):
        seen["project_name"] = project_name
        seen["projects_root"] = str(projects_root)
        seen["check_perms"] = check_perms
        return {"OPENROUTER_API_KEY": "from-secret-file"}

    monkeypatch.setattr("kira_hq.hermes_bridge.load_secrets", fake_load_secrets)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    request = BridgeRequest(
        task_id="36",
        prompt="run worker",
        project_dir=tmp_path / "repo",
        handoff_out=tmp_path / "handoff.json",
    )
    request.project_dir.mkdir()

    assert _load_bridge_secret(request, "OPENROUTER_API_KEY") == "from-secret-file"
    assert seen["project_name"] == "repo"
    assert seen["projects_root"] == str(tmp_path)
    assert seen["check_perms"] is True


def test_bridge_secret_loader_treats_empty_env_as_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("kira_hq.hermes_bridge.load_secrets", lambda *args, **kwargs: {"OPENROUTER_API_KEY": "from-secret-file"})
    monkeypatch.setenv("OPENROUTER_API_KEY", "")

    request = BridgeRequest(
        task_id="36",
        prompt="run worker",
        project_dir=tmp_path / "repo",
        handoff_out=tmp_path / "handoff.json",
    )
    request.project_dir.mkdir()

    assert _load_bridge_secret(request, "OPENROUTER_API_KEY") == ""
