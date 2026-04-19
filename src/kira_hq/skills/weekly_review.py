"""Write a minimal weekly review markdown stub from pipeline logs and snapshots."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable

from kira_hq.pipeline_log import GLOBAL_LOG
from kira_hq.tokens import parse_log


DEFAULT_SNAPSHOTS_DIR = Path.home() / ".kira-hq" / "snapshots"
DEFAULT_REVIEWS_DIR = Path.home() / ".kira-hq" / "reviews"


def _normalize_timestamp(value: datetime | str) -> datetime:
    ts = datetime.fromisoformat(value) if isinstance(value, str) else value
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _week_window(now: datetime) -> tuple[datetime, datetime]:
    now = _normalize_timestamp(now)
    iso_year, iso_week, _ = now.isocalendar()
    start = datetime.fromisocalendar(iso_year, iso_week, 1).replace(tzinfo=now.tzinfo)
    end = start + timedelta(days=7)
    return start, end


def _snapshot_days(now: datetime) -> Iterable[str]:
    start, _ = _week_window(now)
    for offset in range(7):
        yield (start.date() + timedelta(days=offset)).isoformat()


def _top_n_rows(rows: list, n: int = 3) -> list[tuple[str, int, int]]:
    totals: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = totals.setdefault(row.project, {"tokens_in": 0, "tokens_out": 0})
        bucket["tokens_in"] += row.tokens_in
        bucket["tokens_out"] += row.tokens_out
    ranked = sorted(
        totals.items(),
        key=lambda kv: kv[1]["tokens_in"] + kv[1]["tokens_out"],
        reverse=True,
    )
    return [(project, data["tokens_in"], data["tokens_out"]) for project, data in ranked[:n]]


def run_weekly_review(
    *,
    pipeline_log: Path | str,
    snapshots_dir: Path | str,
    reviews_dir: Path | str,
    now: datetime,
    projects_yaml: Path | None,
) -> Path:
    del projects_yaml  # reserved for T-24 expansion
    now = _normalize_timestamp(now)
    pipeline_log = Path(pipeline_log)
    snapshots_dir = Path(snapshots_dir)
    reviews_dir = Path(reviews_dir)
    reviews_dir.mkdir(parents=True, exist_ok=True)

    iso_year, iso_week, _ = now.isocalendar()
    week_iso = f"{iso_year}-W{iso_week:02d}"
    out_path = reviews_dir / f"{week_iso}.md"

    start, end = _week_window(now)
    rows = []
    for row in parse_log(pipeline_log):
        ts = _normalize_timestamp(row.timestamp)
        if start <= ts < end:
            rows.append(row)

    top3 = _top_n_rows(rows, n=3)
    projects = sorted({row.project for row in rows})
    snapshot_count = sum(1 for day in _snapshot_days(now) if (snapshots_dir / day).exists())

    window_label = f"{start.date().isoformat()} to {(end.date() - timedelta(days=1)).isoformat()}"
    lines = [f"# Weekly review {week_iso}", "", f"Reporting window: {window_label}", ""]
    lines.extend(["## Top-3 token consumers"])
    if top3:
        for project, tokens_in, tokens_out in top3:
            runs = sum(1 for row in rows if row.project == project)
            lines.append(f"- {project}: in={tokens_in}, out={tokens_out}, runs={runs}")
    else:
        lines.append("- none")

    lines.extend(["", "## Cron success"])
    if projects:
        for project in projects:
            ok = sum(1 for row in rows if row.project == project and row.status == "ok")
            fail = sum(1 for row in rows if row.project == project and row.status == "fail")
            lines.append(f"- {project}: {ok} ok / {fail} fail")
    else:
        lines.append("- none")

    lines.extend(["", "## Snapshot health", f"- {snapshot_count}/7 days present"])
    lines.extend([
        "",
        "## Parallel track",
        "- Placeholder for Path A Hermes vs Path B Claude Code weekly comparison (T-24).",
    ])

    out_path.write_text("\n".join(lines) + "\n")
    return out_path


def _parse_now(value: str) -> datetime:
    return datetime.fromisoformat(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-log", type=Path, default=GLOBAL_LOG)
    parser.add_argument("--snapshots-dir", type=Path, default=DEFAULT_SNAPSHOTS_DIR)
    parser.add_argument("--reviews-dir", type=Path, default=DEFAULT_REVIEWS_DIR)
    parser.add_argument("--now", type=_parse_now, default=datetime.now().astimezone().isoformat())
    parser.add_argument("--projects-yaml", type=Path, default=None)
    args = parser.parse_args(argv)

    out = run_weekly_review(
        pipeline_log=args.pipeline_log,
        snapshots_dir=args.snapshots_dir,
        reviews_dir=args.reviews_dir,
        now=args.now if isinstance(args.now, datetime) else _parse_now(args.now),
        projects_yaml=args.projects_yaml,
    )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
