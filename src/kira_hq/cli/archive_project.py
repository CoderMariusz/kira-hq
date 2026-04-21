"""`kira-hq archive-project` — PRD §6.9 (inverse clause).

Sets status=archived in ~/.kira-hq/projects.yaml v2 and best-effort
unloads the project's launchd cron plist. Keeps the entry in the yaml
(history) and does NOT delete any files.

Exit codes:
    0 — archived
    1 — project not found
    6 — already archived
    7 — I/O error
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

import yaml


EXIT_OK = 0
EXIT_NOT_FOUND = 1
EXIT_ALREADY_ARCHIVED = 6
EXIT_IO = 7


def _default_cron_uninstaller(project_name: str) -> bool:
    """Best-effort launchctl uninstall. Returns True if something was unloaded."""
    label = f"com.kira-hq.{project_name}.cron"
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist = plist_dir / f"{label}.plist"
    ok = False
    if plist.exists():
        try:
            uid = os.getuid()
            subprocess.run(
                ["launchctl", "bootout", f"gui/{uid}/{label}"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            ok = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return ok


@dataclass
class ArchiveArgs:
    name: str
    projects_yaml: Optional[Path] = None
    cron_uninstaller: Callable[[str], bool] = _default_cron_uninstaller


def archive_project(args: ArchiveArgs, *, stderr=sys.stderr) -> int:
    from kira_hq.projects_yaml import DEFAULT_PROJECTS_YAML, load as load_projects  # late

    yaml_path = (args.projects_yaml or DEFAULT_PROJECTS_YAML).expanduser()
    if not yaml_path.exists():
        print(f"ERROR: {yaml_path} missing", file=stderr)
        return EXIT_IO

    try:
        doc = load_projects(yaml_path)
    except Exception as exc:
        print(f"ERROR: cannot load {yaml_path}: {exc}", file=stderr)
        return EXIT_IO

    target = None
    for p in doc.projects:
        if p.name == args.name:
            target = p
            break
    if target is None:
        print(f"ERROR: project '{args.name}' not found in {yaml_path}", file=stderr)
        return EXIT_NOT_FOUND

    if target.status == "archived":
        print(f"ERROR: project '{args.name}' already archived", file=stderr)
        return EXIT_ALREADY_ARCHIVED

    target.status = "archived"
    serial = {
        "version": doc.version,
        "projects": [p.model_dump(mode="json") for p in doc.projects],
    }
    yaml_path.write_text(yaml.safe_dump(serial, sort_keys=False))

    unloaded = False
    try:
        unloaded = bool(args.cron_uninstaller(args.name))
    except Exception as exc:
        print(f"WARN: cron uninstall error: {exc}")

    project_path = Path(target.path).expanduser()
    print(f"OK: archived '{args.name}' (path retained: {project_path})")
    print(f"   cron unloaded: {'yes' if unloaded else 'no-op'}")
    print("   files left on disk (archival is logical, not destructive)")
    return EXIT_OK


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="kira-hq-archive-project",
        description="Archive a Kira-HQ project (PRD §6.9 inverse).",
    )
    p.add_argument("name", help="project name as it appears in projects.yaml")
    p.add_argument("--projects-yaml", type=Path, default=None)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    return archive_project(
        ArchiveArgs(name=args.name, projects_yaml=args.projects_yaml)
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
