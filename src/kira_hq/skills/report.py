"""Generate post-cycle report summaries from pipeline logs."""
from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kira_hq.pipeline_log import GLOBAL_LOG, append_entry
from kira_hq.tokens import parse_log


_SYNTHETIC_SKILLS = {"kira-hq-report", "kira-weekly-review"}


def _parse_since(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _normalize_timestamp(value: datetime | str) -> datetime:
    ts = datetime.fromisoformat(value) if isinstance(value, str) else value
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def _is_synthetic_observability_row(*, project: str, skill: str) -> bool:
    return project == "kira-hq" and skill in _SYNTHETIC_SKILLS


def generate_report_json(pipeline_log: Path | str, *, since: datetime) -> dict[str, Any]:
    """Return a JSON-serialisable summary of runs since the given timestamp."""
    since = _normalize_timestamp(since)
    rows = []
    blockers = []
    for row in parse_log(pipeline_log):
        ts = _normalize_timestamp(row.timestamp)
        if ts < since:
            continue
        if _is_synthetic_observability_row(project=row.project, skill=row.skill):
            continue
        item = {
            "timestamp": row.timestamp,
            "project": row.project,
            "skill": row.skill,
            "provider": row.provider,
            "tokens_in": row.tokens_in,
            "tokens_out": row.tokens_out,
            "status": row.status,
            "notes": row.notes,
        }
        rows.append(item)
        if row.status == "fail":
            blockers.append({
                "timestamp": row.timestamp,
                "project": row.project,
                "skill": row.skill,
                "notes": row.notes,
            })

    return {
        "changes_since": since.isoformat(),
        "runs": len(rows),
        "failures": len(blockers),
        "blockers": blockers,
        "token_delta": {
            "tokens_in": sum(row["tokens_in"] for row in rows),
            "tokens_out": sum(row["tokens_out"] for row in rows),
        },
        "projects": sorted({row["project"] for row in rows}),
        "items": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pipeline-log", type=Path, default=GLOBAL_LOG)
    parser.add_argument("--since", required=True, type=_parse_since)
    args = parser.parse_args(argv)

    started = time.monotonic()
    payload = generate_report_json(args.pipeline_log, since=args.since)
    append_entry(
        args.pipeline_log,
        timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
        project="kira-hq",
        skill="kira-hq-report",
        provider="hermes",
        expand_used=False,
        tokens_in=0,
        tokens_out=0,
        status="ok",
        duration_s=round(time.monotonic() - started, 3),
        notes=(
            f"summary runs={payload['runs']} blockers={len(payload['blockers'])} "
            f"delta_in={payload['token_delta']['tokens_in']} delta_out={payload['token_delta']['tokens_out']}"
        ),
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
