#!/usr/bin/env python3
"""Deploy Kira-HQ shared skills via symlinks — PRD §6.11.

Reads `~/.kira-hq/projects.yaml` (v2), then for each active project + each
skill in its `skills:` list, ensures three symlinks exist pointing at
`~/.kira-hq/skills-shared/<skill>`:

  1. `<project-path>/.claude/skills/<skill>`     (per-project Claude Code)
  2. `~/.claude/skills/<skill>`                  (global Claude Code pool)
  3. `~/.hermes/skills/kira-hq/<skill>`          (Hermes namespace)

Idempotent: correct symlinks are left alone, broken ones are repaired,
non-symlink collisions are reported (and skipped) rather than overwritten.

Usage:
    python scripts/symlink_skills.py              # deploy
    python scripts/symlink_skills.py --check      # dry-run, report only
    python scripts/symlink_skills.py --prune      # also remove orphans

Exit codes:
    0 — all symlinks correct (or repaired)
    1 — non-symlink collision encountered (manual fix needed)
    2 — missing skill source under skills-shared/
    3 — projects.yaml missing / unreadable
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

# Allow running as a script without install: add repo src/ to sys.path
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from kira_hq.projects_yaml import DEFAULT_PROJECTS_YAML, load  # noqa: E402

SKILLS_SHARED = Path.home() / ".kira-hq" / "skills-shared"
CLAUDE_GLOBAL = Path.home() / ".claude" / "skills"
HERMES_NAMESPACE = Path.home() / ".hermes" / "skills" / "kira-hq"


@dataclass
class Report:
    created: List[str] = field(default_factory=list)
    repaired: List[str] = field(default_factory=list)
    ok: List[str] = field(default_factory=list)
    collisions: List[str] = field(default_factory=list)  # non-symlink in the way
    missing_source: List[str] = field(default_factory=list)
    pruned: List[str] = field(default_factory=list)

    def print_summary(self) -> None:
        print(f"  ok          : {len(self.ok)}")
        print(f"  created     : {len(self.created)}")
        print(f"  repaired    : {len(self.repaired)}")
        print(f"  collisions  : {len(self.collisions)}")
        print(f"  missing src : {len(self.missing_source)}")
        print(f"  pruned      : {len(self.pruned)}")
        for label, items in (
            ("created", self.created),
            ("repaired", self.repaired),
            ("collisions", self.collisions),
            ("missing source", self.missing_source),
            ("pruned", self.pruned),
        ):
            for line in items:
                print(f"    [{label}] {line}")


def _targets_for(project_path: Path, skill: str,
                 claude_global: Path, hermes_ns: Path) -> List[Path]:
    return [
        project_path / ".claude" / "skills" / skill,
        claude_global / skill,
        hermes_ns / skill,
    ]


def _ensure_link(
    link: Path,
    source: Path,
    *,
    check_only: bool,
    report: Report,
) -> None:
    link_s = str(link)
    link.parent.mkdir(parents=True, exist_ok=True)

    if link.is_symlink():
        current = os.readlink(link)
        if Path(current).resolve() == source.resolve():
            report.ok.append(link_s)
            return
        # Broken / wrong target → repair
        if not check_only:
            link.unlink()
            link.symlink_to(source)
        report.repaired.append(f"{link_s} -> {source}")
        return

    if link.exists():
        report.collisions.append(link_s)
        return

    if not check_only:
        link.symlink_to(source)
    report.created.append(f"{link_s} -> {source}")


def deploy(
    projects_yaml: Path = DEFAULT_PROJECTS_YAML,
    skills_shared: Path = SKILLS_SHARED,
    claude_global: Path = CLAUDE_GLOBAL,
    hermes_ns: Path = HERMES_NAMESPACE,
    *,
    check_only: bool = False,
    prune: bool = False,
) -> Tuple[Report, int]:
    """Deploy symlinks; returns (report, exit_code)."""
    report = Report()

    if not projects_yaml.exists():
        print(f"ERROR: projects.yaml not found at {projects_yaml}", file=sys.stderr)
        return report, 3

    doc = load(projects_yaml)

    # Track which global/hermes symlinks we expect — used for --prune.
    expected_global: set[Path] = set()

    for entry in doc.projects:
        if entry.status == "archived":
            continue
        project_path = Path(entry.path).expanduser()
        for skill in entry.skills:
            source = skills_shared / skill
            if not source.exists():
                report.missing_source.append(f"{skill} (needed by {entry.name})")
                continue
            for link in _targets_for(project_path, skill, claude_global, hermes_ns):
                _ensure_link(link, source, check_only=check_only, report=report)
                if link.parent in (claude_global, hermes_ns):
                    expected_global.add(link)

    if prune:
        for root in (claude_global, hermes_ns):
            if not root.exists():
                continue
            for entry_path in root.iterdir():
                if not entry_path.is_symlink():
                    continue
                target = Path(os.readlink(entry_path))
                target_abs = (entry_path.parent / target).resolve() \
                    if not target.is_absolute() else target.resolve()
                # Prune only symlinks into our skills-shared dir that are
                # no longer referenced by any active project.
                try:
                    target_abs.relative_to(skills_shared.resolve())
                except ValueError:
                    continue
                if entry_path not in expected_global:
                    if not check_only:
                        entry_path.unlink()
                    report.pruned.append(str(entry_path))

    exit_code = 0
    if report.collisions:
        exit_code = 1
    elif report.missing_source:
        exit_code = 2
    return report, exit_code


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--projects-yaml", type=Path, default=DEFAULT_PROJECTS_YAML)
    parser.add_argument("--skills-shared", type=Path, default=SKILLS_SHARED)
    parser.add_argument("--claude-global", type=Path, default=CLAUDE_GLOBAL)
    parser.add_argument("--hermes-ns", type=Path, default=HERMES_NAMESPACE)
    parser.add_argument("--check", action="store_true", help="dry-run only")
    parser.add_argument("--prune", action="store_true",
                        help="remove orphan symlinks in global/Hermes dirs")
    args = parser.parse_args(argv)

    report, code = deploy(
        projects_yaml=args.projects_yaml,
        skills_shared=args.skills_shared,
        claude_global=args.claude_global,
        hermes_ns=args.hermes_ns,
        check_only=args.check,
        prune=args.prune,
    )
    report.print_summary()
    return code


if __name__ == "__main__":
    sys.exit(main())
