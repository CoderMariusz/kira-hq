"""`kira-hq add-project` — PRD §6.9.

Non-interactive (all flags) or interactive (prompts) project onboarding:

  1. Validate path exists + is git repo + has .taskmaster/
  2. Warn if prd/master-prd.md missing
  3. Check name unique in ~/.kira-hq/projects.yaml (v2)
  4. Append entry with added_at=today
  5. Create <path>/.env skeleton (chmod 0600)
  6. Symlink chosen skills via scripts.symlink_skills.deploy
  7. Run scripts.render_kanban to generate first kanban
  8. Print summary table

Exit codes:
    0 — success (incl. soft-warn for missing PRD)
    2 — path missing
    3 — not a git repo
    4 — no .taskmaster/ (suggest --init-taskmaster)
    5 — name collision in projects.yaml
    6 — unexpected I/O error

No `click` dependency — uses argparse + input().
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional, Sequence

import yaml


EXIT_OK = 0
EXIT_PATH_MISSING = 2
EXIT_NOT_GIT = 3
EXIT_NO_TASKMASTER = 4
EXIT_NAME_COLLISION = 5
EXIT_IO = 6


_ENV_SKELETON = """# ~/Projects/<project>/.env — Kira-HQ per-project overrides.
# Any keys here shadow the ones in ~/.kira-hq/.env for this project.
# Do NOT commit this file. chmod 0600.
#
# ANTHROPIC_API_KEY=
# OPENAI_API_KEY=
# TELEGRAM_BOT_TOKEN=
"""


@dataclass
class AddProjectArgs:
    path: Path
    name: Optional[str] = None
    priority: str = "medium"
    cron: str = "0 */2 * * *"
    budget_monthly: int = 500_000
    budget_per_run: int = 50_000
    skills: List[str] = None  # type: ignore[assignment]
    init_taskmaster: bool = False
    non_interactive: bool = False
    projects_yaml: Optional[Path] = None  # for testing
    render_kanban: bool = True
    deploy_skills: bool = True


# ---------- helpers ----------


def _is_git_repo(p: Path) -> bool:
    # Either a .git dir, a .git file (worktree), or any ancestor contains one
    cur = p.resolve()
    while True:
        if (cur / ".git").exists():
            return True
        if cur.parent == cur:
            return False
        cur = cur.parent


def _has_taskmaster(p: Path) -> bool:
    return (p / ".taskmaster").is_dir()


def _prompt(label: str, default: str) -> str:
    resp = input(f"{label} [{default}]: ").strip()
    return resp or default


def _print_summary(entry: dict) -> None:
    print()
    print("=" * 60)
    print("Added to projects.yaml:")
    print(f"  name:                  {entry['name']}")
    print(f"  path:                  {entry['path']}")
    print(f"  priority:              {entry['priority']}")
    print(f"  cron:                  {entry['cron']}")
    print(f"  budget_tokens_monthly: {entry['budget_tokens_monthly']}")
    print(f"  budget_tokens_per_run: {entry['budget_tokens_per_run']}")
    print(f"  skills:                {', '.join(entry['skills']) or '(none)'}")
    print(f"  added_at:              {entry['added_at']}")
    print("=" * 60)


# ---------- core ----------


def add_project(args: AddProjectArgs, *, stderr=sys.stderr) -> int:
    """Perform all 9 steps. Returns exit code; prints summary on success."""
    from kira_hq.projects_yaml import (  # late import
        DEFAULT_PROJECTS_YAML,
        ProjectEntryV2,
        ProjectsYamlV2,
        load as load_projects,
    )

    path = args.path.expanduser().resolve()

    # Step 1a: path exists
    if not path.exists():
        print(f"ERROR: path does not exist: {path}", file=stderr)
        return EXIT_PATH_MISSING

    # Step 1b: git repo
    if not _is_git_repo(path):
        print(f"ERROR: not a git repo: {path}", file=stderr)
        return EXIT_NOT_GIT

    # Step 1c: .taskmaster/ present
    if not _has_taskmaster(path):
        if args.init_taskmaster:
            (path / ".taskmaster" / "tasks").mkdir(parents=True, exist_ok=True)
            (path / ".taskmaster" / "tasks" / "tasks.json").write_text(
                '{"master": {"tasks": [], "metadata": {"tag": "master"}}}\n'
            )
        else:
            print(
                f"ERROR: no .taskmaster/ under {path}. "
                "Run `task-master init` first, or pass --init-taskmaster.",
                file=stderr,
            )
            return EXIT_NO_TASKMASTER

    # Step 2: PRD check (soft — warn only)
    prd = path / "prd" / "master-prd.md"
    prd_warning = False
    if not prd.exists():
        print(f"WARN: {prd} missing — project will be onboarded without a PRD.")
        prd_warning = True

    # Step 3: name + collision check
    name = args.name or path.name
    yaml_path = (args.projects_yaml or DEFAULT_PROJECTS_YAML).expanduser()
    yaml_path.parent.mkdir(parents=True, exist_ok=True)

    if yaml_path.exists():
        try:
            doc = load_projects(yaml_path)
        except Exception as exc:
            print(f"ERROR: cannot load {yaml_path}: {exc}", file=stderr)
            return EXIT_IO
        for p in doc.projects:
            if p.name == name:
                print(f"ERROR: project '{name}' already in {yaml_path}", file=stderr)
                return EXIT_NAME_COLLISION
    else:
        doc = ProjectsYamlV2(version=2, projects=[])

    # Step 4: interactive prompts if needed
    priority = args.priority
    cron = args.cron
    budget_monthly = args.budget_monthly
    budget_per_run = args.budget_per_run
    skills = list(args.skills or [])
    if not args.non_interactive:
        priority = _prompt("priority (high|medium|low)", priority)
        cron = _prompt("cron", cron)
        budget_monthly = int(_prompt("budget_tokens_monthly", str(budget_monthly)))
        budget_per_run = int(_prompt("budget_tokens_per_run", str(budget_per_run)))
        if not skills:
            raw = _prompt("skills (comma-separated, or empty)", "kira-hq-render-kanban")
            skills = [s.strip() for s in raw.split(",") if s.strip()]

    # Step 5: append to projects.yaml
    new_entry = ProjectEntryV2(
        name=name,
        path=str(path),
        status="active",
        priority=priority,  # type: ignore[arg-type]
        cron=cron,
        added_at=date.today().isoformat(),
        skills=skills,
        budget_tokens_monthly=budget_monthly,
        budget_tokens_per_run=budget_per_run,
        notes=None,
    )
    doc.projects.append(new_entry)
    # Serialize: ProjectsYamlV2 doesn't expose a direct dumper → build dict.
    serial = {
        "version": doc.version,
        "projects": [p.model_dump(mode="json") for p in doc.projects],
    }
    yaml_path.write_text(yaml.safe_dump(serial, sort_keys=False))

    # Step 6: .env skeleton
    env_file = path / ".env"
    if not env_file.exists():
        env_file.write_text(_ENV_SKELETON)
        try:
            os.chmod(env_file, 0o600)
        except OSError:
            pass  # non-POSIX; tolerate
    else:
        print(f"INFO: {env_file} already exists — left as-is.")

    # Step 7: deploy symlinks
    if args.deploy_skills and skills:
        try:
            # Importing scripts.symlink_skills requires scripts/ on sys.path
            # (pyproject has pythonpath=["src", "scripts"] for pytest but not
            # for runtime). Add it defensively.
            repo_root = Path(__file__).resolve().parents[3]
            scripts_dir = repo_root / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            import symlink_skills  # type: ignore
            symlink_skills.deploy(projects_yaml=yaml_path)
        except Exception as exc:
            print(f"WARN: symlink deploy skipped: {exc}")

    # Step 8: initial kanban render (optional — skippable for tests)
    if args.render_kanban:
        try:
            repo_root = Path(__file__).resolve().parents[3]
            scripts_dir = repo_root / "scripts"
            if str(scripts_dir) not in sys.path:
                sys.path.insert(0, str(scripts_dir))
            import render_kanban  # type: ignore
            # Public entrypoint is main() returning an exit code.
            render_kanban.main(["--projects-yaml", str(yaml_path)])
        except SystemExit:
            pass  # main() calls sys.exit
        except Exception as exc:
            print(f"WARN: kanban render skipped: {exc}")

    # Step 9: summary
    _print_summary(serial["projects"][-1])
    if prd_warning:
        print("(soft-warn: no PRD — consider adding prd/master-prd.md)")

    return EXIT_OK


# ---------- CLI ----------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kira-hq-add-project",
        description="Onboard a project into Kira-HQ (PRD §6.9).",
    )
    p.add_argument("path", type=Path, help="project root (must be a git repo)")
    p.add_argument("--name", help="override project name (default: basename of path)")
    p.add_argument("--priority", choices=("high", "medium", "low"), default="medium")
    p.add_argument("--cron", default="0 */2 * * *")
    p.add_argument("--budget-monthly", type=int, default=500_000, dest="budget_monthly")
    p.add_argument("--budget-per-run", type=int, default=50_000, dest="budget_per_run")
    p.add_argument(
        "--skills",
        default="",
        help="comma-separated skill names (leave empty for none)",
    )
    p.add_argument(
        "--init-taskmaster",
        action="store_true",
        dest="init_taskmaster",
        help="create minimal .taskmaster/ if missing instead of erroring",
    )
    p.add_argument(
        "-y", "--yes", "--non-interactive",
        action="store_true",
        dest="non_interactive",
        help="no prompts; use provided flags and defaults",
    )
    p.add_argument(
        "--projects-yaml",
        type=Path,
        default=None,
        help="override projects.yaml path (for testing)",
    )
    p.add_argument("--no-deploy-skills", action="store_true")
    p.add_argument("--no-render-kanban", action="store_true")
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    skills = [s.strip() for s in args.skills.split(",") if s.strip()]
    return add_project(
        AddProjectArgs(
            path=args.path,
            name=args.name,
            priority=args.priority,
            cron=args.cron,
            budget_monthly=args.budget_monthly,
            budget_per_run=args.budget_per_run,
            skills=skills,
            init_taskmaster=args.init_taskmaster,
            non_interactive=args.non_interactive,
            projects_yaml=args.projects_yaml,
            render_kanban=not args.no_render_kanban,
            deploy_skills=not args.no_deploy_skills,
        ),
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
