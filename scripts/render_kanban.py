#!/usr/bin/env python3
"""Kira-HQ Module 1 — Kanban Renderer (production-ready, T-8).

Reads `~/.kira-hq/projects.yaml` (v2), fetches tasks per active project via
`task-master list --json`, categorizes them, and writes:
    <project>/kanban_board.md        per-project board
    ~/.kira-hq/global-kanban.md      cross-project attention summary
    <project>/pipeline.log.md        append entry per run (PRD §6.1)
    ~/.kira-hq/global-pipeline.log.md same entry, aggregate

Each rendered board includes an ADR section with the last 5 ADRs from
`<project>/docs/ADR/` (PRD §6.8).

Error modes (documented in README, handled here):
    - projects.yaml missing     → exit 3, no partial writes
    - project path missing      → warn, skip, pipeline.log status=skip
    - task-master crash/timeout → warn, skip, pipeline.log status=fail
    - non-zero exit from tm     → warn, skip, pipeline.log status=fail
    - at least one project OK   → exit 0
    - ALL projects failed       → exit 2
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
if str(_REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "scripts"))

from kira_hq.pipeline_log import log_execution  # noqa: E402
from kira_hq.projects_yaml import DEFAULT_PROJECTS_YAML, load  # noqa: E402
from render_adr_index import last_n as last_n_adrs  # noqa: E402

PROJECTS_YAML = DEFAULT_PROJECTS_YAML
GLOBAL_KANBAN = Path.home() / ".kira-hq" / "global-kanban.md"
SKILL_NAME = "kira-hq-render-kanban"


# ---------------------------------------------------------------------------
# task-master subprocess
# ---------------------------------------------------------------------------

def _clean_env() -> Dict[str, str]:
    """Env with the 4 SDK-crashing vars stripped (PRD §6.4)."""
    import os
    env = os.environ.copy()
    for k in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT",
              "CLAUDE_CODE_EXECPATH", "ANTHROPIC_API_KEY"):
        env.pop(k, None)
    return env


def fetch_tasks(project_path: Path, *, timeout: int = 30) -> Optional[List[dict]]:
    """Run `task-master list --json` in project_path. Returns list or None."""
    if not project_path.exists():
        return None
    try:
        result = subprocess.run(
            ["task-master", "list", "--json"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=_clean_env(),
        )
    except subprocess.TimeoutExpired:
        print(f"ERROR: task-master timeout in {project_path}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("ERROR: task-master CLI not on PATH", file=sys.stderr)
        return None

    if result.returncode != 0:
        print(
            f"WARN: task-master exit {result.returncode} in {project_path}: "
            f"{result.stderr.strip()[:200]}",
            file=sys.stderr,
        )
        return None

    stdout = result.stdout.strip()
    if not stdout:
        return []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON from task-master in {project_path}: {e}",
              file=sys.stderr)
        return None

    # task-master shapes: {"tasks": [...]}, or {"<tag>": {"tasks": [...]}}
    if isinstance(data, dict):
        if "tasks" in data and isinstance(data["tasks"], list):
            return data["tasks"]
        # tagged shape — pick master or the first tag
        for key in ("master", *data.keys()):
            val = data.get(key)
            if isinstance(val, dict) and isinstance(val.get("tasks"), list):
                return val["tasks"]
    return data if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# categorization + rendering
# ---------------------------------------------------------------------------

_IN_PROGRESS_STATUSES = {
    "writer", "review", "e2e_test", "qa", "regression", "in-progress",
}
_DONE_STATUSES = {"done"}


def categorize(tasks: List[dict]) -> Dict[str, List[dict]]:
    today = date.today().isoformat()
    cats: Dict[str, List[dict]] = {
        "needs_attention": [], "in_progress": [],
        "done_today": [], "backlog": [], "fixes": [], "blocked": [],
    }
    for t in tasks:
        status = t.get("status", "pending")
        tag = t.get("tag", "master")
        if status == "needs-human":
            cats["needs_attention"].append(t)
        elif status == "blocked":
            cats["blocked"].append(t)
        elif status in _IN_PROGRESS_STATUSES:
            cats["in_progress"].append(t)
        elif status in _DONE_STATUSES and str(t.get("updated_at", "")).startswith(today):
            cats["done_today"].append(t)
        elif tag == "fixes" and status == "pending":
            cats["fixes"].append(t)
        elif status == "pending":
            cats["backlog"].append(t)
    return cats


_PRIO_ORDER = {"high": 0, "medium": 1, "low": 2}


def _fmt_task(t: dict, *, include_deps: bool = False) -> str:
    tid = t.get("id", "?")
    title = t.get("title", "(no title)")
    base = f"- **{tid}** — {title}"
    prio = t.get("priority")
    if prio:
        base += f" — priority: {prio}"
    if include_deps:
        deps = t.get("dependencies") or []
        if deps:
            base += f" — deps: [{','.join(str(d) for d in deps)}]"
    notes = t.get("notes") or t.get("description")
    if notes:
        base += f" — {str(notes)[:80]}"
    return base


def _adr_section(project_path: Path, n: int = 5) -> List[str]:
    adr_dir = project_path / "docs" / "ADR"
    if not adr_dir.exists():
        return [f"## 📚 ADRs — last 0 (of 0 total)", "",
                "_No `docs/ADR/` directory. See `~/.kira-hq/templates/ADR.md`._"]
    try:
        adrs = last_n_adrs(adr_dir, n)
    except Exception as e:
        return [f"## 📚 ADRs (unavailable — {e})", ""]
    lines = [f"## 📚 ADRs — last {min(n, len(adrs))} (of {len(adrs)} total)", ""]
    if not adrs:
        lines.append("_No ADRs yet. See `docs/ADR/` and `~/.kira-hq/templates/ADR.md`._")
        return lines
    for a in adrs:
        lines.append(
            f"- **{a.number_str}** — [{a.title}](docs/ADR/{a.path.name}) "
            f"— {a.status} — {a.date}"
        )
    return lines


def render_project_kanban(
    project_name: str,
    project_path: Path,
    tasks: List[dict],
) -> Dict[str, Any]:
    """Write kanban_board.md; return {'cats': ..., 'path': ..., 'total': N}."""
    cats = categorize(tasks)
    now = datetime.now().isoformat(timespec="minutes")
    total = len(tasks)
    done = sum(1 for t in tasks if t.get("status") in _DONE_STATUSES)
    in_prog = len(cats["in_progress"])
    attn = len(cats["needs_attention"]) + len(cats["blocked"])

    lines: List[str] = [
        f"# {project_name} — Kanban Board",
        f"**Last updated:** {now}",
        f"**Total tasks:** {total} | **Done:** {done} "
        f"| **In progress:** {in_prog} | **Needs attention:** {attn}",
        "",
    ]

    # Needs attention
    lines.append(f"## 🔴 Wymaga Twojej uwagi ({len(cats['needs_attention'])})")
    for t in cats["needs_attention"]:
        lines.append(_fmt_task(t))
    lines.append("")

    # Blocked
    lines.append(f"## ⛔ Blocked ({len(cats['blocked'])})")
    for t in cats["blocked"]:
        lines.append(_fmt_task(t, include_deps=True))
    lines.append("")

    # In progress
    lines.append(f"## 🟡 In progress ({len(cats['in_progress'])})")
    for t in cats["in_progress"]:
        attempts = t.get("attempts", 0)
        lines.append(
            f"- **{t.get('id')}** — {t.get('title','')} "
            f"— stage: {t.get('status')} — attempt {attempts}/3"
        )
    lines.append("")

    # Done today
    lines.append(f"## ✅ Done today ({len(cats['done_today'])})")
    for t in cats["done_today"]:
        lines.append(_fmt_task(t))
    lines.append("")

    # Backlog
    lines.append(f"## 📥 Backlog ({len(cats['backlog'])})")
    for t in sorted(
        cats["backlog"],
        key=lambda x: (_PRIO_ORDER.get(x.get("priority", "medium"), 1),
                       str(x.get("id", ""))),
    ):
        lines.append(_fmt_task(t, include_deps=True))
    lines.append("")

    # Fixes
    lines.append(f"## 🐛 Fixes reported ({len(cats['fixes'])})")
    for t in cats["fixes"]:
        lines.append(_fmt_task(t))
    lines.append("")

    # ADRs (PRD §6.8)
    lines.extend(_adr_section(project_path))

    kanban_path = project_path / "kanban_board.md"
    kanban_path.write_text("\n".join(lines).rstrip() + "\n")
    return {"cats": cats, "path": kanban_path, "total": total, "done": done}


def render_global(
    per_project: Dict[str, Dict[str, Any]],
    out_path: Path = GLOBAL_KANBAN,
) -> Path:
    now = datetime.now().isoformat(timespec="minutes")
    lines: List[str] = [
        "# Kira-HQ — Global Command Center",
        f"**Last updated:** {now}",
        f"**Projects rendered:** {len(per_project)}",
        "",
    ]

    # Summary table
    lines.append("## Overview")
    lines.append("| Project | Total | Done | In progress | Needs attention | Blocked |")
    lines.append("|---------|-------|------|-------------|-----------------|---------|")
    for name, result in per_project.items():
        cats = result["cats"]
        lines.append(
            f"| {name} | {result['total']} | {result['done']} "
            f"| {len(cats['in_progress'])} | {len(cats['needs_attention'])} "
            f"| {len(cats['blocked'])} |"
        )
    lines.append("")

    # Attention stream
    any_attn = False
    for name, result in per_project.items():
        cats = result["cats"]
        total_attn = (len(cats["needs_attention"]) + len(cats["blocked"])
                      + len(cats["fixes"]))
        if total_attn == 0:
            continue
        any_attn = True
        lines.append(f"## {name} — attention items ({total_attn})")
        for t in cats["needs_attention"]:
            lines.append(f"- 🔴 **{t.get('id')}** — {t.get('title','')}")
        for t in cats["blocked"]:
            lines.append(f"- ⛔ **{t.get('id')}** — {t.get('title','')}")
        for t in cats["fixes"]:
            lines.append(f"- 🐛 **{t.get('id')}** — {t.get('title','')}")
        lines.append("")
    if not any_attn:
        lines.append("## ✅ No attention items across all projects\n")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip() + "\n")
    return out_path


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def render_all(
    projects_yaml: Path = PROJECTS_YAML,
    global_out: Path = GLOBAL_KANBAN,
    *,
    write_pipeline_log: bool = True,
) -> Dict[str, Any]:
    """Render everything. Returns {'per_project': ..., 'exit_code': int}."""
    if not projects_yaml.exists():
        print(f"ERROR: {projects_yaml} not found", file=sys.stderr)
        return {"per_project": {}, "exit_code": 3}

    doc = load(projects_yaml)
    per_project: Dict[str, Dict[str, Any]] = {}
    any_success = False
    any_failure = False

    for entry in doc.projects:
        if entry.status != "active":
            continue
        name = entry.name
        project_path = Path(entry.path).expanduser()
        started = time.monotonic()
        status_str = "ok"
        notes = ""

        tasks = fetch_tasks(project_path)
        if tasks is None:
            status_str = "fail" if project_path.exists() else "skip"
            notes = "task-master failed" if project_path.exists() else "project path missing"
            any_failure = True
        else:
            try:
                result = render_project_kanban(name, project_path, tasks)
                per_project[name] = result
                any_success = True
                notes = f"{result['total']} tasks rendered"
                print(f"✓ {result['path']}")
            except Exception as e:  # defensive — should not happen in tests
                status_str = "fail"
                notes = f"render error: {e}"
                any_failure = True

        duration = round(time.monotonic() - started, 3)
        if write_pipeline_log:
            try:
                log_execution(
                    project_path=project_path if project_path.exists() else Path.home(),
                    project=name,
                    skill=SKILL_NAME,
                    provider="n/a",
                    expand_used=False,
                    tokens_in=0,
                    tokens_out=0,
                    status=status_str,
                    duration_s=duration,
                    notes=notes,
                    timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                )
            except Exception as e:
                print(f"WARN: pipeline log write failed for {name}: {e}",
                      file=sys.stderr)

    global_path = render_global(per_project, global_out)
    print(f"✓ {global_path}")

    if not any_success and any_failure:
        code = 2
    elif any_failure:
        code = 1  # partial
    else:
        code = 0
    return {"per_project": per_project, "exit_code": code,
            "global_path": global_path}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Kira-HQ kanban renderer")
    parser.add_argument("--projects-yaml", type=Path, default=PROJECTS_YAML)
    parser.add_argument("--global-out", type=Path, default=GLOBAL_KANBAN)
    parser.add_argument("--no-pipeline-log", action="store_true",
                        help="skip appending pipeline log rows (for testing)")
    args = parser.parse_args(argv)
    res = render_all(
        projects_yaml=args.projects_yaml,
        global_out=args.global_out,
        write_pipeline_log=not args.no_pipeline_log,
    )
    return res["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
