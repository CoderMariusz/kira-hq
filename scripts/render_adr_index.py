#!/usr/bin/env python3
"""ADR index renderer — PRD §6.8.

Scans a per-project `docs/ADR/` directory, parses each `NNNN-kebab-title.md`
file, and writes a sorted `INDEX.md` (number | title | status | date).

Also provides a cross-project aggregator that concatenates every active
project's ADR index into `~/.kira-hq/global-adrs.md`.

Usage:
    python scripts/render_adr_index.py                       # this project
    python scripts/render_adr_index.py --dir <path>          # custom dir
    python scripts/render_adr_index.py --global-aggregate    # all projects
    python scripts/render_adr_index.py --last 5              # tail rows only

Public API (importable):
    parse_adr(path) -> ADR
    render_index(adr_dir) -> Path
    render_global(projects_yaml, out_path) -> Path
    last_n(adr_dir, n) -> list[ADR]        # used by Module 1 renderer (T-8)
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from kira_hq.projects_yaml import DEFAULT_PROJECTS_YAML, load  # noqa: E402

GLOBAL_ADRS = Path.home() / ".kira-hq" / "global-adrs.md"

# Strict filename: NNNN-kebab-title.md
FILENAME_RE = re.compile(r"^(\d{4})-[a-z0-9][a-z0-9-]*\.md$")

# Heading: "# ADR NNNN: <Title>"  — Title is the rest of the line.
HEADING_RE = re.compile(r"^#\s+ADR\s+(\d{4}):\s+(.+?)\s*$")

STATUS_RE = re.compile(r"^\s*-\s*\*\*Status:\*\*\s*(.+?)\s*$", re.IGNORECASE)
DATE_RE = re.compile(r"^\s*-\s*\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})\s*$", re.IGNORECASE)


@dataclass
class ADR:
    number: int
    title: str
    status: str
    date: str
    path: Path

    @property
    def number_str(self) -> str:
        return f"{self.number:04d}"


class ADRParseError(ValueError):
    pass


def parse_adr(path: Path) -> ADR:
    path = Path(path)
    m = FILENAME_RE.match(path.name)
    if not m:
        raise ADRParseError(
            f"{path.name}: filename must match NNNN-kebab-title.md"
        )
    number = int(m.group(1))

    title: Optional[str] = None
    status: Optional[str] = None
    date: Optional[str] = None
    for raw in path.read_text().splitlines():
        if title is None:
            mh = HEADING_RE.match(raw)
            if mh:
                file_num = int(mh.group(1))
                if file_num != number:
                    raise ADRParseError(
                        f"{path.name}: heading number {file_num:04d} "
                        f"mismatches filename {number:04d}"
                    )
                title = mh.group(2).strip()
                continue
        if status is None:
            ms = STATUS_RE.match(raw)
            if ms:
                status = ms.group(1).split("|")[0].strip().rstrip(".")
                continue
        if date is None:
            md = DATE_RE.match(raw)
            if md:
                date = md.group(1)
                continue
        if title and status and date:
            break

    if not title:
        raise ADRParseError(f"{path.name}: missing '# ADR NNNN: <Title>' heading")
    if not status:
        raise ADRParseError(f"{path.name}: missing '- **Status:** ...' line")
    if not date:
        raise ADRParseError(f"{path.name}: missing '- **Date:** YYYY-MM-DD' line")

    return ADR(number=number, title=title, status=status, date=date, path=path)


def collect(adr_dir: Path) -> List[ADR]:
    adrs: List[ADR] = []
    for p in sorted(adr_dir.glob("*.md")):
        if p.name.upper() == "INDEX.MD":
            continue
        if not FILENAME_RE.match(p.name):
            # Non-ADR docs are silently ignored.
            continue
        adrs.append(parse_adr(p))
    adrs.sort(key=lambda a: a.number)
    return adrs


def _render_table(adrs: List[ADR], relative_to: Optional[Path] = None) -> str:
    """Render ADRs as a markdown table.

    `relative_to` controls how link paths are emitted:
      - Path given → `adr.path.relative_to(relative_to)` (fallback: os.path.relpath)
      - None       → `os.path.relpath(adr.path, cwd)`, i.e. full navigable path
        from the caller's working directory. Previously this fell back to
        `adr.path.name`, which broke global-adrs.md links (PR#1 P2 review):
        the bare filename resolved relative to `~/.kira-hq/`, not to the
        owning project's `docs/ADR/` directory.
    """
    lines = [
        "| #    | Title | Status | Date       |",
        "|------|-------|--------|------------|",
    ]
    for adr in adrs:
        if relative_to is not None:
            try:
                link = adr.path.relative_to(relative_to)
            except ValueError:
                # adr.path is not a descendant of relative_to — fall back to
                # a real relative path computation (works across drives/mounts)
                link = Path(os.path.relpath(adr.path, relative_to))
        else:
            link = adr.path  # absolute path — always resolvable
        title_cell = f"[{adr.title}]({link})"
        lines.append(
            f"| {adr.number_str} | {title_cell} | {adr.status} | {adr.date} |"
        )
    return "\n".join(lines) + "\n"


def render_index(adr_dir: Path) -> Path:
    adr_dir = Path(adr_dir)
    adrs = collect(adr_dir)
    out = adr_dir / "INDEX.md"
    body = (
        "# ADR Index\n\n"
        "Generated by `scripts/render_adr_index.py` — PRD §6.8.\n\n"
    )
    if not adrs:
        body += "_No ADRs yet._\n"
    else:
        body += _render_table(adrs, relative_to=adr_dir)
    out.write_text(body)
    return out


def render_global(
    projects_yaml: Path = DEFAULT_PROJECTS_YAML,
    out_path: Path = GLOBAL_ADRS,
) -> Path:
    doc = load(projects_yaml)
    out_path = Path(out_path).expanduser()
    out_dir = out_path.parent
    chunks: List[str] = ["# Global ADRs\n\nAggregated across all active projects. PRD §6.8.\n"]
    for entry in doc.projects:
        if entry.status == "archived":
            continue
        adr_dir = Path(entry.path).expanduser() / "docs" / "ADR"
        if not adr_dir.exists():
            continue
        adrs = collect(adr_dir)
        if not adrs:
            continue
        chunks.append(f"\n## {entry.name}\n")
        # Emit links relative to the GLOBAL file's directory, so clicking them
        # in `~/.kira-hq/global-adrs.md` navigates to the project's ADR dir.
        # `out_dir` may not be an ancestor of `adr_dir` → use os.path.relpath.
        chunks.append(_render_table(adrs, relative_to=out_dir))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(chunks))
    return out_path


def last_n(adr_dir: Path, n: int = 5) -> List[ADR]:
    """Return the N most recent ADRs (by number, descending). For T-8."""
    adrs = collect(Path(adr_dir))
    return sorted(adrs, key=lambda a: a.number, reverse=True)[:n]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path,
                        default=_REPO_ROOT / "docs" / "ADR")
    parser.add_argument("--global-aggregate", action="store_true")
    parser.add_argument("--projects-yaml", type=Path, default=DEFAULT_PROJECTS_YAML)
    parser.add_argument("--out", type=Path, default=GLOBAL_ADRS)
    parser.add_argument("--last", type=int, default=0,
                        help="print last N ADRs as markdown table to stdout")
    args = parser.parse_args(argv)

    if args.last:
        adrs = last_n(args.dir, args.last)
        print(_render_table(adrs))
        return 0

    if args.global_aggregate:
        out = render_global(args.projects_yaml, args.out)
        print(f"global ADR index → {out}")
    else:
        out = render_index(args.dir)
        print(f"per-project ADR index → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
