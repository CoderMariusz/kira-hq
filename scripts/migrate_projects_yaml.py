#!/usr/bin/env python3
"""Idempotent v1 → v2 migration for ~/.kira-hq/projects.yaml (PRD §6.6).

- Detects v1 (missing `version` key or `version: 1`).
- Backs up original to `<path>.v1.bak`.
- Writes v2 preserving order and adding defaults.
- Re-running is a no-op (version already 2 → exits 0).

Usage:
    python3 scripts/migrate_projects_yaml.py [path]    # defaults to ~/.kira-hq/projects.yaml
    python3 scripts/migrate_projects_yaml.py --check   # report only, no writes
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kira_hq.projects_yaml import (  # noqa: E402
    DEFAULT_PROJECTS_YAML,
    detect_version,
    load,
    migrate_v1_to_v2,
)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?", type=Path, default=DEFAULT_PROJECTS_YAML)
    ap.add_argument("--check", action="store_true", help="report only, no writes")
    args = ap.parse_args()

    path = args.path.expanduser()
    if not path.exists():
        print(f"ERROR: {path} does not exist", file=sys.stderr)
        return 2

    version = detect_version(path)
    print(f"Detected version: {version} ({path})")

    if version == 2:
        # Validate structure is actually usable
        load(path)
        print("Already v2. No migration needed (idempotent).")
        return 0

    if args.check:
        print("v1 detected. Run without --check to perform migration.")
        return 0

    # Perform migration
    backup = path.with_suffix(path.suffix + ".v1.bak")
    shutil.copy2(path, backup)
    print(f"Backup: {backup}")

    v1_data = yaml.safe_load(path.read_text()) or {}
    v2_data = migrate_v1_to_v2(v1_data)

    # Validate before writing
    load_path_data_check = yaml.safe_dump(v2_data, sort_keys=False)
    tmp_path = path.with_suffix(path.suffix + ".v2.tmp")
    tmp_path.write_text(load_path_data_check)
    try:
        load(tmp_path)
    except Exception as e:
        print(f"ERROR: migrated data fails validation: {e}", file=sys.stderr)
        tmp_path.unlink(missing_ok=True)
        return 3

    # Atomic rename
    tmp_path.replace(path)
    print(f"Migrated to v2: {path}")
    print(f"  projects: {len(v2_data['projects'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
