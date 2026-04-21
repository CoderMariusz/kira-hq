"""Smoke tests for Task 23 docs — README + DOD checklist."""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.smoke

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_top_level_readme_opens_with_prd_sections():
    text = (REPO_ROOT / "README.md").read_text()
    assert "## Vision" in text
    assert "## Users" in text
    assert "## Architecture" in text
    assert "HERMES" in text
    assert "KIRA-HQ" in text
    assert "PROJECTS" in text


def test_dod_checklist_lists_six_criteria_per_module():
    text = (REPO_ROOT / "DOD_CHECKLIST.md").read_text()
    for module in ("Module 1", "Module 2", "Module 3", "Module 4"):
        assert f"## {module}" in text
    for criterion in (
        "All planned features implemented",
        "Smoke tests pass",
        "Integration tests pass",
        "E2E browser test passes",
        "README present and documents inputs/outputs/error modes",
        "Pipeline log entries seen in the last 24 hours",
    ):
        assert text.count(criterion) == 4
