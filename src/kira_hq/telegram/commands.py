"""Telegram command handlers for Task 21."""
from __future__ import annotations

import io
import json
import logging
import os
from contextlib import redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

from kira_hq.cron_handler import unstale as default_unstale
from kira_hq.incidents import write_incident
from kira_hq.pipeline_log import GLOBAL_LOG
from kira_hq.projects_yaml import DEFAULT_PROJECTS_YAML
from kira_hq.secrets_schema import load_secrets
from kira_hq.skills.report import main as report_main
from kira_hq.skills.weekly_review import main as weekly_review_main

LOGGER = logging.getLogger(__name__)


class ApiClient(Protocol):
    def get(self, path: str) -> Any: ...
    def post(self, path: str, payload: dict[str, Any]) -> Any: ...


def parse_allowed_chats(value: str | Iterable[int | str] | None) -> set[int]:
    if value is None:
        return set()
    if isinstance(value, str):
        parts = value.split(",")
    else:
        parts = list(value)
    allowed: set[int] = set()
    for part in parts:
        text = str(part).strip()
        if not text:
            continue
        try:
            allowed.add(int(text))
        except ValueError:
            LOGGER.warning("Ignoring invalid TELEGRAM_ALLOWED_CHATS entry %r", text)
    return allowed


def _default_allowed_chats() -> set[int] | None:
    env_value = os.environ.get("TELEGRAM_ALLOWED_CHATS")
    if env_value is not None:
        return parse_allowed_chats(env_value)
    secrets = load_secrets(check_perms=False)
    secret_value = secrets.get("TELEGRAM_ALLOWED_CHATS")
    if secret_value is None:
        return set()
    return parse_allowed_chats(secret_value)


def _run_skill_entrypoint(entrypoint: Callable[[list[str] | None], int], argv: list[str]) -> str:
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = entrypoint(argv)
    if exit_code != 0:
        raise RuntimeError(f"skill entrypoint exited with status {exit_code}")
    return stdout.getvalue().strip()



def _default_status_runner(pipeline_log: Path | str, since: datetime) -> dict[str, Any]:
    output = _run_skill_entrypoint(
        report_main,
        ["--pipeline-log", str(pipeline_log), "--since", since.isoformat()],
    )
    return json.loads(output)



def _default_review_runner(
    *,
    pipeline_log: Path | str = GLOBAL_LOG,
    snapshots_dir: Path | str | None = None,
    reviews_dir: Path | str | None = None,
    now: datetime | None = None,
    projects_yaml: Path | None = DEFAULT_PROJECTS_YAML,
) -> str:
    review_output = _run_skill_entrypoint(
        weekly_review_main,
        [
            "--pipeline-log",
            str(pipeline_log),
            "--snapshots-dir",
            str(snapshots_dir or (Path.home() / ".kira-hq" / "snapshots")),
            "--reviews-dir",
            str(reviews_dir or (Path.home() / ".kira-hq" / "reviews")),
            "--now",
            (now or datetime.now(UTC)).isoformat(),
            *(
                ["--projects-yaml", str(projects_yaml)]
                if projects_yaml is not None
                else []
            ),
        ],
    )
    review_path = Path(review_output.splitlines()[-1])
    telegram_summary_path = review_path.with_name(f"{review_path.stem}.telegram.txt")
    return telegram_summary_path.read_text()


def _extract_message(update: dict[str, Any]) -> tuple[int | None, str | None]:
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    return chat.get("id"), message.get("text")


def _chat_allowed(chat_id: int | None, allowed_chats: set[int] | None) -> bool:
    if chat_id is None:
        return False
    return chat_id in allowed_chats


def _format_status(payload: dict[str, Any]) -> str:
    projects = ", ".join(payload["projects"]) if payload["projects"] else "none"
    return (
        f"Status since {payload['changes_since']}\n"
        f"Runs: {payload['runs']}\n"
        f"Failures: {payload['failures']}\n"
        f"Projects: {projects}\n"
        f"Token delta: in={payload['token_delta']['tokens_in']} out={payload['token_delta']['tokens_out']}"
    )


def _format_blockers(blockers: list[dict[str, Any]]) -> str:
    if not blockers:
        return "No current blockers."
    lines = ["Current blockers:"]
    for item in blockers:
        lines.append(f"- {item['project']} #{item['id']}: {item['title']}")
    return "\n".join(lines)


def handle_update(
    update: dict[str, Any],
    *,
    allowed_chats: str | Iterable[int | str] | None = None,
    api_client: ApiClient | None = None,
    pipeline_log: Path | str = GLOBAL_LOG,
    report_since: datetime | None = None,
    status_runner: Callable[[Path | str, datetime], dict[str, Any]] | None = None,
    review_runner: Callable[[], str] | None = None,
    unstale_runner: Callable[[str], bool] | None = None,
    incident_logger: Callable[[str, str, str], Any] | None = None,
) -> str | None:
    """Dispatch a Telegram update into a reply string.

    Unauthorized chats are silently dropped and logged. The caller is expected
    to send the returned text back to Telegram when it is not None.
    """
    chat_id, text = _extract_message(update)
    allowed = parse_allowed_chats(allowed_chats) if allowed_chats is not None else _default_allowed_chats()
    if not _chat_allowed(chat_id, allowed):
        LOGGER.warning("Unauthorized Telegram chat %s attempted command", chat_id)
        return None
    if not text or not text.strip():
        return None

    tokens = text.strip().split(maxsplit=3)
    command = tokens[0]

    try:
        if command == "/status":
            since = report_since or (datetime.now(UTC) - timedelta(hours=24))
            runner = status_runner or _default_status_runner
            payload = runner(pipeline_log, since)
            return _format_status(payload)

        if command == "/blockers":
            if api_client is None:
                return "Sorry — /blockers is unavailable: API client not configured"
            blockers = api_client.get("/views/blockers")
            return _format_blockers(list(blockers))

        if command == "/add":
            if len(tokens) < 3:
                return "Usage: /add <project> <title>"
            if api_client is None:
                return "Sorry — /add is unavailable: API client not configured"
            project = tokens[1]
            title = text.strip().split(maxsplit=2)[2]
            created = api_client.post(
                f"/projects/{project}/tasks",
                {"title": title, "description": "", "priority": "medium"},
            )
            return f"Added task {project}#{created['id']}: {created['title']}"

        if command == "/fix":
            if len(tokens) < 4:
                return "Usage: /fix <project> <task-id> <note>"
            if api_client is None:
                return "Sorry — /fix is unavailable: API client not configured"
            project, task_id, note = tokens[1], tokens[2], tokens[3]
            created = api_client.post(
                f"/projects/{project}/tasks",
                {
                    "title": f"FIX: {note}",
                    "description": note,
                    "priority": "medium",
                    "parent_id": task_id,
                },
            )
            return f"Created fix task {project}#{created['id']} under parent {task_id}"

        if command == "/review":
            if review_runner is not None:
                return review_runner()
            return _default_review_runner(pipeline_log=pipeline_log)

        if command == "/unstale":
            if len(tokens) < 2:
                return "Usage: /unstale <project>"
            project = tokens[1]
            runner = unstale_runner or default_unstale
            ok = runner(project)
            if ok:
                return f"Project {project} reactivated."
            return f"Project {project} was not stale (or was not found)."

        return (
            "Unknown command. Available: /status /blockers /add /fix /review /unstale"
        )
    except Exception as exc:  # friendly Telegram-safe fallback
        LOGGER.exception("Telegram command %s failed", command)
        logger = incident_logger or write_incident
        try:
            logger("kira-hq", f"telegram-{command}", str(exc))
        except Exception:
            LOGGER.exception("Telegram incident logging failed for %s", command)
        return f"Sorry — {command} failed: {exc}"
