from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from kira_hq.telegram.bridge import (
    TelegramBridge,
    TelegramBridgeConfig,
    TelegramBridgeError,
)

pytestmark = pytest.mark.integration


class FakeTelegramClient:
    def __init__(self, updates: list[dict] | None = None) -> None:
        self.updates = list(updates or [])
        self.sent_messages: list[tuple[int, str]] = []
        self.calls: list[tuple[str, object]] = []
        self.closed = False

    def get_updates(self, *, offset: int | None, timeout_s: int, limit: int = 100) -> list[dict]:
        self.calls.append(("get_updates", {"offset": offset, "timeout_s": timeout_s, "limit": limit}))
        updates, self.updates = self.updates, []
        return updates

    def send_message(self, chat_id: int, text: str) -> dict:
        self.sent_messages.append((chat_id, text))
        self.calls.append(("send_message", {"chat_id": chat_id, "text": text}))
        return {"message_id": len(self.sent_messages)}

    def close(self) -> None:
        self.closed = True


class FakeApiClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict | None]] = []

    def get(self, path: str):
        self.calls.append(("GET", path, None))
        if path == "/views/blockers":
            return [{"project": "alpha", "id": "7", "title": "Blocked deploy"}]
        raise AssertionError(path)

    def post(self, path: str, payload: dict):
        self.calls.append(("POST", path, payload))
        return {"id": "1", **payload}

    def close(self) -> None:
        return None


class CapturingIncidentLogger:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, project: str, skill: str, error: str):
        self.calls.append((project, skill, error))
        return None


def _config(tmp_path: Path) -> TelegramBridgeConfig:
    return TelegramBridgeConfig(
        bot_token="token",
        allowed_chat_id=111,
        inbox_dir=tmp_path / "tg-inbox",
        outbox_dir=tmp_path / "tg-outbox",
        offset_path=tmp_path / "telegram-offset.json",
        poll_timeout_s=1,
        outbox_ttl_seconds=60,
    )


def _update(text: str, *, update_id: int = 1, chat_id: int = 111) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id * 10,
            "chat": {"id": chat_id, "type": "private"},
            "text": text,
        },
    }


def test_poll_once_dispatches_deterministic_command_and_persists_offset(tmp_path: Path) -> None:
    telegram = FakeTelegramClient([_update("/blockers", update_id=55)])
    api_client = FakeApiClient()
    bridge = TelegramBridge(_config(tmp_path), telegram_client=telegram, api_client=api_client)

    processed = bridge.poll_once()

    assert processed == 1
    assert api_client.calls == [("GET", "/views/blockers", None)]
    assert telegram.sent_messages == [(111, "Current blockers:\n- alpha #7: Blocked deploy")]
    offset_payload = json.loads((tmp_path / "telegram-offset.json").read_text(encoding="utf-8"))
    assert offset_payload["next_offset"] == 56


def test_local_api_client_bypasses_exposed_auth_for_in_process_bridge(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from kira_hq.telegram.bridge import LocalApiClient

    monkeypatch.setenv("KIRA_HQ_EXPOSED", "true")
    client = LocalApiClient(project_dir=tmp_path)
    try:
        assert isinstance(client.get("/views/blockers"), list)
    finally:
        client.close()


def test_poll_once_queues_ask_requests_in_inbox_and_acks(tmp_path: Path) -> None:
    telegram = FakeTelegramClient([_update("/ask inspect rollout", update_id=7)])
    bridge = TelegramBridge(_config(tmp_path), telegram_client=telegram, api_client=FakeApiClient())

    processed = bridge.poll_once()

    assert processed == 1
    inbox_files = sorted((tmp_path / "tg-inbox").glob("*.json"))
    assert len(inbox_files) == 1
    payload = json.loads(inbox_files[0].read_text(encoding="utf-8"))
    assert payload["kind"] == "telegram-orchestration-request"
    assert payload["chat_id"] == 111
    assert payload["update_id"] == 7
    assert payload["text"] == "inspect rollout"
    assert payload["reply_via"]["transport"] == "telegram-outbox"
    assert telegram.sent_messages[0][0] == 111
    assert telegram.sent_messages[0][1].startswith("Queued request tg-")


def test_plain_text_also_queues_free_form_request(tmp_path: Path) -> None:
    telegram = FakeTelegramClient([_update("please inspect the release branch", update_id=8)])
    bridge = TelegramBridge(_config(tmp_path), telegram_client=telegram, api_client=FakeApiClient())

    bridge.poll_once()

    inbox_files = sorted((tmp_path / "tg-inbox").glob("*.json"))
    payload = json.loads(inbox_files[0].read_text(encoding="utf-8"))
    assert payload["text"] == "please inspect the release branch"


def test_bridge_drops_unauthorized_chat_without_side_effects(tmp_path: Path) -> None:
    telegram = FakeTelegramClient([_update("/blockers", update_id=9, chat_id=999)])
    bridge = TelegramBridge(_config(tmp_path), telegram_client=telegram, api_client=FakeApiClient())

    processed = bridge.poll_once()

    assert processed == 1
    assert telegram.sent_messages == []
    assert list((tmp_path / "tg-inbox").glob("*.json")) == []


def test_drain_outbox_delivers_pending_message_and_marks_sent(tmp_path: Path) -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    telegram = FakeTelegramClient()
    bridge = TelegramBridge(
        _config(tmp_path),
        telegram_client=telegram,
        api_client=FakeApiClient(),
        now=lambda: now,
    )
    outbox_path = tmp_path / "tg-outbox" / "reply.json"
    outbox_path.write_text(
        json.dumps(
            {
                "chat_id": 111,
                "text": "Claude reply",
                "created_at": (now - timedelta(seconds=10)).isoformat(),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    delivered = bridge.drain_outbox()

    assert delivered == 1
    assert telegram.sent_messages == [(111, "Claude reply")]
    payload = json.loads(outbox_path.read_text(encoding="utf-8"))
    assert payload["sent_at"] == now.isoformat()


def test_drain_outbox_expires_stale_reply_without_sending(tmp_path: Path) -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=UTC)
    telegram = FakeTelegramClient()
    bridge = TelegramBridge(
        _config(tmp_path),
        telegram_client=telegram,
        api_client=FakeApiClient(),
        now=lambda: now,
    )
    outbox_path = tmp_path / "tg-outbox" / "expired.json"
    outbox_path.write_text(
        json.dumps(
            {
                "chat_id": 111,
                "text": "Too late",
                "created_at": (now - timedelta(seconds=120)).isoformat(),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    delivered = bridge.drain_outbox()

    assert delivered == 0
    assert telegram.sent_messages == []
    payload = json.loads(outbox_path.read_text(encoding="utf-8"))
    assert payload["expired_at"] == now.isoformat()
    assert "sent_at" not in payload

    delivered_again = bridge.drain_outbox()
    assert delivered_again == 0
    assert json.loads(outbox_path.read_text(encoding="utf-8")) == payload


def test_bridge_creates_private_transport_dirs_and_files(tmp_path: Path) -> None:
    config = _config(tmp_path)
    telegram = FakeTelegramClient([_update("/ask inspect rollout", update_id=3)])
    bridge = TelegramBridge(config, telegram_client=telegram, api_client=FakeApiClient())

    assert oct(config.inbox_dir.stat().st_mode & 0o777) == "0o700"
    assert oct(config.outbox_dir.stat().st_mode & 0o777) == "0o700"
    assert oct(config.offset_path.parent.stat().st_mode & 0o777) == "0o700"

    bridge.poll_once()

    inbox_file = next(config.inbox_dir.glob("*.json"))
    assert oct(inbox_file.stat().st_mode & 0o777) == "0o600"
    assert oct(config.offset_path.stat().st_mode & 0o777) == "0o600"


def test_config_from_sources_requires_exactly_one_paired_chat(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret")
    monkeypatch.setenv("TELEGRAM_ALLOWED_CHATS", "111,222")

    with pytest.raises(TelegramBridgeError, match="exactly one paired chat"):
        TelegramBridgeConfig.from_sources(inbox_dir=tmp_path / "inbox")


def test_telegram_transport_errors_are_sanitized() -> None:
    token = "12345:secret-token"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request, text="unauthorized")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    from kira_hq.telegram.bridge import TelegramBotClient

    bot = TelegramBotClient(token, client=client)

    with pytest.raises(TelegramBridgeError) as excinfo:
        bot.get_updates(offset=None, timeout_s=1)

    message = str(excinfo.value)
    assert token not in message
    assert "[REDACTED]" in message


def test_poll_once_logs_incident_and_keeps_running_on_get_updates_failure(tmp_path: Path) -> None:
    class FailingTelegramClient(FakeTelegramClient):
        def get_updates(self, *, offset: int | None, timeout_s: int, limit: int = 100) -> list[dict]:
            raise TelegramBridgeError("Telegram getUpdates failed: https://api.telegram.org/bot[REDACTED]/getUpdates")

    incidents = CapturingIncidentLogger()
    telegram = FailingTelegramClient()
    bridge = TelegramBridge(
        _config(tmp_path),
        telegram_client=telegram,
        api_client=FakeApiClient(),
        incident_logger=incidents,
    )

    processed = bridge.poll_once()

    assert processed == 0
    assert incidents.calls == [
        (
            "kira-hq",
            "telegram-getUpdates",
            "Telegram getUpdates failed: https://api.telegram.org/bot[REDACTED]/getUpdates",
        )
    ]


def test_poll_once_resets_invalid_offset_state_without_crashing(tmp_path: Path) -> None:
    offset_path = tmp_path / "telegram-offset.json"
    offset_path.write_text("{not-json}\n", encoding="utf-8")
    telegram = FakeTelegramClient([_update("/blockers", update_id=99)])
    incidents = CapturingIncidentLogger()
    bridge = TelegramBridge(
        _config(tmp_path),
        telegram_client=telegram,
        api_client=FakeApiClient(),
        incident_logger=incidents,
    )

    processed = bridge.poll_once()

    assert processed == 1
    assert incidents.calls[0][0] == "kira-hq"
    assert incidents.calls[0][1] == "telegram-offset"
    assert "Invalid Telegram offset state" in incidents.calls[0][2]
    payload = json.loads(offset_path.read_text(encoding="utf-8"))
    assert payload["next_offset"] == 100


def test_process_update_logs_incident_and_keeps_offset_on_send_failure(tmp_path: Path) -> None:
    class FailingTelegramClient(FakeTelegramClient):
        def send_message(self, chat_id: int, text: str) -> dict:
            raise TelegramBridgeError("Telegram sendMessage failed: timeout")

    incidents = CapturingIncidentLogger()
    telegram = FailingTelegramClient([_update("/blockers", update_id=5)])
    bridge = TelegramBridge(
        _config(tmp_path),
        telegram_client=telegram,
        api_client=FakeApiClient(),
        incident_logger=incidents,
    )

    processed = bridge.poll_once()

    assert processed == 1
    assert json.loads((tmp_path / "telegram-offset.json").read_text(encoding="utf-8"))["next_offset"] == 6
    assert incidents.calls == [
        ("kira-hq", "telegram-update", "Telegram sendMessage failed: timeout")
    ]


def test_drain_outbox_quarantines_unauthorized_payload_instead_of_retrying_forever(tmp_path: Path) -> None:
    telegram = FakeTelegramClient()
    bridge = TelegramBridge(_config(tmp_path), telegram_client=telegram, api_client=FakeApiClient())
    outbox_path = tmp_path / "tg-outbox" / "unauthorized.json"
    outbox_path.write_text(
        json.dumps({"chat_id": 999, "text": "nope", "created_at": datetime.now(UTC).isoformat()}) + "\n",
        encoding="utf-8",
    )

    delivered = bridge.drain_outbox()

    quarantined = tmp_path / "tg-outbox" / "quarantine" / "unauthorized.json"
    assert delivered == 0
    assert not outbox_path.exists()
    payload = json.loads(quarantined.read_text(encoding="utf-8"))
    assert payload["status"] == "rejected"
    assert payload["reject_reason"] == "unauthorized-chat"


def test_drain_outbox_quarantines_malformed_json(tmp_path: Path) -> None:
    telegram = FakeTelegramClient()
    bridge = TelegramBridge(_config(tmp_path), telegram_client=telegram, api_client=FakeApiClient())
    outbox_path = tmp_path / "tg-outbox" / "broken.json"
    outbox_path.write_text("{not-json\n", encoding="utf-8")

    delivered = bridge.drain_outbox()

    quarantined = tmp_path / "tg-outbox" / "quarantine" / "broken.json"
    assert delivered == 0
    assert not outbox_path.exists()
    payload = json.loads(quarantined.read_text(encoding="utf-8"))
    assert payload["status"] == "rejected"
    assert payload["reject_reason"] == "malformed-json"


def test_drain_outbox_retries_transient_transport_failures_without_quarantine(tmp_path: Path) -> None:
    class FlakyTelegramClient(FakeTelegramClient):
        def __init__(self) -> None:
            super().__init__()
            self.attempts = 0

        def send_message(self, chat_id: int, text: str) -> dict:
            self.attempts += 1
            if self.attempts == 1:
                raise TelegramBridgeError("Telegram sendMessage failed: timeout")
            return super().send_message(chat_id, text)

    incidents = CapturingIncidentLogger()
    telegram = FlakyTelegramClient()
    bridge = TelegramBridge(
        _config(tmp_path),
        telegram_client=telegram,
        api_client=FakeApiClient(),
        incident_logger=incidents,
    )
    outbox_path = tmp_path / "tg-outbox" / "retry.json"
    outbox_path.write_text(
        json.dumps({"chat_id": 111, "text": "retry me", "created_at": datetime.now(UTC).isoformat()}) + "\n",
        encoding="utf-8",
    )

    first = bridge.drain_outbox()
    second = bridge.drain_outbox()

    assert first == 0
    assert second == 1
    assert outbox_path.exists()
    assert not (tmp_path / "tg-outbox" / "quarantine" / "retry.json").exists()
    payload = json.loads(outbox_path.read_text(encoding="utf-8"))
    assert payload["sent_at"]
    assert incidents.calls == [("kira-hq", "telegram-outbox", "Telegram sendMessage failed: timeout")]


def test_config_from_sources_honors_project_dir_for_project_secrets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project_dir = tmp_path / "demo"
    project_dir.mkdir()
    seen: dict[str, object] = {}

    def fake_load_secrets(project_name=None, *, global_env=None, projects_root=None, check_perms=True):
        seen["project_name"] = project_name
        seen["projects_root"] = projects_root
        seen["check_perms"] = check_perms
        return {"TELEGRAM_BOT_TOKEN": "secret", "TELEGRAM_ALLOWED_CHATS": "111"}

    monkeypatch.setattr("kira_hq.telegram.bridge.load_secrets", fake_load_secrets)

    config = TelegramBridgeConfig.from_sources(project_dir=project_dir)

    assert config.bot_token == "secret"
    assert seen == {
        "project_name": "demo",
        "projects_root": tmp_path,
        "check_perms": True,
    }


def test_bridge_honors_project_dir_for_status_pipeline_log(tmp_path: Path) -> None:
    telegram = FakeTelegramClient([_update("/status", update_id=12)])
    captured: dict[str, object] = {}

    def status_runner(log_path: Path | str, since: datetime) -> dict[str, object]:
        captured["log_path"] = Path(log_path)
        return {
            "changes_since": since.isoformat(),
            "runs": 0,
            "failures": 0,
            "projects": [],
            "token_delta": {"tokens_in": 0, "tokens_out": 0},
        }

    project_dir = tmp_path / "repo"
    project_dir.mkdir()

    from kira_hq.telegram import commands as commands_module

    original_status = commands_module._default_status_runner
    commands_module._default_status_runner = status_runner
    try:
        bridge = TelegramBridge(
            _config(tmp_path),
            telegram_client=telegram,
            api_client=FakeApiClient(),
            project_dir=project_dir,
        )
        bridge.poll_once()
    finally:
        commands_module._default_status_runner = original_status

    assert captured["log_path"] == project_dir / "pipeline.log.md"
