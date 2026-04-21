"""Pipeline log writer — PRD §6.1.

Append-only markdown-table log. Per-project at `<project>/pipeline.log.md`
plus global aggregate at `~/.kira-hq/global-pipeline.log.md`.

Schema (updated 2026-04-18 per PRD §6.19 token economics):
    timestamp | project | skill | provider | expand_used | tokens_in | tokens_out | status | duration_s | notes
"""
from __future__ import annotations

import fcntl
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

GLOBAL_LOG = Path.home() / ".kira-hq" / "global-pipeline.log.md"

COLUMNS = (
    "timestamp", "project", "skill", "provider", "expand_used",
    "tokens_in", "tokens_out", "status", "duration_s", "notes",
)

HEADER = (
    "| timestamp           | project   | skill                  | provider | expand_used | tokens_in | tokens_out | status | duration_s | notes                |\n"
    "|---------------------|-----------|------------------------|----------|-------------|-----------|------------|--------|------------|----------------------|\n"
)


def _format_value(key: str, value: object) -> str:
    """Render a cell value for the markdown table.

    CRITICAL: Escapes `|` so free-form fields (especially `notes`, and
    anything a future caller might drop in) can't break the 10-column
    layout. Raw `|` inside a cell splits the row, which
    `kira_hq.tokens.parse_log` then rejects as malformed — silently
    losing token rollups and needs-attention signals.

    Also normalises newlines (GFM table cells cannot contain literal
    newlines; replace with a visible `↵` marker so grep still finds
    them).
    """
    if key == "expand_used":
        return "true" if bool(value) else "false"
    if value is None:
        return ""
    s = str(value)
    # GFM escape for pipe inside a table cell
    s = s.replace("|", r"\|")
    # Collapse newlines / CR — tables can't span lines
    s = s.replace("\r\n", " ↵ ").replace("\n", " ↵ ").replace("\r", " ↵ ")
    return s


def append_entry(
    path: Union[str, Path],
    *,
    timestamp: str,
    project: str,
    skill: str,
    provider: str,
    expand_used: bool,
    tokens_in: int,
    tokens_out: int,
    status: str,
    duration_s: float,
    notes: str = "",
) -> None:
    """Append one row to a pipeline log file. Writes header on first append.

    Args:
        path: Log file path. Created with header if absent.
        timestamp: ISO 8601 UTC timestamp.
        project: Project name (matches projects.yaml name).
        skill: Skill/workflow identifier.
        provider: LLM provider (sonnet-4.6, kimi-2.6, qwen3-coder, etc.).
        expand_used: True if provider-aware expand applied (PRD §6.16).
        tokens_in: Input tokens consumed.
        tokens_out: Output tokens generated.
        status: "ok" | "fail" | "skip".
        duration_s: Wall-clock duration in seconds.
        notes: Free-form short note.
    """
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    values = {
        "timestamp": timestamp,
        "project": project,
        "skill": skill,
        "provider": provider,
        "expand_used": expand_used,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "status": status,
        "duration_s": duration_s,
        "notes": notes,
    }
    row = "| " + " | ".join(_format_value(k, values[k]) for k in COLUMNS) + " |\n"
    with p.open("a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.seek(0, os.SEEK_END)
        if f.tell() == 0:
            f.write(HEADER)
        f.write(row)
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def append_global(**fields) -> None:
    """Append to the cross-project aggregate log at ~/.kira-hq/global-pipeline.log.md."""
    append_entry(GLOBAL_LOG, **fields)


def log_execution(
    project_path: Union[str, Path],
    project: str,
    skill: str,
    provider: str,
    expand_used: bool,
    tokens_in: int,
    tokens_out: int,
    status: str,
    duration_s: float,
    notes: str = "",
    timestamp: str | None = None,
) -> None:
    """Convenience: write BOTH per-project and global in one call.

    Per-project log path: <project_path>/pipeline.log.md
    """
    ts = timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")
    kwargs = {
        "timestamp": ts,
        "project": project,
        "skill": skill,
        "provider": provider,
        "expand_used": expand_used,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "status": status,
        "duration_s": duration_s,
        "notes": notes,
    }
    append_entry(Path(project_path).expanduser() / "pipeline.log.md", **kwargs)
    append_global(**kwargs)
