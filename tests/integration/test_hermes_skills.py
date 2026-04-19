"""Integration tests for shared Hermes skill runners — T-20 Module 4."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

SKILLS_SHARED = Path.home() / ".kira-hq" / "skills-shared"
REPORT_RUN = SKILLS_SHARED / "kira-hq-report" / "run.py"
WEEKLY_RUN = SKILLS_SHARED / "kira-weekly-review" / "run.py"
ADD_PROJECT_SKILL = SKILLS_SHARED / "kira-add-project" / "SKILL.md"


def test_report_runner_emits_json(tmp_path):
    log = tmp_path / "pipeline.log.md"
    log.write_text(
        "| timestamp | project | skill | provider | expand_used | tokens_in | tokens_out | status | duration_s | notes |\n"
        "|-----------|---------|-------|----------|-------------|-----------|------------|--------|------------|-------|\n"
        "| 2026-04-17T03:00:00+00:00 | p1 | render | sonnet | false | 10 | 20 | ok | 1.0 | a |\n"
    )
    result = subprocess.run(
        [sys.executable, str(REPORT_RUN), "--pipeline-log", str(log), "--since", "2026-04-17T02:00:00+00:00"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["runs"] == 1
    assert payload["projects"] == ["p1"]


def test_weekly_review_runner_writes_output_file(tmp_path):
    log = tmp_path / "pipeline.log.md"
    log.write_text(
        "| timestamp | project | skill | provider | expand_used | tokens_in | tokens_out | status | duration_s | notes |\n"
        "|-----------|---------|-------|----------|-------------|-----------|------------|--------|------------|-------|\n"
        "| 2026-04-15T03:00:00+00:00 | p2 | other-skill | kimi | false | 500 | 400 | fail | 1.0 | b |\n"
    )
    snaps = tmp_path / "snaps"
    for d in ["2026-04-09", "2026-04-10", "2026-04-11", "2026-04-12", "2026-04-13", "2026-04-14", "2026-04-15"]:
        (snaps / d).mkdir(parents=True)
    reviews = tmp_path / "reviews"
    result = subprocess.run(
        [
            sys.executable,
            str(WEEKLY_RUN),
            "--pipeline-log",
            str(log),
            "--snapshots-dir",
            str(snaps),
            "--reviews-dir",
            str(reviews),
            "--now",
            "2026-04-15T09:00:00+00:00",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    out = Path(result.stdout.strip())
    assert out.exists()
    assert out.read_text().startswith("# Weekly review")


def test_add_project_skill_frontmatter_is_hermes_compatible():
    text = ADD_PROJECT_SKILL.read_text()
    assert text.startswith("---\nname: kira-add-project\n")
    assert "description:" in text
    assert "# kira-add-project" in text
