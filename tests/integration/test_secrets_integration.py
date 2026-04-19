"""Integration tests for secrets_schema — PRD §6.5.

Exercises realistic layout: a full ~/.kira-hq/.env template + project override.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from kira_hq.secrets_schema import SCHEMA_KEYS, load_secrets, missing_keys

pytestmark = pytest.mark.integration


GLOBAL_TEMPLATE = """\
# Telegram
TELEGRAM_BOT_TOKEN=global-tg-token
TELEGRAM_ALLOWED_CHATS=111,222

# Fallback LLM
OPENROUTER_API_KEY=global-or
MINIMAX_API_KEY=global-mm

# GitHub
GITHUB_TOKEN=global-gh

# FastAPI auth
KIRA_HQ_USER=mariusz
KIRA_HQ_PASS=global-pass
"""

PROJECT_OVERRIDE = """\
# kira-hq override
GITHUB_TOKEN=project-specific-gh
KIRA_HQ_PASS=project-pass
"""


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    os.chmod(path, 0o600)


def test_full_merge_project_override(tmp_path):
    global_env = tmp_path / "kira-hq" / ".env"
    _write(global_env, GLOBAL_TEMPLATE)

    projects_root = tmp_path / "Projects"
    _write(projects_root / "kira-hq" / ".env", PROJECT_OVERRIDE)

    out = load_secrets(
        "kira-hq", global_env=global_env, projects_root=projects_root
    )

    # All required keys present
    assert missing_keys(out) == []

    # Global values survive where project doesn't override
    assert out["TELEGRAM_BOT_TOKEN"] == "global-tg-token"
    assert out["TELEGRAM_ALLOWED_CHATS"] == "111,222"
    assert out["OPENROUTER_API_KEY"] == "global-or"
    assert out["KIRA_HQ_USER"] == "mariusz"

    # Project overrides win
    assert out["GITHUB_TOKEN"] == "project-specific-gh"
    assert out["KIRA_HQ_PASS"] == "project-pass"


def test_no_project_override_falls_back_to_global(tmp_path):
    global_env = tmp_path / "kira-hq" / ".env"
    _write(global_env, GLOBAL_TEMPLATE)
    projects_root = tmp_path / "Projects"
    (projects_root / "ghost").mkdir(parents=True)  # no .env

    out = load_secrets("ghost", global_env=global_env, projects_root=projects_root)
    assert out["GITHUB_TOKEN"] == "global-gh"
    assert out["KIRA_HQ_PASS"] == "global-pass"


def test_all_schema_keys_documented_in_template():
    """Template example file must contain every PRD §6.5 key."""
    example = Path(__file__).resolve().parents[2] / "templates" / "env.kira-hq.example"
    assert example.exists(), f"missing {example}"
    content = example.read_text()
    for key in SCHEMA_KEYS:
        assert key in content, f"{key} missing from {example}"
