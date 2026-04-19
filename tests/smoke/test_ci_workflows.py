"""Smoke tests for T-15 CI workflows — validate YAML + key structure.

We don't actually run GH Actions here; we assert the files parse as YAML
and contain the load-bearing fields the CI/nightly contract requires.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.smoke

REPO = Path(__file__).resolve().parents[2]
CI = REPO / ".github" / "workflows" / "ci.yml"
NIGHTLY = REPO / ".github" / "workflows" / "nightly.yml"
README = REPO / "README.md"


def _load(path: Path) -> dict:
    assert path.exists(), f"missing workflow: {path}"
    # PyYAML parses `on:` key as Python True (bool); that's fine — we look
    # up by the string form via raw text too where it matters.
    return yaml.safe_load(path.read_text())


def test_ci_yml_parses() -> None:
    data = _load(CI)
    assert data["name"] == "CI"
    # `on` becomes True under YAML 1.1 — check either spelling.
    trigger = data.get("on") or data.get(True)
    assert trigger, "ci.yml missing trigger block"
    assert "push" in trigger
    assert "pull_request" in trigger
    jobs = data["jobs"]
    assert "test" in jobs
    steps = jobs["test"]["steps"]
    step_names = [s.get("name", "") for s in steps]
    assert any("smoke + integration" in n.lower() for n in step_names)
    # Must run smoke OR integration (not just e2e) on push CI.
    raw = CI.read_text()
    assert '-m "smoke or integration"' in raw
    assert "e2e" not in raw.split("Run smoke")[1].split("Shell")[0], (
        "push-CI must not run e2e (requires local taskmaster)"
    )


def test_nightly_yml_parses() -> None:
    data = _load(NIGHTLY)
    assert data["name"] == "Nightly"
    trigger = data.get("on") or data.get(True)
    assert trigger and "schedule" in trigger
    # cron must be 08:00 UTC (≈ 09:00 Europe/Warsaw winter/summer compromise).
    crons = trigger["schedule"]
    assert any(c.get("cron") == "0 8 * * *" for c in crons)
    raw = NIGHTLY.read_text()
    assert "playwright" in raw.lower()
    assert "task-master-ai" in raw
    assert "-m e2e" in raw


def test_readme_has_ci_badges() -> None:
    assert README.exists(), "README.md is required for T-15 status badge"
    content = README.read_text()
    assert "ci.yml/badge.svg" in content, "CI badge missing in README"
    assert "nightly.yml/badge.svg" in content, "Nightly badge missing in README"
