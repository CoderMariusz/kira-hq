"""Weekly review ritual skill — PRD §4.M4 + §6.18."""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Callable, Iterable

from kira_hq.pipeline_log import GLOBAL_LOG, append_entry
from kira_hq.projects_yaml import load as load_projects
from kira_hq.tokens import LogRow, parse_log

DEFAULT_SNAPSHOTS_DIR = Path.home() / ".kira-hq" / "snapshots"
DEFAULT_REVIEWS_DIR = Path.home() / ".kira-hq" / "reviews"
_SYNTHETIC_SKILLS = {"kira-hq-report", "kira-weekly-review"}

_TRACK_RE = re.compile(r"(?:^|\s)track=(A|B)(?:\s|$)")
_TASKS_RE = re.compile(r"(?:^|\s)tasks_completed=(\d+)(?:\s|$)")
_ALERTS_RE = re.compile(r"(?:^|\s)alerts=(\d+)(?:\s|$)")
_INCIDENT_RE = re.compile(r"(?:^|\s)incident=([^\s]+)")


@dataclass
class ProjectTasksSnapshot:
    blockers: int = 0
    needs_human: int = 0


@dataclass
class ParallelSummary:
    track: str
    tasks: int = 0
    tokens: int = 0
    human_interventions: int = 0
    alerts: int = 0
    latency_total: float = 0.0
    runs: int = 0

    @property
    def avg_latency_s(self) -> float:
        if self.runs == 0:
            return 0.0
        return round(self.latency_total / self.runs, 1)


@dataclass
class ReviewArtifacts:
    path: Path
    telegram_summary_path: Path
    telegram_summary: str


def _normalize_timestamp(value: datetime | str) -> datetime:
    ts = datetime.fromisoformat(value) if isinstance(value, str) else value
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _week_window(now: datetime) -> tuple[datetime, datetime]:
    now = _normalize_timestamp(now)
    iso_year, iso_week, _ = now.isocalendar()
    start = datetime.fromisocalendar(iso_year, iso_week, 1).replace(tzinfo=UTC)
    end = start + timedelta(days=7)
    return start, end


def _week_label(now: datetime) -> str:
    now = _normalize_timestamp(now)
    iso_year, iso_week, _ = now.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _snapshot_days(now: datetime) -> Iterable[str]:
    start, _ = _week_window(now)
    for offset in range(7):
        yield (start.date() + timedelta(days=offset)).isoformat()


def _extract_int(pattern: re.Pattern[str], notes: str) -> int:
    match = pattern.search(notes or "")
    return int(match.group(1)) if match else 0


def _extract_track(notes: str) -> str | None:
    match = _TRACK_RE.search(notes or "")
    return match.group(1) if match else None


def _has_human_intervention(notes: str) -> bool:
    return bool(_INCIDENT_RE.search(notes or ""))


def _row_tokens(row: LogRow) -> int:
    return row.tokens_in + row.tokens_out


def _is_synthetic_observability_row(row: LogRow) -> bool:
    return row.project == "kira-hq" and row.skill in _SYNTHETIC_SKILLS


def _read_tasks(project_path: str | Path) -> list[dict]:
    task_file = Path(project_path).expanduser() / ".taskmaster" / "tasks" / "tasks.json"
    if not task_file.exists():
        return []
    try:
        data = json.loads(task_file.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, dict):
        if isinstance(data.get("tasks"), list):
            return data["tasks"]
        if isinstance(data.get("master"), dict) and isinstance(data["master"].get("tasks"), list):
            return data["master"]["tasks"]
        for value in data.values():
            if isinstance(value, dict) and isinstance(value.get("tasks"), list):
                return value["tasks"]
    return []


def _load_project_snapshots(projects_yaml: Path | None) -> tuple[dict[str, ProjectTasksSnapshot], list[tuple[str, str, str]]]:
    if projects_yaml is None or not Path(projects_yaml).exists():
        return {}, []

    doc = load_projects(projects_yaml)
    snapshots: dict[str, ProjectTasksSnapshot] = {}
    stale_projects: list[tuple[str, str, str]] = []

    for project in doc.projects:
        tasks = _read_tasks(project.path)
        blockers = 0
        needs_human = 0
        for task in tasks:
            if not isinstance(task, dict):
                continue
            status = str(task.get("status", "")).lower()
            if status == "blocked":
                blockers += 1
            if status in {"needs-human", "needs_human"}:
                needs_human += 1
        snapshots[project.name] = ProjectTasksSnapshot(blockers=blockers, needs_human=needs_human)
        if project.status == "stale":
            stale_projects.append(
                (
                    project.name,
                    "none",
                    f"/unstale {project.name} after human review",
                )
            )

    return snapshots, stale_projects


def _group_rows_by_project(rows: list[LogRow]) -> dict[str, list[LogRow]]:
    grouped: dict[str, list[LogRow]] = {}
    for row in rows:
        grouped.setdefault(row.project, []).append(row)
    return grouped


def _token_totals(rows: list[LogRow]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for row in rows:
        totals[row.project] = totals.get(row.project, 0) + _row_tokens(row)
    return totals


def _format_delta(delta: int) -> str:
    return f"+{delta}" if delta >= 0 else str(delta)


def _parallel_summaries(rows: list[LogRow]) -> dict[str, ParallelSummary]:
    summaries = {track: ParallelSummary(track=track) for track in ("A", "B")}
    for row in rows:
        track = _extract_track(row.notes)
        if track not in summaries:
            continue
        summary = summaries[track]
        summary.tasks += _extract_int(_TASKS_RE, row.notes)
        summary.tokens += _row_tokens(row)
        summary.human_interventions += 1 if _has_human_intervention(row.notes) else 0
        summary.alerts += _extract_int(_ALERTS_RE, row.notes)
        try:
            summary.latency_total += float(row.duration_s)
        except ValueError:
            summary.latency_total += 0.0
        summary.runs += 1
    return summaries


def _autolearn_section_lines(now: datetime) -> list[str]:
    del now
    api_url = os.environ.get("HERMES_API_URL")
    if not api_url:
        return ["- unavailable (Hermes API absent)"]
    return [f"- unavailable (Hermes API configured at {api_url!r} but live fetch is unsupported in this worker)"]


def _review_markdown(
    *,
    pipeline_log: Path,
    snapshots_dir: Path,
    now: datetime,
    projects_yaml: Path | None,
    telegram_summary_path: Path,
    parallel_tracks_enabled: bool | None,
) -> str:
    now = _normalize_timestamp(now)
    week_iso = _week_label(now)
    start, end = _week_window(now)
    previous_week_iso = _week_label(start - timedelta(days=1))
    window_label = f"{start.date().isoformat()} to {(end.date() - timedelta(days=1)).isoformat()}"

    current_rows = []
    previous_rows = []
    prev_start, prev_end = _week_window(start - timedelta(days=1))
    for row in parse_log(pipeline_log):
        if _is_synthetic_observability_row(row):
            continue
        ts = _normalize_timestamp(row.timestamp)
        if start <= ts < end:
            current_rows.append(row)
        elif prev_start <= ts < prev_end:
            previous_rows.append(row)

    rows_by_project = _group_rows_by_project(current_rows)
    project_snapshots, stale_projects = _load_project_snapshots(projects_yaml)

    tasks_completed: dict[str, int] = {}
    for row in current_rows:
        tasks_completed[row.project] = tasks_completed.get(row.project, 0) + _extract_int(_TASKS_RE, row.notes)

    current_tokens = _token_totals(current_rows)
    previous_tokens = _token_totals(previous_rows)
    token_projects = sorted(current_tokens)
    top3 = sorted(current_tokens.items(), key=lambda item: item[1], reverse=True)[:3]

    all_task_projects = sorted(set(tasks_completed) | set(project_snapshots))
    cron_projects = sorted(rows_by_project)
    summaries = _parallel_summaries(current_rows)

    present_days = [day for day in _snapshot_days(now) if (snapshots_dir / day).exists()]
    missing_days = [day for day in _snapshot_days(now) if day not in set(present_days)]

    lines = [
        f"# Weekly review {week_iso}",
        "",
        f"Reporting window: {window_label}",
        f"Telegram summary artifact: {telegram_summary_path}",
        "",
        "## 1) Tasks",
    ]
    if all_task_projects:
        for project in all_task_projects:
            snapshot = project_snapshots.get(project, ProjectTasksSnapshot())
            lines.append(
                f"- {project}: completed={tasks_completed.get(project, 0)}, "
                f"blockers={snapshot.blockers}, needs-human={snapshot.needs_human}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## 2) Tokens"])
    if token_projects:
        for project in token_projects:
            total = current_tokens.get(project, 0)
            delta = total - previous_tokens.get(project, 0)
            lines.append(f"- {project}: total={total} (Δ {_format_delta(delta)} vs {previous_week_iso})")
        if top3:
            top3_rendered = ", ".join(f"{project}={total}" for project, total in top3)
            lines.append(f"- Top-3: {top3_rendered}")
    else:
        lines.append("- none")

    lines.extend(["", "## 3) Cron"])
    if cron_projects:
        for project in cron_projects:
            project_rows = rows_by_project[project]
            total_runs = len(project_rows)
            ok_runs = sum(1 for row in project_rows if str(row.status).lower() == "ok")
            success_rate = 0.0 if total_runs == 0 else round((ok_runs / total_runs) * 100, 1)
            failed_runs = [
                f"{row.timestamp} {row.skill}"
                for row in project_rows
                if str(row.status).lower() != "ok"
            ]
            failed_text = ", ".join(failed_runs) if failed_runs else "none"
            lines.append(
                f"- {project}: {success_rate:.1f}% success ({ok_runs}/{total_runs}), failed runs: {failed_text}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## 4) Parallel track A vs B"])
    if parallel_tracks_enabled is False:
        lines.append("- disabled by config")
    elif summaries["A"].runs == 0 and summaries["B"].runs == 0:
        lines.append("- inactive this week (no track=A/track=B evaluation rows)")
    else:
        for track in ("A", "B"):
            summary = summaries[track]
            lines.append(
                f"- Track {track}: tasks={summary.tasks}, tokens={summary.tokens}, "
                f"human_interventions={summary.human_interventions}, alerts={summary.alerts}, "
                f"avg_latency_s={summary.avg_latency_s:.1f}"
            )

    lines.extend(["", "## 5) Snapshot health"])
    lines.append(f"- Present: {len(present_days)}/7 days")
    if len(missing_days) >= 2:
        lines.append(f"- ALERT: missed {len(missing_days)} day(s): {', '.join(missing_days)}")
    elif missing_days:
        lines.append(f"- Missed: {', '.join(missing_days)}")
    else:
        lines.append("- Healthy: no missed days")

    lines.extend(["", "## 6) Stale projects + suggested action"])
    if stale_projects:
        for name, last_activity, suggestion in stale_projects:
            lines.append(
                f"- {name}: status=stale, last_activity={last_activity}, suggested_action={suggestion}"
            )
    else:
        lines.append("- none")

    lines.extend(["", "## 7) Hermes autolearn delta"])
    lines.extend(_autolearn_section_lines(now))
    lines.append("")
    return "\n".join(lines)


def build_telegram_summary(review_path: Path | str, *, max_chars: int = 700) -> str:
    path = Path(review_path)
    text = path.read_text().splitlines()
    summary_lines: list[str] = []
    for line in text:
        if not line.strip():
            continue
        summary_lines.append(line)
        if line.startswith("## 2)"):
            break
    summary = "\n".join(summary_lines)
    summary = f"{summary}\nFull review: {path}"
    if len(summary) <= max_chars:
        return summary
    trimmed = summary[: max_chars - 4].rstrip()
    return trimmed + " ..."


def run_weekly_review(
    *,
    pipeline_log: Path | str,
    snapshots_dir: Path | str,
    reviews_dir: Path | str,
    now: datetime,
    projects_yaml: Path | None,
    parallel_tracks_enabled: bool | None = None,
) -> ReviewArtifacts:
    now = _normalize_timestamp(now)
    pipeline_log = Path(pipeline_log)
    snapshots_dir = Path(snapshots_dir)
    reviews_dir = Path(reviews_dir)
    reviews_dir.mkdir(parents=True, exist_ok=True)

    out_path = reviews_dir / f"{_week_label(now)}.md"
    telegram_summary_path = reviews_dir / f"{_week_label(now)}.telegram.txt"
    out_path.write_text(
        _review_markdown(
            pipeline_log=pipeline_log,
            snapshots_dir=snapshots_dir,
            now=now,
            projects_yaml=Path(projects_yaml) if projects_yaml is not None else None,
            telegram_summary_path=telegram_summary_path,
            parallel_tracks_enabled=parallel_tracks_enabled,
        )
    )
    telegram_summary = build_telegram_summary(out_path)
    telegram_summary_path.write_text(telegram_summary)
    return ReviewArtifacts(
        path=out_path,
        telegram_summary_path=telegram_summary_path,
        telegram_summary=telegram_summary,
    )


def _parse_now(value: str) -> datetime:
    return datetime.fromisoformat(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-log", type=Path, default=GLOBAL_LOG)
    parser.add_argument("--snapshots-dir", type=Path, default=DEFAULT_SNAPSHOTS_DIR)
    parser.add_argument("--reviews-dir", type=Path, default=DEFAULT_REVIEWS_DIR)
    parser.add_argument("--now", type=_parse_now, default=datetime.now().astimezone().isoformat())
    parser.add_argument("--projects-yaml", type=Path, default=None)
    parser.add_argument(
        "--parallel-tracks",
        choices=("auto", "on", "off"),
        default="auto",
        help="auto=render when track rows exist, on=always render section, off=disable section metrics",
    )
    args = parser.parse_args(argv)

    parallel_tracks_enabled = {
        "auto": None,
        "on": True,
        "off": False,
    }[args.parallel_tracks]

    started = time.monotonic()
    artifacts = run_weekly_review(
        pipeline_log=args.pipeline_log,
        snapshots_dir=args.snapshots_dir,
        reviews_dir=args.reviews_dir,
        now=args.now if isinstance(args.now, datetime) else _parse_now(args.now),
        projects_yaml=args.projects_yaml,
        parallel_tracks_enabled=parallel_tracks_enabled,
    )
    append_entry(
        args.pipeline_log,
        timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
        project="kira-hq",
        skill="kira-weekly-review",
        provider="hermes",
        expand_used=False,
        tokens_in=0,
        tokens_out=0,
        status="ok",
        duration_s=round(time.monotonic() - started, 3),
        notes=f"wrote {artifacts.path}; telegram_summary={artifacts.telegram_summary_path}",
    )
    print(artifacts.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
