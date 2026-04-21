"""Integration tests for shared Hermes skill runners — T-20 Module 4."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO_ROOT = Path(__file__).resolve().parents[2]


def _build_skills_shared(tmp_path: Path) -> Path:
    shared = tmp_path / "skills-shared"

    report_dir = shared / "kira-hq-report"
    report_dir.mkdir(parents=True)
    (report_dir / "run.py").write_text(textwrap.dedent(
        """
        from kira_hq.skills.report import main

        if __name__ == "__main__":
            raise SystemExit(main())
        """
    ).strip() + "\n")

    weekly_dir = shared / "kira-weekly-review"
    weekly_dir.mkdir(parents=True)
    (weekly_dir / "run.py").write_text(textwrap.dedent(
        """
        from kira_hq.skills.weekly_review import main

        if __name__ == "__main__":
            raise SystemExit(main())
        """
    ).strip() + "\n")

    add_project_dir = shared / "kira-add-project"
    add_project_dir.mkdir(parents=True)
    (add_project_dir / "SKILL.md").write_text(textwrap.dedent(
        """
        ---
        name: kira-add-project
        description: Use to onboard a new project into Kira-HQ. Validates git+taskmaster+PRD, updates projects.yaml v2, creates .env, symlinks chosen skills, runs first kanban render.
        ---

        # kira-add-project

        Delegates to CLI: `kira-hq add-project <path> --name=... --priority=... --cron=... --budget-monthly=... --budget-per-run=... --skill=... --yes`.

        See PRD §6.9 for the 9-step behavior.
        """
    ).strip() + "\n")

    return shared


def _runner_env() -> dict[str, str]:
    env = os.environ.copy()
    pythonpath_parts = [str(REPO_ROOT / "src")]
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return env


def test_report_runner_emits_json_and_appends_pipeline_log(tmp_path: Path):
    skills_shared = _build_skills_shared(tmp_path)
    log = tmp_path / "pipeline.log.md"
    log.write_text(
        "| timestamp | project | skill | provider | expand_used | tokens_in | tokens_out | status | duration_s | notes |\n"
        "|-----------|---------|-------|----------|-------------|-----------|------------|--------|------------|-------|\n"
        "| 2026-04-17T03:00:00 | p1 | render | sonnet | false | 10 | 20 | ok | 1.0 | a |\n"
        "| 2026-04-17T04:00:00 | p2 | execute | kimi | true | 5 | 8 | fail | 2.0 | blocker: task crashed |\n"
    )
    before = log.read_text()
    result = subprocess.run(
        [sys.executable, str(skills_shared / "kira-hq-report" / "run.py"), "--pipeline-log", str(log), "--since", "2026-04-17T02:00:00+00:00"],
        capture_output=True,
        text=True,
        check=False,
        env=_runner_env(),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["runs"] == 2
    assert payload["projects"] == ["p1", "p2"]
    assert payload["blockers"] == [
        {
            "project": "p2",
            "skill": "execute",
            "timestamp": "2026-04-17T04:00:00",
            "notes": "blocker: task crashed",
        }
    ]
    after = log.read_text()
    assert after.startswith(before)
    assert "| kira-hq | kira-hq-report |" in after


def test_weekly_review_runner_writes_output_file_and_appends_pipeline_log(tmp_path: Path):
    skills_shared = _build_skills_shared(tmp_path)
    log = tmp_path / "pipeline.log.md"
    log.write_text(
        "| timestamp | project | skill | provider | expand_used | tokens_in | tokens_out | status | duration_s | notes |\n"
        "|-----------|---------|-------|----------|-------------|-----------|------------|--------|------------|-------|\n"
        "| 2026-04-15T03:00:00 | p2 | other-skill | kimi | false | 500 | 400 | fail | 1.0 | b |\n"
    )
    before = log.read_text()
    snaps = tmp_path / "snaps"
    for d in ["2026-04-13", "2026-04-14", "2026-04-15", "2026-04-16", "2026-04-17", "2026-04-18", "2026-04-19"]:
        (snaps / d).mkdir(parents=True)
    reviews = tmp_path / "reviews"
    result = subprocess.run(
        [
            sys.executable,
            str(skills_shared / "kira-weekly-review" / "run.py"),
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
        env=_runner_env(),
    )
    assert result.returncode == 0, result.stderr
    out = Path(result.stdout.strip())
    assert out.exists()
    assert out.name == "2026-W16.md"
    telegram_summary = reviews / "2026-W16.telegram.txt"
    assert telegram_summary.exists()
    assert "Reporting window: 2026-04-13 to 2026-04-19" in out.read_text()
    assert f"Telegram summary artifact: {telegram_summary}" in out.read_text()
    after = log.read_text()
    assert after.startswith(before)
    assert "| kira-hq | kira-weekly-review | hermes | false | 0 | 0 | ok |" in after
    assert f"wrote {out}" in after
    assert f"telegram_summary={telegram_summary}" in after


def test_add_project_skill_frontmatter_is_hermes_compatible(tmp_path: Path):
    skills_shared = _build_skills_shared(tmp_path)
    text = (skills_shared / "kira-add-project" / "SKILL.md").read_text()
    assert text.startswith("---\nname: kira-add-project\n")
    assert "description:" in text
    assert "# kira-add-project" in text
