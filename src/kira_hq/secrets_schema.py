"""Secrets loader — PRD §6.5.

Loads `~/.kira-hq/.env` (global) + `~/Projects/<name>/.env` (per-project),
with per-project values taking precedence. Warns if either file is
world/group-readable (chmod should be 600).

Usage:
    from kira_hq.secrets_schema import load_secrets
    secrets = load_secrets("kira-hq")
    tok = secrets["TELEGRAM_BOT_TOKEN"]

No dependency on python-dotenv — we parse a minimal .env subset ourselves
(`KEY=value`, `export KEY=value`, `#` comments, blank lines, optional
single/double quoted values). Values are NOT os.environ-injected; the
returned dict is the contract.

Schema keys (documented in docs/SECRETS.md):
    TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_CHATS,
    OPENROUTER_API_KEY, MINIMAX_API_KEY,
    GITHUB_TOKEN,
    KIRA_HQ_USER, KIRA_HQ_PASS
"""
from __future__ import annotations

import os
import stat
import warnings
from pathlib import Path
from typing import Dict, Iterable, Optional, Union

PathLike = Union[str, Path]

GLOBAL_ENV = Path.home() / ".kira-hq" / ".env"
PROJECTS_ROOT = Path.home() / "Projects"

# Canonical keys from PRD §6.5 — used for docs & optional validation
SCHEMA_KEYS = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_ALLOWED_CHATS",
    "OPENROUTER_API_KEY",
    "MINIMAX_API_KEY",
    "GITHUB_TOKEN",
    "KIRA_HQ_USER",
    "KIRA_HQ_PASS",
)


class InsecurePermissionsWarning(UserWarning):
    """Raised when a .env file is group- or world-readable."""


def _strip_quotes(val: str) -> str:
    if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
        return val[1:-1]
    return val


def parse_env_file(path: PathLike) -> Dict[str, str]:
    """Parse a .env file into a dict. Returns {} if file missing."""
    p = Path(path)
    if not p.exists():
        return {}
    out: Dict[str, str] = {}
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        # strip inline comments only if value unquoted
        value = value.strip()
        if value and value[0] not in ("'", '"'):
            hash_idx = value.find(" #")
            if hash_idx != -1:
                value = value[:hash_idx].rstrip()
        out[key] = _strip_quotes(value)
    return out


def check_permissions(path: PathLike) -> bool:
    """Warn if file is group- or world-readable. Returns True if secure."""
    p = Path(path)
    if not p.exists():
        return True
    mode = p.stat().st_mode
    if mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH):
        warnings.warn(
            f"{p} has insecure permissions (mode={oct(mode & 0o777)}); "
            f"run: chmod 600 {p}",
            InsecurePermissionsWarning,
            stacklevel=2,
        )
        return False
    return True


def project_env_path(project_name: str, projects_root: Optional[PathLike] = None) -> Path:
    root = Path(projects_root) if projects_root else PROJECTS_ROOT
    return root / project_name / ".env"


def load_secrets(
    project_name: Optional[str] = None,
    *,
    global_env: Optional[PathLike] = None,
    projects_root: Optional[PathLike] = None,
    check_perms: bool = True,
) -> Dict[str, str]:
    """Load merged secrets. Per-project values override global values.

    Args:
        project_name: If given, merge `<projects_root>/<name>/.env` on top of global.
        global_env: Override path for ~/.kira-hq/.env (tests).
        projects_root: Override for ~/Projects (tests).
        check_perms: Emit InsecurePermissionsWarning if files not chmod 600.
    """
    g_path = Path(global_env) if global_env else GLOBAL_ENV
    if check_perms:
        check_permissions(g_path)
    merged: Dict[str, str] = dict(parse_env_file(g_path))

    if project_name:
        p_path = project_env_path(project_name, projects_root)
        if check_perms:
            check_permissions(p_path)
        merged.update(parse_env_file(p_path))

    return merged


def missing_keys(
    secrets: Dict[str, str],
    required: Iterable[str] = SCHEMA_KEYS,
) -> list[str]:
    """Return list of SCHEMA_KEYS absent or empty in secrets."""
    return [k for k in required if not secrets.get(k)]


__all__ = [
    "SCHEMA_KEYS",
    "GLOBAL_ENV",
    "InsecurePermissionsWarning",
    "parse_env_file",
    "check_permissions",
    "project_env_path",
    "load_secrets",
    "missing_keys",
]
