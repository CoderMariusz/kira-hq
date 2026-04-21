"""Task 22 Track A weekly parallel-track comparator."""
from __future__ import annotations

import argparse
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kira_hq.pipeline_log import GLOBAL_LOG
from kira_hq.tokens import parse_log

_TRACK_RE = re.compile(r"(?:^|\s)track=(A|B)(?:\s|$)")
_TASKS_RE = re.compile(r"(?:^|\s)tasks_completed=(\d+)(?:\s|$)")
_ALERTS_RE = re.compile(r"(?:^|\s)alerts=(\d+)(?:\s|$)")
_INCIDENT_RE = re.compile(r"(?:^|\s)incident=([^\s]+)")


class TrackSummary:
    def __init__(self, track: str) -> None:
        self.track = track
        self.tasks_completed = 0
        self.tokens = 0
        self.human_interventions = 0
        self.alerts = 0
        self.latency_total = 0.0
        self.runs = 0

    @property
    def avg_latency(self) -> float:
        if self.runs == 0:
            return 0.0
        return round(self.latency_total / self.runs, 1)


def _normalize_timestamp(value: datetime | str) -> datetime:
    ts = datetime.fromisoformat(value) if isinstance(value, str) else value
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _week_window(now: datetime) -> tuple[str, datetime, datetime]:
    now = _normalize_timestamp(now)
    iso_year, iso_week, _ = now.isocalendar()
    start = datetime.fromisocalendar(iso_year, iso_week, 1).replace(tzinfo=UTC)
    end = start + timedelta(days=7)
    return f"{iso_year}-W{iso_week:02d}", start, end


def _extract_metric(pattern: re.Pattern[str], notes: str) -> int:
    match = pattern.search(notes or "")
    return int(match.group(1)) if match else 0


def _extract_track(notes: str) -> str | None:
    match = _TRACK_RE.search(notes or "")
    return match.group(1) if match else None


def _has_human_intervention(notes: str) -> bool:
    return bool(_INCIDENT_RE.search(notes or ""))


def _iter_week_rows(pipeline_log: Path | str, now: datetime) -> Iterable:
    _, start, end = _week_window(now)
    for row in parse_log(pipeline_log):
        ts = _normalize_timestamp(row.timestamp)
        if start <= ts < end:
            yield row


def build_weekly_track_comparison(*, pipeline_log: Path | str = GLOBAL_LOG, now: datetime) -> str:
    week_iso, _, _ = _week_window(now)
    summaries = {track: TrackSummary(track=track) for track in ("A", "B")}

    for row in _iter_week_rows(pipeline_log, now):
        track = _extract_track(row.notes)
        if track not in summaries:
            continue
        summary = summaries[track]
        summary.tasks_completed += _extract_metric(_TASKS_RE, row.notes)
        summary.tokens += row.tokens_in + row.tokens_out
        summary.human_interventions += 1 if _has_human_intervention(row.notes) else 0
        summary.alerts += _extract_metric(_ALERTS_RE, row.notes)
        summary.latency_total += float(row.duration_s)
        summary.runs += 1

    lines = [
        f"# Parallel track comparison — {week_iso}",
        "",
        "| Track | Tasks completed | Tokens | Human interventions | Alerts | Avg latency (s) |",
        "|-------|------------------|--------|---------------------|--------|------------------|",
    ]
    for track in ("A", "B"):
        summary = summaries[track]
        lines.append(
            f"| {track} | {summary.tasks_completed} | {summary.tokens} | "
            f"{summary.human_interventions} | {summary.alerts} | {summary.avg_latency:.1f} |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "- Track is derived from `notes` (`track=A` or `track=B`) without changing pipeline log schema.",
            "- Human interventions are counted from incident references in `notes` (for example `incident=...`).",
        ]
    )
    return "\n".join(lines) + "\n"


def _parse_now(value: str) -> datetime:
    return datetime.fromisoformat(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-log", type=Path, default=GLOBAL_LOG)
    parser.add_argument("--now", type=_parse_now, default=datetime.now(UTC).isoformat())
    args = parser.parse_args(argv)

    markdown = build_weekly_track_comparison(
        pipeline_log=args.pipeline_log,
        now=args.now if isinstance(args.now, datetime) else _parse_now(args.now),
    )
    print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
