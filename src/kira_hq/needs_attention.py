"""Needs-attention algorithm — PRD §6.10.

Aggregates 5 trigger conditions into a single ~/.kira-hq/needs-attention.md
report that Module 2 (/views/needs-attention) consumes.

Triggers:
    1. Task status=blocked for >48h (from task updated_at)
    2. Task priority=high AND status=pending for >72h
    3. Task status=needs-human
    4. Project has FAIL cron run in last 24h (from pipeline log T-1)
    5. Project sum(tokens_in+tokens_out) last 30d > budget_tokens_monthly
       (from pipeline log + projects.yaml v2 budgets)

Public API:
    compute(now, projects_yaml, pipeline_log, metrics_dir=None, tasks_loader=None)
        -> NeedsAttentionReport
    render(report) -> str
    write(report, path=None) -> Path
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Union

PathLike = Union[str, Path]

DEFAULT_OUTPUT = Path.home() / ".kira-hq" / "needs-attention.md"

# Match the pipeline log's FAIL marker. T-11 writes "FAIL" for failed crons.
_FAIL_STATUSES = {"FAIL", "FAILED", "fail", "failed", "error", "ERROR"}


# ---------- data types ----------


@dataclass
class BlockedItem:
    project: str
    task_id: str
    title: str
    blocked_by: str
    hours: int


@dataclass
class StaleHighItem:
    project: str
    task_id: str
    title: str
    hours: int


@dataclass
class NeedsHumanItem:
    project: str
    task_id: str
    title: str


@dataclass
class FailedCronItem:
    project: str
    skill: str
    timestamp: str
    incident: Optional[str] = None


@dataclass
class BudgetItem:
    project: str
    tokens_used: int
    budget: int


@dataclass
class NeedsAttentionReport:
    generated_at: str
    blocked: List[BlockedItem] = field(default_factory=list)
    high_prio_stale: List[StaleHighItem] = field(default_factory=list)
    needs_human: List[NeedsHumanItem] = field(default_factory=list)
    failed_crons: List[FailedCronItem] = field(default_factory=list)
    budget_exceeded: List[BudgetItem] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not (
            self.blocked
            or self.high_prio_stale
            or self.needs_human
            or self.failed_crons
            or self.budget_exceeded
        )


# ---------- helpers ----------


def _parse_ts(s: str) -> Optional[datetime]:
    """Accept 2026-04-17, 2026-04-17T03:00, 2026-04-17T03:00:12, with or without tz."""
    if not s:
        return None
    s = s.strip()
    # normalize trailing Z to +00:00
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M%z",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    # last-ditch: ISO
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _hours_between(a: datetime, b: datetime) -> int:
    return int((a - b).total_seconds() // 3600)


def default_tasks_loader(project_path: PathLike) -> List[dict]:
    """Read <project_path>/.taskmaster/tasks/tasks.json and return the task list.

    Supports both the top-level `{"tasks": [...]}` shape and the newer
    `{"master": {"tasks": [...]}}` shape task-master writes.
    Returns [] if the file is missing / unreadable.
    """
    p = Path(project_path).expanduser() / ".taskmaster" / "tasks" / "tasks.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, dict):
        if "tasks" in data and isinstance(data["tasks"], list):
            return data["tasks"]
        # tagged format: {"master": {"tasks": [...]}}, {"feature-x": {...}}
        # Prefer "master" if present; otherwise flatten the first tag we find.
        if "master" in data and isinstance(data["master"], dict):
            t = data["master"].get("tasks", [])
            return t if isinstance(t, list) else []
        for v in data.values():
            if isinstance(v, dict) and isinstance(v.get("tasks"), list):
                return v["tasks"]
    return []


# ---------- core ----------


def compute(
    now: datetime,
    projects_yaml: PathLike,
    pipeline_log: PathLike,
    metrics_dir: Optional[PathLike] = None,  # reserved for future use; PRD §6.2
    tasks_loader: Optional[Callable[[str], List[dict]]] = None,
) -> NeedsAttentionReport:
    """Compute all 5 triggers and return the aggregated report."""
    from kira_hq.projects_yaml import load as load_projects  # late import
    from kira_hq.tokens import parse_log  # late import

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    loader = tasks_loader or default_tasks_loader

    report = NeedsAttentionReport(
        generated_at=now.strftime("%Y-%m-%dT%H:%M:%S"),
    )

    doc = load_projects(projects_yaml)
    active_projects = [p for p in doc.projects if p.status == "active"]

    # --- triggers 1/2/3: per-task inspection ---
    for proj in active_projects:
        try:
            tasks = loader(proj.path)
        except Exception:
            tasks = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            status = str(task.get("status", "")).lower()
            priority = str(task.get("priority", "")).lower()
            task_id = str(task.get("id", "?"))
            title = str(task.get("title", "")).strip() or "(untitled)"
            updated_at = _parse_ts(str(task.get("updated_at") or task.get("updatedAt") or ""))

            # Trigger 3: needs-human (no time check)
            if status in {"needs-human", "needs_human"}:
                report.needs_human.append(NeedsHumanItem(proj.name, task_id, title))

            if updated_at is None:
                continue
            age_h = _hours_between(now, updated_at)
            # Trigger 1: blocked >48h
            if status == "blocked" and age_h > 48:
                deps = task.get("dependencies") or task.get("blocked_by") or []
                blocked_by = (
                    ",".join(str(d) for d in deps) if isinstance(deps, (list, tuple))
                    else str(deps)
                )
                report.blocked.append(
                    BlockedItem(proj.name, task_id, title, blocked_by or "?", age_h)
                )
            # Trigger 2: high-prio pending >72h
            if priority == "high" and status == "pending" and age_h > 72:
                report.high_prio_stale.append(
                    StaleHighItem(proj.name, task_id, title, age_h)
                )

    # --- trigger 4: failed crons in last 24h (from pipeline log) ---
    cutoff_24h = now - timedelta(hours=24)
    rows = parse_log(pipeline_log)
    for row in rows:
        if row.status not in _FAIL_STATUSES:
            continue
        ts = _parse_ts(row.timestamp)
        if ts is None or ts < cutoff_24h:
            continue
        # Extract incident reference from notes if present ("incident 2026-04-17T030014").
        incident = None
        for tok in (row.notes or "").split():
            if tok.startswith("incident") or "incident" in (row.notes or "").lower():
                # Be lenient — just pass notes through; renderer trims.
                incident = row.notes
                break
        report.failed_crons.append(
            FailedCronItem(row.project, row.skill, row.timestamp, incident)
        )

    # --- trigger 5: token budget exceeded last 30d ---
    cutoff_30d = now - timedelta(days=30)
    totals: dict = {}
    for row in rows:
        ts = _parse_ts(row.timestamp)
        if ts is None or ts < cutoff_30d:
            continue
        totals[row.project] = totals.get(row.project, 0) + row.tokens_in + row.tokens_out
    for proj in active_projects:
        used = totals.get(proj.name, 0)
        budget = getattr(proj, "budget_tokens_monthly", 0) or 0
        if budget > 0 and used > budget:
            report.budget_exceeded.append(BudgetItem(proj.name, used, budget))

    return report


# ---------- render ----------


def render(report: NeedsAttentionReport) -> str:
    """Render the report as markdown matching PRD §6.10 sample."""
    lines: List[str] = [f"# Needs Attention — generated {report.generated_at}", ""]

    def section(title_fmt: str, count: int, items: Iterable[str]) -> None:
        if count == 0:
            return
        lines.append(title_fmt.format(count=count))
        for s in items:
            lines.append(f"- {s}")
        lines.append("")

    section(
        "## 🔴 Blocked >48h ({count})",
        len(report.blocked),
        (
            f'{b.project}/T-{b.task_id} "{b.title}" — blocked by {b.blocked_by}, {b.hours}h'
            for b in report.blocked
        ),
    )
    section(
        "## 🟠 High-prio stale >72h ({count})",
        len(report.high_prio_stale),
        (
            f'{h.project}/T-{h.task_id} "{h.title}" — {h.hours}h'
            for h in report.high_prio_stale
        ),
    )
    section(
        "## 🔥 Needs-human ({count})",
        len(report.needs_human),
        (
            f'{n.project}/T-{n.task_id} "{n.title}"'
            for n in report.needs_human
        ),
    )
    section(
        "## 🚨 Failed crons ({count})",
        len(report.failed_crons),
        (
            f"{f.project}/{f.skill} at {f.timestamp}"
            + (f" — see {f.incident}" if f.incident else "")
            for f in report.failed_crons
        ),
    )
    section(
        "## 💰 Budget exceeded ({count})",
        len(report.budget_exceeded),
        (
            f"{bu.project} — {bu.tokens_used} tokens / {bu.budget} budget (last 30d)"
            for bu in report.budget_exceeded
        ),
    )

    if report.is_empty:
        lines.append("_No items — all projects healthy._")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write(report: NeedsAttentionReport, path: Optional[PathLike] = None) -> Path:
    """Write rendered report to `path` (default ~/.kira-hq/needs-attention.md)."""
    out = Path(path).expanduser() if path else DEFAULT_OUTPUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(report))
    return out


__all__ = [
    "BlockedItem",
    "BudgetItem",
    "FailedCronItem",
    "NeedsAttentionReport",
    "NeedsHumanItem",
    "StaleHighItem",
    "compute",
    "default_tasks_loader",
    "render",
    "write",
    "DEFAULT_OUTPUT",
]
