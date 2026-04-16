#!/usr/bin/env python3
"""Kira-HQ — Kanban Renderer (Phase 1 simple version).

Reads ~/.kira-hq/projects.yaml, runs `task-master list --json` per active
project, and writes kanban_board.md per project plus a cross-project
global-kanban.md in ~/.kira-hq/.
"""
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

PROJECTS_YAML = Path.home() / ".kira-hq" / "projects.yaml"
GLOBAL_KANBAN = Path.home() / ".kira-hq" / "global-kanban.md"


def load_projects():
    if not PROJECTS_YAML.exists():
        print(f"ERROR: {PROJECTS_YAML} not found", file=sys.stderr)
        sys.exit(1)
    with open(PROJECTS_YAML) as f:
        return yaml.safe_load(f) or {}


def fetch_tasks(project_path: Path):
    try:
        result = subprocess.run(
            ["task-master", "list", "--json"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(
                f"WARN: task-master failed in {project_path}: {result.stderr.strip()}",
                file=sys.stderr,
            )
            return None
        stdout = result.stdout.strip()
        if not stdout:
            return []
        data = json.loads(stdout)
        if isinstance(data, dict) and "tasks" in data:
            return data["tasks"]
        return data
    except Exception as e:
        print(f"ERROR in {project_path}: {e}", file=sys.stderr)
        return None


def categorize(tasks):
    today = date.today().isoformat()
    cats = {
        "needs_attention": [],
        "in_progress": [],
        "done_today": [],
        "backlog": [],
        "fixes": [],
    }
    for t in tasks:
        status = t.get("status", "pending")
        tag = t.get("tag", "master")
        if status == "needs-human":
            cats["needs_attention"].append(t)
        elif status in ["writer", "review", "e2e_test", "qa", "regression", "in-progress"]:
            cats["in_progress"].append(t)
        elif status == "done" and str(t.get("updated_at", "")).startswith(today):
            cats["done_today"].append(t)
        elif tag == "fixes" and status == "pending":
            cats["fixes"].append(t)
        elif status == "pending":
            cats["backlog"].append(t)
    return cats


def render_project_kanban(project_name, project_path: Path, tasks):
    cats = categorize(tasks)
    now = datetime.now().isoformat(timespec="minutes")
    total = len(tasks)
    done = sum(1 for t in tasks if t.get("status") == "done")
    in_prog = len(cats["in_progress"])
    attn = len(cats["needs_attention"])

    lines = [
        f"# {project_name} — Kanban Board",
        f"**Last updated:** {now}",
        f"**Total tasks:** {total} | **Done:** {done} | **In progress:** {in_prog} | **Needs attention:** {attn}",
        "",
        f"## 🔴 Wymaga Twojej uwagi ({len(cats['needs_attention'])})",
    ]
    for t in cats["needs_attention"]:
        lines.append(
            f"- **{t.get('id')}** — {t.get('title','(no title)')} — {t.get('notes','')}"
        )

    lines.append(f"\n## 🟡 In progress by Hermes ({len(cats['in_progress'])})")
    for t in cats["in_progress"]:
        attempts = t.get("attempts", 0)
        lines.append(
            f"- **{t.get('id')}** — {t.get('title','')} — stage: {t.get('status')} — attempt {attempts}/3"
        )

    lines.append(f"\n## ✅ Done today ({len(cats['done_today'])})")
    for t in cats["done_today"]:
        lines.append(f"- **{t.get('id')}** — {t.get('title','')}")

    lines.append(f"\n## 📥 Backlog ({len(cats['backlog'])})")
    for t in sorted(cats["backlog"], key=lambda x: x.get("priority", "medium")):
        deps = ",".join(str(d) for d in t.get("dependencies", []))
        cplx = t.get("complexity", "?")
        lines.append(
            f"- **{t.get('id')}** — {t.get('title','')} — deps: [{deps}] — complexity: {cplx}/10"
        )

    lines.append(f"\n## 🐛 Fixes reported ({len(cats['fixes'])})")
    for t in cats["fixes"]:
        lines.append(
            f"- **{t.get('id')}** — {t.get('title','')} — priority: {t.get('priority','medium')}"
        )

    kanban_path = project_path / "kanban_board.md"
    kanban_path.write_text("\n".join(lines) + "\n")
    return cats


def render_global(all_cats):
    now = datetime.now().isoformat(timespec="minutes")
    lines = [
        "# Kira-HQ — Global View",
        f"**Last updated:** {now}",
        "",
    ]
    for project_name, cats in all_cats.items():
        attention_count = len(cats["needs_attention"]) + len(cats["fixes"])
        if attention_count == 0:
            continue
        lines.append(f"## {project_name} ({attention_count})")
        for t in cats["needs_attention"]:
            lines.append(f"- 🔴 **{t.get('id')}** — {t.get('title','')}")
        for t in cats["fixes"]:
            lines.append(f"- 🐛 **{t.get('id')}** — {t.get('title','')}")
        lines.append("")
    GLOBAL_KANBAN.write_text("\n".join(lines) + "\n")


def main():
    cfg = load_projects()
    all_cats = {}
    exit_code = 0
    for proj in cfg.get("projects", []) or []:
        if proj.get("status") != "active":
            continue
        name = proj["name"]
        path = Path(proj["path"]).expanduser()
        tasks = fetch_tasks(path)
        if tasks is None:
            exit_code = 2
            continue
        cats = render_project_kanban(name, path, tasks)
        all_cats[name] = cats
        print(f"✓ Rendered {path}/kanban_board.md")
    render_global(all_cats)
    print(f"✓ Rendered {GLOBAL_KANBAN}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
