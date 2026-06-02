"""Local Telegram Bot API long-poll bridge for Kira-HQ."""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import httpx
from fastapi.testclient import TestClient

from kira_hq.api.app import make_app
from kira_hq.incidents import write_incident
from kira_hq.secrets_schema import load_secrets
from kira_hq.telegram.commands import handle_update, parse_allowed_chats

LOGGER = logging.getLogger(__name__)

KIRA_HOME = Path.home() / ".kira-hq"
DEFAULT_INBOX_DIR = KIRA_HOME / "tg-inbox"
DEFAULT_OUTBOX_DIR = KIRA_HOME / "tg-outbox"
DEFAULT_OFFSET_PATH = KIRA_HOME / "telegram-offset.json"
DEFAULT_OUTBOX_TTL_SECONDS = 3600
DEFAULT_MESSAGE_MAX_CHARS = 4000
QUARANTINE_DIRNAME = "quarantine"


class TelegramBridgeError(RuntimeError):
    """Bridge misconfiguration or transport failure."""


class TerminalOutboxError(TelegramBridgeError):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def sanitize_telegram_error(text: str, bot_token: str | None = None) -> str:
    sanitized = re.sub(r"(https://api\.telegram\.org/bot)[^/\s]+", r"\1[REDACTED]", text)
    if bot_token:
        sanitized = sanitized.replace(bot_token, "[REDACTED]")
    return sanitized


def _single_project_doc(project_dir: Path) -> dict[str, Any]:
    return {
        "version": 2,
        "projects": [
            {
                "name": project_dir.name,
                "path": str(project_dir),
                "status": "active",
                "priority": "medium",
            }
        ],
    }


def _ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    path.chmod(0o700)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        tmp_name = handle.name
    Path(tmp_name).chmod(0o600)
    Path(tmp_name).replace(path)
    path.chmod(0o600)


@dataclass(frozen=True)
class TelegramBridgeConfig:
    bot_token: str
    allowed_chat_id: int
    inbox_dir: Path = DEFAULT_INBOX_DIR
    outbox_dir: Path = DEFAULT_OUTBOX_DIR
    offset_path: Path = DEFAULT_OFFSET_PATH
    poll_timeout_s: int = 30
    message_max_chars: int = DEFAULT_MESSAGE_MAX_CHARS
    outbox_ttl_seconds: int = DEFAULT_OUTBOX_TTL_SECONDS

    @classmethod
    def from_sources(
        cls,
        *,
        project_dir: Path | None = None,
        inbox_dir: Path | None = None,
        outbox_dir: Path | None = None,
        offset_path: Path | None = None,
        poll_timeout_s: int = 30,
        message_max_chars: int = DEFAULT_MESSAGE_MAX_CHARS,
        outbox_ttl_seconds: int = DEFAULT_OUTBOX_TTL_SECONDS,
    ) -> "TelegramBridgeConfig":
        project_root = project_dir.expanduser().resolve() if project_dir is not None else None
        secrets = (
            load_secrets(project_root.name, projects_root=project_root.parent)
            if project_root is not None
            else load_secrets()
        )
        token = os.environ["TELEGRAM_BOT_TOKEN"] if "TELEGRAM_BOT_TOKEN" in os.environ else secrets.get("TELEGRAM_BOT_TOKEN")
        allowed_raw = (
            os.environ["TELEGRAM_ALLOWED_CHATS"]
            if "TELEGRAM_ALLOWED_CHATS" in os.environ
            else secrets.get("TELEGRAM_ALLOWED_CHATS")
        )
        allowed = parse_allowed_chats(allowed_raw)
        if not token:
            raise TelegramBridgeError("TELEGRAM_BOT_TOKEN is required for telegram-serve")
        if not allowed:
            raise TelegramBridgeError("TELEGRAM_ALLOWED_CHATS must contain exactly one paired chat id")
        if len(allowed) != 1:
            raise TelegramBridgeError(
                "Phase 1 telegram-serve requires exactly one paired chat in TELEGRAM_ALLOWED_CHATS"
            )
        return cls(
            bot_token=token,
            allowed_chat_id=next(iter(allowed)),
            inbox_dir=(inbox_dir or DEFAULT_INBOX_DIR).expanduser(),
            outbox_dir=(outbox_dir or DEFAULT_OUTBOX_DIR).expanduser(),
            offset_path=(offset_path or DEFAULT_OFFSET_PATH).expanduser(),
            poll_timeout_s=poll_timeout_s,
            message_max_chars=message_max_chars,
            outbox_ttl_seconds=outbox_ttl_seconds,
        )


class LocalApiClient:
    """Internal API client backed by the FastAPI app, no localhost server required."""

    def __init__(self, *, project_dir: Path | None = None) -> None:
        project_root = project_dir.expanduser().resolve() if project_dir is not None else None
        app = make_app(
            projects_loader=(lambda: _single_project_doc(project_root)) if project_root is not None else None,
            projects_yaml_path=project_root / "projects.yaml" if project_root is not None else None,
            pipeline_log_loader=(lambda: project_root / "pipeline.log.md") if project_root is not None else None,
            auth_exposed_probe=lambda: False,
        )
        self._test_client = TestClient(app)

    def get(self, path: str) -> Any:
        response = self._test_client.get(path)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        response = self._test_client.post(path, json=payload)
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._test_client.close()


class TelegramBotClient:
    def __init__(self, bot_token: str, *, client: httpx.Client | None = None) -> None:
        self._bot_token = bot_token
        self._owns_client = client is None
        self._client = client or httpx.Client(timeout=60.0)
        self._base_url = f"https://api.telegram.org/bot{bot_token}"

    def get_updates(self, *, offset: int | None, timeout_s: int, limit: int = 100) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": timeout_s, "limit": limit}
        if offset is not None:
            payload["offset"] = offset
        try:
            response = self._client.get(f"{self._base_url}/getUpdates", params=payload)
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise self._transport_error("getUpdates", exc) from exc
        if not body.get("ok"):
            raise self._transport_error("getUpdates", body)
        result = body.get("result")
        return list(result) if isinstance(result, list) else []

    def send_message(self, chat_id: int, text: str) -> dict[str, Any]:
        try:
            response = self._client.post(
                f"{self._base_url}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise self._transport_error("sendMessage", exc) from exc
        if not body.get("ok"):
            raise self._transport_error("sendMessage", body)
        result = body.get("result")
        return result if isinstance(result, dict) else {}

    def _transport_error(self, action: str, detail: object) -> TelegramBridgeError:
        if isinstance(detail, str):
            rendered = detail
        elif isinstance(detail, Exception):
            rendered = str(detail)
        else:
            rendered = json.dumps(detail, ensure_ascii=False, sort_keys=True)
        return TelegramBridgeError(f"Telegram {action} failed: {sanitize_telegram_error(rendered, self._bot_token)}")

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


@dataclass
class BridgePaths:
    inbox_dir: Path
    outbox_dir: Path
    offset_path: Path
    quarantine_dir: Path

    def ensure(self) -> None:
        _ensure_private_dir(self.inbox_dir)
        _ensure_private_dir(self.outbox_dir)
        _ensure_private_dir(self.offset_path.parent)
        _ensure_private_dir(self.quarantine_dir)


class TelegramBridge:
    def __init__(
        self,
        config: TelegramBridgeConfig,
        *,
        telegram_client: TelegramBotClient,
        api_client: Any | None = None,
        incident_logger: Callable[..., Any] = write_incident,
        now: Callable[[], datetime] | None = None,
        project_dir: Path | None = None,
    ) -> None:
        self.config = config
        self.telegram_client = telegram_client
        self.project_dir = project_dir.expanduser().resolve() if project_dir is not None else None
        self.api_client = api_client or LocalApiClient(project_dir=self.project_dir)
        self.incident_logger = incident_logger
        self.now = now or (lambda: datetime.now(UTC))
        self.paths = BridgePaths(
            config.inbox_dir,
            config.outbox_dir,
            config.offset_path,
            config.outbox_dir / QUARANTINE_DIRNAME,
        )
        self.paths.ensure()

    def close(self) -> None:
        close_api = getattr(self.api_client, "close", None)
        if callable(close_api):
            close_api()
        self.telegram_client.close()

    def load_offset(self) -> int | None:
        if not self.config.offset_path.exists():
            return None
        try:
            payload = json.loads(self.config.offset_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TelegramBridgeError(f"Invalid Telegram offset state: {self.config.offset_path}") from exc
        offset = payload.get("next_offset")
        return int(offset) if offset is not None else None

    def save_offset(self, next_offset: int) -> None:
        payload = {
            "next_offset": int(next_offset),
            "updated_at": self.now().isoformat(),
        }
        _write_json_atomic(self.config.offset_path, payload)

    def serve_forever(self, *, max_iterations: int | None = None, drain_outbox_first: bool = True) -> None:
        iterations = 0
        try:
            while max_iterations is None or iterations < max_iterations:
                if drain_outbox_first:
                    self.drain_outbox()
                self.poll_once()
                iterations += 1
        except KeyboardInterrupt:
            LOGGER.info("Telegram bridge interrupted; shutting down")
        finally:
            self.close()

    def poll_once(self) -> int:
        try:
            offset = self.load_offset()
        except TelegramBridgeError as exc:
            self._log_incident("telegram-offset", exc)
            LOGGER.warning("Telegram offset state invalid; resetting offset: %s", exc)
            offset = None
        try:
            updates = self.telegram_client.get_updates(offset=offset, timeout_s=self.config.poll_timeout_s)
        except TelegramBridgeError as exc:
            self._log_incident("telegram-getUpdates", exc)
            LOGGER.warning("Telegram polling failed: %s", exc)
            return 0
        processed = 0
        for update in updates:
            try:
                self.process_update(update)
            except TelegramBridgeError as exc:
                self._log_incident("telegram-update", exc)
                LOGGER.warning("Telegram update processing failed: %s", exc)
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                self.save_offset(update_id + 1)
            processed += 1
        self.drain_outbox()
        return processed

    def process_update(self, update: dict[str, Any]) -> str | None:
        chat_id, text = self.extract_chat_and_text(update)
        if chat_id != self.config.allowed_chat_id:
            LOGGER.warning("Unauthorized Telegram chat %s attempted bridge access", chat_id)
            return None
        if not text:
            return None

        if self.is_free_form_request(text):
            request_id = self.enqueue_request(update, chat_id=chat_id, text=text)
            reply = f"Queued request {request_id}. Waiting for orchestrator reply via outbox."
            self.telegram_client.send_message(chat_id, reply)
            return reply

        reply = handle_update(
            update,
            allowed_chats={self.config.allowed_chat_id},
            api_client=self.api_client,
            pipeline_log=self._pipeline_log_path(),
            incident_logger=self.incident_logger,
        )
        if reply:
            self.telegram_client.send_message(chat_id, self._bounded_text(reply))
        return reply

    def drain_outbox(self) -> int:
        delivered = 0
        for path in sorted(self.config.outbox_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("sent_at") or payload.get("expired_at") or payload.get("rejected_at"):
                    continue
                try:
                    chat_id = int(payload.get("chat_id"))
                except (TypeError, ValueError) as exc:
                    raise TerminalOutboxError("invalid-chat-id", "outbox payload is missing a valid integer chat_id") from exc
                if chat_id != self.config.allowed_chat_id:
                    raise TerminalOutboxError(
                        "unauthorized-chat",
                        f"outbox payload targets unauthorized chat {chat_id}",
                    )
                try:
                    expired = self._is_expired(payload)
                except (TypeError, ValueError) as exc:
                    raise TerminalOutboxError("invalid-expiry", "outbox payload has an invalid timestamp") from exc
                if expired:
                    payload["expired_at"] = self.now().isoformat()
                    _write_json_atomic(path, payload)
                    continue
                text = self._bounded_text(str(payload.get("text") or ""))
                self.telegram_client.send_message(chat_id, text)
                payload["sent_at"] = self.now().isoformat()
                _write_json_atomic(path, payload)
                delivered += 1
            except json.JSONDecodeError:
                self._quarantine_outbox_path(path, reason="malformed-json", detail="outbox payload is not valid JSON")
                LOGGER.warning("Quarantined malformed Telegram outbox payload %s", path)
            except TerminalOutboxError as exc:
                self._quarantine_outbox_payload(path, reason=exc.reason, detail=str(exc))
                LOGGER.warning("Rejected Telegram outbox payload %s: %s", path, exc)
            except TelegramBridgeError as exc:
                LOGGER.warning("Failed to deliver Telegram outbox message %s: %s", path, exc)
                self._log_incident("telegram-outbox", exc)
            except Exception as exc:
                LOGGER.exception("Failed to deliver Telegram outbox message %s", path)
                self._log_incident("telegram-outbox", exc)
        return delivered

    def enqueue_request(self, update: dict[str, Any], *, chat_id: int, text: str) -> str:
        created_at = self.now().isoformat()
        request_id = f"tg-{self.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:10]}"
        message = (update.get("message") or update.get("edited_message") or {})
        payload = {
            "request_id": request_id,
            "kind": "telegram-orchestration-request",
            "chat_id": chat_id,
            "update_id": update.get("update_id"),
            "message_id": message.get("message_id"),
            "text": self._normalized_request_text(text),
            "raw_text": text,
            "created_at": created_at,
            "status": "pending",
            "reply_via": {
                "transport": "telegram-outbox",
                "outbox_dir": str(self.config.outbox_dir),
            },
        }
        path = self.config.inbox_dir / f"{request_id}.json"
        _write_json_atomic(path, payload)
        return request_id

    @staticmethod
    def extract_chat_and_text(update: dict[str, Any]) -> tuple[int | None, str | None]:
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = message.get("text")
        return int(chat_id) if isinstance(chat_id, int) else None, text if isinstance(text, str) else None

    @staticmethod
    def is_free_form_request(text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return False
        if stripped.startswith("/ask ") or stripped == "/ask":
            return True
        if not stripped.startswith("/"):
            return True
        return False

    def _normalized_request_text(self, text: str) -> str:
        stripped = text.strip()
        if stripped == "/ask":
            return ""
        if stripped.startswith("/ask "):
            return stripped[5:].strip()
        return stripped

    def _bounded_text(self, text: str) -> str:
        bounded = text.strip()[: self.config.message_max_chars]
        return bounded or "(empty reply)"

    def _is_expired(self, payload: dict[str, Any]) -> bool:
        expires_at = payload.get("expires_at")
        if isinstance(expires_at, str) and expires_at:
            return self.now() >= datetime.fromisoformat(expires_at)
        created_at = payload.get("created_at")
        if not isinstance(created_at, str) or not created_at:
            return False
        return (self.now() - datetime.fromisoformat(created_at)).total_seconds() > self.config.outbox_ttl_seconds

    def _pipeline_log_path(self) -> Path:
        return self.project_dir / "pipeline.log.md" if self.project_dir is not None else Path.home() / ".kira-hq" / "global-pipeline.log.md"

    def _log_incident(self, skill: str, exc: Exception) -> None:
        try:
            self.incident_logger("kira-hq", skill, sanitize_telegram_error(str(exc), self.config.bot_token))
        except Exception:
            LOGGER.exception("Telegram incident logging failed for %s", skill)

    def _quarantine_outbox_payload(self, path: Path, *, reason: str, detail: str) -> None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self._quarantine_outbox_path(path, reason=reason, detail=detail)
            return
        payload["status"] = "rejected"
        payload["rejected_at"] = self.now().isoformat()
        payload["reject_reason"] = reason
        payload["reject_detail"] = detail
        target = self.paths.quarantine_dir / path.name
        _write_json_atomic(target, payload)
        path.unlink(missing_ok=True)

    def _quarantine_outbox_path(self, path: Path, *, reason: str, detail: str) -> None:
        target = self.paths.quarantine_dir / path.name
        wrapped = {
            "status": "rejected",
            "rejected_at": self.now().isoformat(),
            "reject_reason": reason,
            "reject_detail": detail,
            "source_path": str(path),
            "raw_payload": path.read_text(encoding="utf-8", errors="replace"),
        }
        _write_json_atomic(target, wrapped)
        path.unlink(missing_ok=True)


__all__ = [
    "DEFAULT_INBOX_DIR",
    "DEFAULT_OFFSET_PATH",
    "DEFAULT_OUTBOX_DIR",
    "LocalApiClient",
    "TelegramBotClient",
    "TelegramBridge",
    "TelegramBridgeConfig",
    "TelegramBridgeError",
    "sanitize_telegram_error",
]
