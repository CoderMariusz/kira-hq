"""GET /metrics/tokens, GET /metrics/pipeline — PRD §6.1 + §6.2."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _parse_since(since: Optional[str]) -> Optional[datetime]:
    if not since:
        return None
    # Accept YYYY-MM-DD or full ISO 8601
    try:
        return datetime.fromisoformat(since)
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=f"invalid 'since' (use YYYY-MM-DD or ISO 8601): {e}",
        ) from e


@router.get("/tokens")
def tokens(
    request: Request,
    since: Optional[str] = Query(None, description="YYYY-MM-DD lower bound"),
) -> Dict[str, Any]:
    """Aggregate tokens_in/out per project from the global pipeline log.

    Roll-up windows from `since` (inclusive) up to today. If `since` is
    absent, defaults to 30 days back to keep payloads bounded.
    """
    from kira_hq.tokens import rollup_day  # late import

    log_path = request.app.state.pipeline_log_loader()
    if not Path(log_path).exists():
        return {"since": since, "log": str(log_path), "projects": {}}

    end = datetime.utcnow().date()
    if since:
        start = _parse_since(since).date()
    else:
        start = end - timedelta(days=30)

    aggregate: Dict[str, Dict[str, int]] = {}
    day = start
    while day <= end:
        per_day = rollup_day(day.isoformat(), log_path)
        for proj, totals in per_day.items():
            bucket = aggregate.setdefault(
                proj, {"tokens_in": 0, "tokens_out": 0}
            )
            bucket["tokens_in"] += totals["tokens_in"]
            bucket["tokens_out"] += totals["tokens_out"]
        day += timedelta(days=1)
    return {
        "since": start.isoformat(),
        "until": end.isoformat(),
        "log": str(log_path),
        "projects": aggregate,
    }


@router.get("/pipeline")
def pipeline(
    request: Request,
    since: Optional[str] = Query(None, description="ISO 8601 lower bound"),
) -> List[Dict[str, Any]]:
    """Return raw pipeline log rows ≥ `since` — PRD §6.1.

    Provides direct visibility into skill invocation history (provider used,
    expand_used flag, durations, status). The frontend tail-views this for
    debugging cron behaviour.
    """
    from kira_hq.tokens import parse_log  # late import (reuses LogRow parser)

    log_path = request.app.state.pipeline_log_loader()
    if not Path(log_path).exists():
        return []
    bound = _parse_since(since)
    rows: List[Dict[str, Any]] = []
    for r in parse_log(log_path):
        try:
            ts = datetime.fromisoformat(r.timestamp)
        except ValueError:
            continue
        if bound and ts < bound:
            continue
        rows.append({
            "timestamp": r.timestamp,
            "project": r.project,
            "skill": r.skill,
            "provider": r.provider,
            "expand_used": r.expand_used,
            "tokens_in": r.tokens_in,
            "tokens_out": r.tokens_out,
            "status": r.status,
            "duration_s": r.duration_s,
            "notes": r.notes,
        })
    return rows
