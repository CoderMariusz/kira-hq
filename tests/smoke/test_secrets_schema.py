"""Smoke tests for secrets_schema — PRD §6.5."""
from __future__ import annotations

import os
import warnings
from pathlib import Path

import pytest

from kira_hq.secrets_schema import (
    SCHEMA_KEYS,
    InsecurePermissionsWarning,
    check_permissions,
    load_secrets,
    missing_keys,
    parse_env_file,
)

pytestmark = pytest.mark.smoke


def _write_env(path: Path, content: str, mode: int = 0o600) -> None:
    path.write_text(content)
    os.chmod(path, mode)


def test_parse_basic(tmp_path):
    f = tmp_path / ".env"
    _write_env(f, "FOO=bar\nBAZ=qux\n")
    assert parse_env_file(f) == {"FOO": "bar", "BAZ": "qux"}


def test_parse_comments_blank_export_quotes(tmp_path):
    f = tmp_path / ".env"
    _write_env(
        f,
        "# comment\n"
        "\n"
        "export FOO=hello\n"
        "QUOTED=\"spa ced\"\n"
        "SINGLE='1 2 3'\n"
        "INLINE=val # trailing\n",
    )
    out = parse_env_file(f)
    assert out == {
        "FOO": "hello",
        "QUOTED": "spa ced",
        "SINGLE": "1 2 3",
        "INLINE": "val",
    }


def test_parse_missing_file(tmp_path):
    assert parse_env_file(tmp_path / "nope.env") == {}


def test_load_secrets_global_only(tmp_path):
    g = tmp_path / ".env"
    _write_env(g, "TELEGRAM_BOT_TOKEN=abc\nKIRA_HQ_USER=m\n")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        out = load_secrets(global_env=g)
    assert out["TELEGRAM_BOT_TOKEN"] == "abc"
    assert out["KIRA_HQ_USER"] == "m"


def test_load_secrets_project_override(tmp_path):
    g = tmp_path / "global.env"
    _write_env(g, "GITHUB_TOKEN=global\nKIRA_HQ_USER=global\n")
    projects = tmp_path / "projects"
    proj = projects / "kira-hq"
    proj.mkdir(parents=True)
    pe = proj / ".env"
    _write_env(pe, "KIRA_HQ_USER=project\n")

    out = load_secrets("kira-hq", global_env=g, projects_root=projects)
    assert out["GITHUB_TOKEN"] == "global"      # global kept
    assert out["KIRA_HQ_USER"] == "project"     # project wins


def test_insecure_permissions_warn(tmp_path):
    g = tmp_path / ".env"
    _write_env(g, "FOO=bar\n", mode=0o644)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        check_permissions(g)
    assert any(issubclass(w.category, InsecurePermissionsWarning) for w in caught)


def test_missing_keys_reports_absent():
    secrets = {"TELEGRAM_BOT_TOKEN": "x", "KIRA_HQ_USER": "m"}
    absent = missing_keys(secrets)
    for k in SCHEMA_KEYS:
        if k in ("TELEGRAM_BOT_TOKEN", "KIRA_HQ_USER"):
            assert k not in absent
        else:
            assert k in absent
