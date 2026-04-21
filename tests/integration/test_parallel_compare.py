"""RED tests for Task 22 Track A weekly comparator."""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SCRIPT_PATH = ROOT / "scripts" / "parallel_track_compare.py"

pytestmark = pytest.mark.integration


def _load_parallel_compare_module():
    if not SCRIPT_PATH.exists():
        pytest.fail(
            "Missing implementation target: scripts/parallel_track_compare.py "
            "(Task 22 Track A comparator entrypoint)."
        )

    spec = importlib.util.spec_from_file_location("parallel_track_compare", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        pytest.fail(f"Unable to load comparator module from {SCRIPT_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_weekly_track_comparison_renders_track_a_markdown_table(pipeline_log_tmp):
    pipeline_log_tmp.append(
        timestamp="2026-04-13T12:00:00+00:00",
        project="alpha",
        skill="planner",
        provider="sonnet",
        tokens_in=100,
        tokens_out=50,
        status="ok",
        duration_s=10.0,
        notes="track=A tasks_completed=2 alerts=0",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-14T09:30:00+00:00",
        project="alpha",
        skill="executor",
        provider="sonnet",
        tokens_in=30,
        tokens_out=20,
        status="fail",
        duration_s=20.0,
        notes="track=A tasks_completed=1 alerts=1 incident=INC-100",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-15T11:00:00+00:00",
        project="beta",
        skill="planner",
        provider="claude-code",
        tokens_in=80,
        tokens_out=20,
        status="ok",
        duration_s=9.0,
        notes="track=B tasks_completed=4 alerts=0",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-16T18:45:00+00:00",
        project="beta",
        skill="executor",
        provider="claude-code",
        tokens_in=40,
        tokens_out=10,
        status="ok",
        duration_s=5.0,
        notes="track=B tasks_completed=0 alerts=2",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-17T08:15:00+00:00",
        project="ignored-no-track",
        skill="executor",
        provider="sonnet",
        tokens_in=500,
        tokens_out=500,
        status="ok",
        duration_s=99.0,
        notes="tasks_completed=99 alerts=9",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-08T08:15:00+00:00",
        project="ignored-outside-week",
        skill="executor",
        provider="sonnet",
        tokens_in=500,
        tokens_out=500,
        status="ok",
        duration_s=99.0,
        notes="track=A tasks_completed=99 alerts=9 incident=INC-999",
    )

    module = _load_parallel_compare_module()

    markdown = module.build_weekly_track_comparison(
        pipeline_log=pipeline_log_tmp.path,
        now=datetime(2026, 4, 16, 9, 0, 0, tzinfo=timezone.utc),
    )

    assert "2026-W16" in markdown
    assert "| Track | Tasks completed | Tokens | Human interventions | Alerts | Avg latency (s) |" in markdown
    assert "| A | 3 | 200 | 1 | 1 | 15.0 |" in markdown
    assert "| B | 4 | 150 | 0 | 2 | 7.0 |" in markdown
    assert "ignored-no-track" not in markdown
    assert "ignored-outside-week" not in markdown


def test_main_prints_weekly_track_comparison_markdown(pipeline_log_tmp, capsys):
    pipeline_log_tmp.append(
        timestamp="2026-04-13T12:00:00+00:00",
        project="alpha",
        skill="planner",
        provider="sonnet",
        tokens_in=12,
        tokens_out=8,
        status="ok",
        duration_s=4.0,
        notes="track=A tasks_completed=1 alerts=0",
    )
    pipeline_log_tmp.append(
        timestamp="2026-04-13T14:00:00+00:00",
        project="beta",
        skill="planner",
        provider="claude-code",
        tokens_in=10,
        tokens_out=5,
        status="ok",
        duration_s=6.0,
        notes="track=B tasks_completed=2 alerts=1 incident=INC-101",
    )

    module = _load_parallel_compare_module()

    exit_code = module.main(
        [
            "--pipeline-log",
            str(pipeline_log_tmp.path),
            "--now",
            "2026-04-16T09:00:00+00:00",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "| Track | Tasks completed | Tokens | Human interventions | Alerts | Avg latency (s) |" in captured.out
    assert "| A | 1 | 20 | 0 | 0 | 4.0 |" in captured.out
    assert "| B | 2 | 15 | 1 | 1 | 6.0 |" in captured.out
