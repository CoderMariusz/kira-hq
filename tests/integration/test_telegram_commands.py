"""Integration tests for Telegram command dispatch — Task 21."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


class FakeApiClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict | None]] = []
        self.responses: dict[tuple[str, str], object] = {}

    def get(self, path: str):
        self.calls.append(("GET", path, None))
        response = self.responses.get(("GET", path), [])
        if isinstance(response, Exception):
            raise response
        return response

    def post(self, path: str, payload: dict):
        self.calls.append(("POST", path, payload))
        response = self.responses.get(("POST", path), {"id": "1", **payload})
        if isinstance(response, Exception):
            raise response
        return response


def _update(text: str, chat_id: int = 111) -> dict:
    return {
        "message": {
            "message_id": 1,
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
        }
    }


def test_status_returns_report_summary(tmp_path: Path):
    from kira_hq.telegram.commands import handle_update

    pipeline_log = tmp_path / "pipeline.log.md"
    pipeline_log.write_text(
        "| timestamp | project | skill | provider | expand_used | tokens_in | tokens_out | status | duration_s | notes |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
        "| 2026-04-19T08:00:00+00:00 | alpha | k1 | sonnet | false | 100 | 50 | ok | 1.0 | ok |\n"
        "| 2026-04-19T08:05:00+00:00 | beta | k2 | sonnet | false | 200 | 80 | fail | 2.0 | boom |\n"
    )

    result = handle_update(
        _update("/status"),
        allowed_chats={111},
        pipeline_log=pipeline_log,
        report_since=datetime(2026, 4, 19, 0, 0, tzinfo=UTC),
    )

    assert result == (
        "Status since 2026-04-19T00:00:00+00:00\n"
        "Runs: 2\n"
        "Failures: 1\n"
        "Projects: alpha, beta\n"
        "Token delta: in=300 out=130"
    )


def test_status_uses_injected_runner_entrypoint(tmp_path: Path):
    from kira_hq.telegram.commands import handle_update

    pipeline_log = tmp_path / "pipeline.log.md"
    seen: dict[str, object] = {}

    def status_runner(log_path: Path | str, since: datetime) -> dict[str, object]:
        seen["pipeline_log"] = log_path
        seen["since"] = since
        return {
            "changes_since": since.isoformat(),
            "runs": 3,
            "failures": 0,
            "projects": ["alpha"],
            "token_delta": {"tokens_in": 12, "tokens_out": 7},
        }

    result = handle_update(
        _update("/status"),
        allowed_chats={111},
        pipeline_log=pipeline_log,
        report_since=datetime(2026, 4, 19, 0, 0, tzinfo=UTC),
        status_runner=status_runner,
    )

    assert seen == {
        "pipeline_log": pipeline_log,
        "since": datetime(2026, 4, 19, 0, 0, tzinfo=UTC),
    }
    assert result == (
        "Status since 2026-04-19T00:00:00+00:00\n"
        "Runs: 3\n"
        "Failures: 0\n"
        "Projects: alpha\n"
        "Token delta: in=12 out=7"
    )


def test_blockers_calls_views_endpoint():
    from kira_hq.telegram.commands import handle_update

    api = FakeApiClient()
    api.responses[("GET", "/views/blockers")] = [
        {"project": "alpha", "id": "2", "title": "Blocked alpha"},
        {"project": "beta", "id": "8", "title": "Blocked beta"},
    ]

    result = handle_update(_update("/blockers"), allowed_chats={111}, api_client=api)

    assert api.calls == [("GET", "/views/blockers", None)]
    assert result == (
        "Current blockers:\n"
        "- alpha #2: Blocked alpha\n"
        "- beta #8: Blocked beta"
    )


def test_add_posts_task_to_project():
    from kira_hq.telegram.commands import handle_update

    api = FakeApiClient()
    api.responses[("POST", "/projects/alpha/tasks")] = {
        "id": "12",
        "title": "Ship docs",
        "status": "pending",
    }

    result = handle_update(_update("/add alpha Ship docs"), allowed_chats={111}, api_client=api)

    assert api.calls == [
        (
            "POST",
            "/projects/alpha/tasks",
            {
                "title": "Ship docs",
                "description": "",
                "priority": "medium",
            },
        )
    ]
    assert result == "Added task alpha#12: Ship docs"


def test_fix_creates_fix_subtask_with_parent_note():
    from kira_hq.telegram.commands import handle_update

    api = FakeApiClient()
    api.responses[("POST", "/projects/alpha/tasks")] = {
        "id": "13",
        "title": "FIX: flaky deploy",
        "status": "pending",
    }

    result = handle_update(
        _update("/fix alpha 7 flaky deploy"),
        allowed_chats={111},
        api_client=api,
    )

    assert api.calls == [
        (
            "POST",
            "/projects/alpha/tasks",
            {
                "title": "FIX: flaky deploy",
                "description": "flaky deploy",
                "priority": "medium",
                "parent_id": "7",
            },
        )
    ]
    assert result == "Created fix task alpha#13 under parent 7"


def test_review_triggers_weekly_review_runner(tmp_path: Path):
    from kira_hq.telegram.commands import handle_update

    called: dict[str, object] = {}

    def review_runner() -> str:
        out = tmp_path / "2026-W16.telegram.txt"
        out.write_text("Weekly review 2026-W16\n- ok")
        called["ran"] = True
        return out.read_text()

    result = handle_update(
        _update("/review"),
        allowed_chats={111},
        review_runner=review_runner,
    )

    assert called == {"ran": True}
    assert result == "Weekly review 2026-W16\n- ok"


def test_default_review_runner_uses_weekly_review_entrypoint(monkeypatch, tmp_path: Path):
    from kira_hq.telegram import commands

    seen: dict[str, object] = {}

    def fake_review_entrypoint(argv: list[str] | None = None) -> int:
        seen["argv"] = argv
        review_path = tmp_path / "reviews" / "2026-W16.md"
        telegram_path = tmp_path / "reviews" / "2026-W16.telegram.txt"
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_text("weekly review")
        telegram_path.write_text("Weekly review 2026-W16\n- ok")
        print(review_path)
        return 0

    monkeypatch.setattr(commands, "weekly_review_main", fake_review_entrypoint)

    result = commands._default_review_runner(
        pipeline_log=tmp_path / "pipeline.log.md",
        snapshots_dir=tmp_path / "snapshots",
        reviews_dir=tmp_path / "reviews",
        now=datetime(2026, 4, 19, 9, 0, tzinfo=UTC),
    )

    assert seen["argv"] == [
        "--pipeline-log",
        str(tmp_path / "pipeline.log.md"),
        "--snapshots-dir",
        str(tmp_path / "snapshots"),
        "--reviews-dir",
        str(tmp_path / "reviews"),
        "--now",
        "2026-04-19T09:00:00+00:00",
        "--projects-yaml",
        str(commands.DEFAULT_PROJECTS_YAML),
    ]
    assert result == "Weekly review 2026-W16\n- ok"


def test_unstale_calls_local_unstale_runner():
    from kira_hq.telegram.commands import handle_update

    calls: list[str] = []

    def unstale_runner(project: str) -> bool:
        calls.append(project)
        return True

    result = handle_update(
        _update("/unstale alpha"),
        allowed_chats={111},
        unstale_runner=unstale_runner,
    )

    assert calls == ["alpha"]
    assert result == "Project alpha reactivated."


def test_unauthorized_chat_is_silent_and_logged(caplog):
    from kira_hq.telegram.commands import handle_update

    with caplog.at_level("WARNING"):
        result = handle_update(_update("/status", chat_id=999), allowed_chats={111})

    assert result is None
    assert "Unauthorized Telegram chat 999" in caplog.text


def test_empty_explicit_allowlist_denies_all(caplog):
    from kira_hq.telegram.commands import handle_update

    with caplog.at_level("WARNING"):
        result = handle_update(_update("/status", chat_id=111), allowed_chats="")

    assert result is None
    assert "Unauthorized Telegram chat 111" in caplog.text


def test_malformed_env_allowlist_fails_closed(monkeypatch, caplog):
    from kira_hq.telegram.commands import handle_update

    monkeypatch.setenv("TELEGRAM_ALLOWED_CHATS", "not-an-int")

    with caplog.at_level("WARNING"):
        result = handle_update(_update("/status", chat_id=111))

    assert result is None
    assert "Ignoring invalid TELEGRAM_ALLOWED_CHATS entry 'not-an-int'" in caplog.text
    assert "Unauthorized Telegram chat 111" in caplog.text


def test_missing_allowlist_configuration_fails_closed(monkeypatch, caplog):
    from kira_hq.telegram import commands

    monkeypatch.delenv("TELEGRAM_ALLOWED_CHATS", raising=False)
    monkeypatch.setattr(commands, "load_secrets", lambda check_perms=False: {})

    with caplog.at_level("WARNING"):
        result = commands.handle_update(_update("/status", chat_id=111))

    assert result is None
    assert "Unauthorized Telegram chat 111" in caplog.text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("/add", "Usage: /add <project> <title>"),
        ("/fix alpha", "Usage: /fix <project> <task-id> <note>"),
        ("/unstale", "Usage: /unstale <project>"),
    ],
)
def test_usage_errors_are_friendly(text: str, expected: str):
    from kira_hq.telegram.commands import handle_update

    assert handle_update(_update(text), allowed_chats={111}) == expected


def test_backend_errors_are_friendly_and_logged_to_incidents(tmp_path: Path):
    from kira_hq.telegram.commands import handle_update

    api = FakeApiClient()
    api.responses[("GET", "/views/blockers")] = RuntimeError("boom")
    seen: dict[str, object] = {}

    def incident_logger(project: str, skill: str, error: str):
        seen["project"] = project
        seen["skill"] = skill
        seen["error"] = error
        incident_path = tmp_path / "incidents" / "incident.md"
        incident_path.parent.mkdir(parents=True, exist_ok=True)
        incident_path.write_text(error)
        return incident_path

    result = handle_update(
        _update("/blockers"),
        allowed_chats={111},
        api_client=api,
        incident_logger=incident_logger,
    )

    assert result == "Sorry — /blockers failed: boom"
    assert seen == {
        "project": "kira-hq",
        "skill": "telegram-/blockers",
        "error": "boom",
    }
