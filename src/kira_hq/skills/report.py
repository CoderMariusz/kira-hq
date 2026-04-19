"""Generate post-cycle report summaries from pipeline logs."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from kira_hq.pipeline_log import GLOBAL_LOG
from kira_hq.tokens import parse_log


def _parse_since(value: str) -> datetime:
    return datetime.fromisoformat(value)


def generate_report_json(pipeline_log: Path | str, *, since: datetime) -> dict[str, Any]:
    """Return a JSON-serialisable summary of runs since the given timestamp."""
    rows = []
    for row in parse_log(pipeline_log):
        ts = datetime.fromisoformat(row.timestamp)
        if ts < since:
            continue
        rows.append({
            "timestamp": row.timestamp,
            "project": row.project,
            "skill": row.skill,
            "provider": row.provider,
            "tokens_in": row.tokens_in,
            "tokens_out": row.tokens_out,
            "status": row.status,
            "notes": row.notes,
        })

    return {
        "changes_since": since.isoformat(),
        "runs": len(rows),
        "failures": sum(1 for row in rows if row["status"] == "fail"),
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

    payload = generate_report_json(args.pipeline_log, since=args.since)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
