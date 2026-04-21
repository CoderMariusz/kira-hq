"""Incidents — PRD §6.3.

Writes `~/.kira-hq/incidents/<ts>-<project>.md` with full context (stderr,
last 50 lines of stdout, exception traceback). One file per incident.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

INCIDENTS_DIR = Path.home() / ".kira-hq" / "incidents"

_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _slug(s: str) -> str:
    return _SLUG_RE.sub("-", s.lower()).strip("-") or "unknown"


@dataclass
class Incident:
    timestamp: str
    project: str
    skill: str
    error: str
    stderr: str
    stdout_tail: str
    path: Path


def _tail(text: str, n: int = 50) -> str:
    lines = text.splitlines()
    return "\n".join(lines[-n:]) if len(lines) > n else text


def write_incident(
    project: str,
    skill: str,
    error: str,
    *,
    stderr: str = "",
    stdout: str = "",
    timestamp: Optional[str] = None,
    incidents_dir: Optional[Union[str, Path]] = None,
) -> Incident:
    """Write one incident .md and return the Incident record."""
    ts = timestamp or datetime.now(timezone.utc).isoformat(timespec="seconds")
    out_dir = Path(incidents_dir).expanduser() if incidents_dir else INCIDENTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # filename-safe timestamp (no colons on common filesystems)
    ts_safe = ts.replace(":", "").replace("+", "Z")
    fname = f"{ts_safe}-{_slug(project)}-{_slug(skill)}.md"
    path = out_dir / fname

    body = (
        f"# Incident: {project}/{skill}\n\n"
        f"- **Timestamp:** {ts}\n"
        f"- **Project:** {project}\n"
        f"- **Skill:** {skill}\n\n"
        f"## Error\n\n```\n{error.strip()}\n```\n\n"
        f"## Stderr\n\n```\n{stderr.strip()}\n```\n\n"
        f"## Stdout (last 50 lines)\n\n```\n{_tail(stdout).strip()}\n```\n"
    )
    path.write_text(body)
    return Incident(
        timestamp=ts, project=project, skill=skill, error=error,
        stderr=stderr, stdout_tail=_tail(stdout), path=path,
    )


def list_recent(
    *,
    since_hours: int = 24,
    incidents_dir: Optional[Union[str, Path]] = None,
) -> list[Incident]:
    """List incident files newer than N hours. Used by needs-attention (T-9)."""
    from datetime import timedelta
    out_dir = Path(incidents_dir).expanduser() if incidents_dir else INCIDENTS_DIR
    if not out_dir.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=since_hours)
    out: list[Incident] = []
    for p in sorted(out_dir.glob("*.md")):
        mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            continue
        out.append(Incident(
            timestamp=mtime.isoformat(timespec="seconds"),
            project="", skill="", error="", stderr="", stdout_tail="",
            path=p,
        ))
    return out


__all__ = ["INCIDENTS_DIR", "Incident", "write_incident", "list_recent"]
