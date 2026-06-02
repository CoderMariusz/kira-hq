"""Claude -> Hermes(worker) -> OpenRouter/Qwen bridge.

The bridge is deliberately neutral/shared: Claude calls `kira-hq delegate-worker`
instead of shelling directly to a bespoke Hermes-only path. This keeps one repo
entrypoint, one handoff shape, and one shared substrate.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kira_hq.handoff import parse_handoff
from kira_hq.pipeline_log import log_execution
from kira_hq.secrets_schema import load_secrets

DEFAULT_BRIDGE_MODEL = "qwen/qwen3-coder-30b-a3b-instruct"
DEFAULT_BRIDGE_PROVIDER = "openrouter"
DEFAULT_WORKER_NAME = "hermes-qwen-worker"
ENV_STRIP_KEYS = {
    "CLAUDECODE",
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_CODE_EXECPATH",
    "ANTHROPIC_API_KEY",
}


class BridgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class BridgeRequest:
    task_id: str
    prompt: str
    project_dir: Path
    handoff_out: Path
    worker_command: str = "hermes"
    provider: str = DEFAULT_BRIDGE_PROVIDER
    model: str = DEFAULT_BRIDGE_MODEL
    skill: str = "kira-hq-hermes-worker"
    track: str = "B"
    worker_name: str = DEFAULT_WORKER_NAME
    project_name: str | None = None
    global_pipeline_log: Path | None = None
    log_to_default_global: bool = True


@dataclass(frozen=True)
class BridgeResult:
    handoff: dict[str, Any]
    stdout: str
    stderr: str
    returncode: int
    command: list[str]


def sanitized_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key not in ENV_STRIP_KEYS}
    if extra:
        env.update(extra)
    return env


def build_query(request: BridgeRequest) -> str:
    return (
        "You are the Hermes worker for Kira-HQ. "
        "Return only Stage-1 handoff JSON, no markdown fences, no preamble. "
        f"task_id={request.task_id}. "
        f"worktree={request.project_dir}. lane=claude-hermes-qwen. worker={request.worker_name}. "
        "step=1. status=completed on success, failed on failure. "
        "List changed files under files[] with intent strings. "
        f"Write artifacts under .hermes/artifacts/{request.task_id}/ if needed. "
        f"Delegated work request: {request.prompt.strip()}"
    )


def build_command(request: BridgeRequest) -> list[str]:
    return [
        request.worker_command,
        "chat",
        "-q",
        build_query(request),
        "--provider",
        request.provider,
        "--model",
        request.model,
        "--source",
        "tool",
        "-Q",
    ]


def _write_handoff(path: Path, payload: dict[str, Any]) -> None:
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
    tmp_path = Path(tmp_name)
    tmp_path.chmod(0o600)
    tmp_path.replace(path)
    path.chmod(0o600)


def _load_bridge_secret(request: BridgeRequest, key: str) -> str | None:
    project_root = request.project_dir.expanduser().resolve()
    secrets = load_secrets(project_root.name, projects_root=project_root.parent)
    if key in os.environ:
        return os.environ.get(key)
    return secrets.get(key)


def invoke_bridge(request: BridgeRequest) -> BridgeResult:
    if not request.task_id.strip():
        raise BridgeError("task_id is required")
    if not request.prompt.strip():
        raise BridgeError("prompt is required")
    if not request.project_dir.exists():
        raise BridgeError(f"project_dir does not exist: {request.project_dir}")
    if not request.project_dir.is_dir():
        raise BridgeError(f"project_dir is not a directory: {request.project_dir}")
    openrouter_key = _load_bridge_secret(request, "OPENROUTER_API_KEY")
    if request.provider == "openrouter" and not openrouter_key:
        raise BridgeError("OPENROUTER_API_KEY is not set; Hermes OpenRouter/Qwen route is unavailable")

    command = build_command(request)
    env = sanitized_env({"KIRA_HQ_TRACK": request.track})
    if openrouter_key:
        env["OPENROUTER_API_KEY"] = openrouter_key
    result = None
    try:
        result = subprocess.run(
            command,
            cwd=str(request.project_dir),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise BridgeError(f"Hermes worker command not found: {request.worker_command}") from exc
    if result.returncode != 0:
        raise BridgeError(result.stderr.strip() or result.stdout.strip() or "Hermes worker invocation failed")

    parsed = parse_handoff(result.stdout.strip())
    payload = parsed.model_dump()
    _write_handoff(request.handoff_out, payload)

    project_name = request.project_name or request.project_dir.name
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    notes = f"track={request.track}; handoff={request.handoff_out}; worker={request.worker_command}"
    if request.log_to_default_global:
        log_execution(
            request.project_dir,
            project=project_name,
            skill=request.skill,
            provider="qwen3-coder",
            expand_used=False,
            tokens_in=0,
            tokens_out=0,
            status="ok",
            duration_s=0.0,
            notes=notes,
            timestamp=timestamp,
        )
    else:
        from kira_hq.pipeline_log import append_entry

        append_entry(
            request.project_dir / "pipeline.log.md",
            timestamp=timestamp,
            project=project_name,
            skill=request.skill,
            provider="qwen3-coder",
            expand_used=False,
            tokens_in=0,
            tokens_out=0,
            status="ok",
            duration_s=0.0,
            notes=notes,
        )
    if request.global_pipeline_log is not None:
        # `log_execution` already writes the user's real global log; this optional
        # fixture-specific path is for tests and bounded validation.
        from kira_hq.pipeline_log import append_entry

        append_entry(
            request.global_pipeline_log,
            timestamp=timestamp,
            project=project_name,
            skill=request.skill,
            provider="qwen3-coder",
            expand_used=False,
            tokens_in=0,
            tokens_out=0,
            status="ok",
            duration_s=0.0,
            notes=notes,
        )

    return BridgeResult(
        handoff=payload,
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
        command=command,
    )
