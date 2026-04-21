"""Top-level `kira-hq` CLI dispatcher."""
from __future__ import annotations

import argparse
import sys
from typing import Sequence

from kira_hq.cli import add_project, archive_project


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kira-hq",
        description="Kira-HQ command line interface.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("add-project", parents=[add_project._build_parser()], add_help=False)
    subparsers.add_parser("archive-project", parents=[archive_project._build_parser()], add_help=False)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        _build_parser().print_help()
        return 0
    try:
        if args[0] == "add-project":
            return add_project.main(args[1:])
        if args[0] == "archive-project":
            return archive_project.main(args[1:])
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else 0
    if args[0] in {"-h", "--help"}:
        _build_parser().print_help()
        return 0
    raise SystemExit(f"unknown command: {args[0]}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
