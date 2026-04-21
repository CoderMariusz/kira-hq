"""Token tracking — PRD §6.2.

Aggregates tokens_in/tokens_out from the 10-column v2 pipeline log
(PRD §6.1/§6.19) into daily and weekly roll-ups, plus a per-run budget
check against projects.yaml v2 (`budget_tokens_per_run`).

Cost is NOT tracked (explicit PRD decision — OAuth Claude Max is
unmetered; tokens indicate where compute flows).

Public API:
    parse_log(path)              -> list[LogRow]
    rollup_day(date, path)       -> dict[project, {tokens_in, tokens_out}]
    write_daily_rollup(...)      -> Path to tokens-YYYY-MM-DD.json
    top_n_weekly(week_iso, path) -> list[(project, tokens_in, tokens_out)]
    check_run_budget(project, tokens, projects_yaml) -> bool (True=within)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date as _date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple, Union

PathLike = Union[str, Path]

METRICS_DIR = Path.home() / ".kira-hq" / "metrics"

# Column order must match kira_hq.pipeline_log.COLUMNS (PRD §6.1/§6.19).
_COLUMNS = (
    "timestamp", "project", "skill", "provider", "expand_used",
    "tokens_in", "tokens_out", "status", "duration_s", "notes",
)

# Row lines start with "|" and are NOT the header or separator.
_SEPARATOR_RE = re.compile(r"^\|[\s|:\-]+\|$")


@dataclass
class LogRow:
    timestamp: str
    project: str
    skill: str
    provider: str
    expand_used: str
    tokens_in: int
    tokens_out: int
    status: str
    duration_s: str
    notes: str

    @property
    def date(self) -> str:
        # Accept "2026-04-17T03:00", "2026-04-17T03:00:12", "2026-04-17T03:00:12+00:00"
        return self.timestamp.split("T", 1)[0]


def _split_row(line: str) -> Optional[List[str]]:
    line = line.rstrip("\n")
    if not line.startswith("|") or not line.endswith("|"):
        return None
    if _SEPARATOR_RE.match(line):
        return None
    # Split on unescaped pipes only (`\|` is a literal pipe in a GFM cell).
    # Use a negative-lookbehind regex: split at "|" not preceded by "\".
    # Then un-escape "\|" → "|" in each cell and strip whitespace.
    inner = line[1:-1]
    parts = re.split(r"(?<!\\)\|", inner)
    cells = [p.replace(r"\|", "|").strip() for p in parts]
    return cells


def parse_log(path: PathLike) -> List[LogRow]:
    """Parse a pipeline log markdown table. Returns [] if file missing."""
    p = Path(path).expanduser()
    if not p.exists():
        return []

    rows: List[LogRow] = []
    saw_header = False
    for raw in p.read_text().splitlines():
        cells = _split_row(raw)
        if cells is None:
            continue
        if not saw_header:
            # First data-shaped line is the header row ("| timestamp | ...").
            if cells and cells[0] == "timestamp":
                saw_header = True
                continue
            # Defensive: tolerate files without a header (skip one line).
            saw_header = True
            continue
        if len(cells) != len(_COLUMNS):
            # Skip malformed rows rather than crash the rollup.
            continue
        record = dict(zip(_COLUMNS, cells))
        try:
            tokens_in = int(record["tokens_in"] or 0)
            tokens_out = int(record["tokens_out"] or 0)
        except ValueError:
            continue
        rows.append(
            LogRow(
                timestamp=record["timestamp"],
                project=record["project"],
                skill=record["skill"],
                provider=record["provider"],
                expand_used=record["expand_used"],
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                status=record["status"],
                duration_s=record["duration_s"],
                notes=record["notes"],
            )
        )
    return rows


def rollup_day(day: str, log_path: PathLike) -> Dict[str, Dict[str, int]]:
    """Aggregate tokens per project for a single ISO date (YYYY-MM-DD)."""
    out: Dict[str, Dict[str, int]] = {}
    for row in parse_log(log_path):
        if row.date != day:
            continue
        bucket = out.setdefault(row.project, {"tokens_in": 0, "tokens_out": 0})
        bucket["tokens_in"] += row.tokens_in
        bucket["tokens_out"] += row.tokens_out
    return out


def write_daily_rollup(
    day: str,
    log_path: PathLike,
    metrics_dir: Optional[PathLike] = None,
) -> Path:
    """Compute daily rollup and persist to <metrics_dir>/tokens-<day>.json."""
    data = rollup_day(day, log_path)
    out_dir = Path(metrics_dir).expanduser() if metrics_dir else METRICS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"tokens-{day}.json"
    payload = {"date": day, "projects": data}
    out_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return out_file


def _iso_week_days(week_iso: str) -> List[str]:
    """Expand ISO week string '2026-W16' → 7 ISO dates (Mon..Sun)."""
    year_s, week_s = week_iso.split("-W")
    year, week = int(year_s), int(week_s)
    monday = datetime.fromisocalendar(year, week, 1).date()
    return [(monday + timedelta(days=i)).isoformat() for i in range(7)]


def top_n_weekly(
    week_iso: str,
    log_path: PathLike,
    n: int = 3,
) -> List[Tuple[str, int, int]]:
    """Top N token consumers in a given ISO week (by tokens_in + tokens_out)."""
    totals: Dict[str, Dict[str, int]] = {}
    week_days = set(_iso_week_days(week_iso))
    for row in parse_log(log_path):
        if row.date not in week_days:
            continue
        bucket = totals.setdefault(row.project, {"tokens_in": 0, "tokens_out": 0})
        bucket["tokens_in"] += row.tokens_in
        bucket["tokens_out"] += row.tokens_out
    ranked = sorted(
        totals.items(),
        key=lambda kv: kv[1]["tokens_in"] + kv[1]["tokens_out"],
        reverse=True,
    )
    return [(name, v["tokens_in"], v["tokens_out"]) for name, v in ranked[:n]]


def check_run_budget(
    project_name: str,
    tokens: int,
    projects_yaml: PathLike,
) -> bool:
    """Return True if `tokens` stays within project's per-run budget.

    Reads `budget_tokens_per_run` from projects.yaml v2. If project is
    unknown or budget unset, returns True (no enforcement).
    """
    from kira_hq.projects_yaml import load as load_projects_yaml  # late import
    doc = load_projects_yaml(projects_yaml)
    for entry in doc.projects:
        if entry.name == project_name:
            budget = getattr(entry, "budget_tokens_per_run", None)
            if not budget:
                return True
            return tokens <= budget
    return True


__all__ = [
    "LogRow",
    "METRICS_DIR",
    "parse_log",
    "rollup_day",
    "write_daily_rollup",
    "top_n_weekly",
    "check_run_budget",
]
