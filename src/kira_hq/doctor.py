"""Readiness checks for the Claude-first / Hermes-worker setup."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kira_hq.secrets_schema import load_secrets
from kira_hq.task_store import current_tag, resolve_paths
from kira_hq.telegram.commands import parse_allowed_chats
from kira_hq.telegram.bridge import DEFAULT_INBOX_DIR, DEFAULT_OFFSET_PATH, DEFAULT_OUTBOX_DIR


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )


def collect_doctor_checks(project_dir: str | Path = ".") -> list[CheckResult]:
    root = Path(project_dir).expanduser().resolve()
    paths = resolve_paths(root)
    checks: list[CheckResult] = []

    try:
        tag = current_tag(paths)
        checks.append(CheckResult("current_tag", tag == "master", f"currentTag={tag}"))
    except Exception as exc:
        checks.append(CheckResult("current_tag", False, str(exc)))

    for label, path in {
        "tasks_store": paths.tasks_file,
        "state_store": paths.state_file,
        "projects_registry": Path.home() / ".kira-hq" / "projects.yaml",
        "global_pipeline_log": Path.home() / ".kira-hq" / "global-pipeline.log.md",
    }.items():
        checks.append(CheckResult(label, path.exists(), str(path)))

    skill_check = _run(["python", "scripts/symlink_skills.py", "--check"], cwd=root)
    checks.append(
        CheckResult(
            "shared_skills",
            skill_check.returncode == 0,
            (skill_check.stdout or skill_check.stderr).strip() or "symlink_skills.py --check",
        )
    )

    hermes_probe = _run(["hermes", "chat", "--help"])
    checks.append(
        CheckResult(
            "hermes_cli",
            hermes_probe.returncode == 0,
            "hermes chat available" if hermes_probe.returncode == 0 else (hermes_probe.stderr.strip() or "hermes unavailable"),
        )
    )

    secrets = load_secrets(root.name, projects_root=root.parent)
    openrouter_secret = os.environ["OPENROUTER_API_KEY"] if "OPENROUTER_API_KEY" in os.environ else secrets.get("OPENROUTER_API_KEY")
    checks.append(
        CheckResult(
            "openrouter_key",
            bool(openrouter_secret),
            "OPENROUTER_API_KEY present" if openrouter_secret else "OPENROUTER_API_KEY missing",
        )
    )

    telegram_token = os.environ["TELEGRAM_BOT_TOKEN"] if "TELEGRAM_BOT_TOKEN" in os.environ else secrets.get("TELEGRAM_BOT_TOKEN")
    allowed_raw = (
        os.environ["TELEGRAM_ALLOWED_CHATS"]
        if "TELEGRAM_ALLOWED_CHATS" in os.environ
        else secrets.get("TELEGRAM_ALLOWED_CHATS")
    )
    allowed = parse_allowed_chats(allowed_raw)
    checks.append(
        CheckResult(
            "telegram_bot_token",
            bool(telegram_token),
            "TELEGRAM_BOT_TOKEN present" if telegram_token else "TELEGRAM_BOT_TOKEN missing",
        )
    )
    checks.append(
        CheckResult(
            "telegram_paired_chat",
            len(allowed) == 1,
            f"paired chats configured={len(allowed)}",
        )
    )

    for label, path in {
        "telegram_inbox_dir": DEFAULT_INBOX_DIR,
        "telegram_outbox_dir": DEFAULT_OUTBOX_DIR,
        "telegram_offset_parent": DEFAULT_OFFSET_PATH.parent,
    }.items():
        try:
            path.mkdir(parents=True, exist_ok=True)
            checks.append(CheckResult(label, True, str(path)))
        except OSError as exc:
            checks.append(CheckResult(label, False, str(exc)))

    wrapper_env = os.environ.copy()
    wrapper_env.update(
        {
            "CLAUDECODE": "1",
            "CLAUDE_CODE_ENTRYPOINT": "1",
            "CLAUDE_CODE_EXECPATH": "1",
            "ANTHROPIC_API_KEY": "blocked",
        }
    )
    taskmaster_probe = subprocess.run(
        [sys.executable, "-c", "from kira_hq.task_store import list_tasks; print(len(list_tasks()[1]))"],
        cwd=str(root),
        env=wrapper_env,
        text=True,
        capture_output=True,
        check=False,
    )
    checks.append(
        CheckResult(
            "neutral_cli_read_path",
            taskmaster_probe.returncode == 0,
            (taskmaster_probe.stdout or taskmaster_probe.stderr).strip() or "neutral task read path",
        )
    )

    log_path = Path.home() / ".kira-hq" / "global-pipeline.log.md"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8"):
            pass
        checks.append(CheckResult("global_log_writable", True, str(log_path)))
    except OSError as exc:
        checks.append(CheckResult("global_log_writable", False, str(exc)))

    return checks


def doctor_report(project_dir: str | Path = ".") -> dict[str, Any]:
    checks = collect_doctor_checks(project_dir)
    ok = all(check.ok for check in checks)
    return {
        "ok": ok,
        "project_dir": str(Path(project_dir).expanduser().resolve()),
        "checks": [check.__dict__ for check in checks],
    }


def format_doctor_text(report: dict[str, Any]) -> str:
    lines = [f"overall: {'ok' if report['ok'] else 'fail'}", f"project_dir: {report['project_dir']}"]
    for check in report["checks"]:
        lines.append(f"- {check['name']}: {'ok' if check['ok'] else 'fail'} — {check['detail']}")
    return "\n".join(lines)


def format_doctor_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2) + "\n"
