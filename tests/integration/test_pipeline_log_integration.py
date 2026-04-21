"""Integration: multi-project writers feed both local and global logs."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kira_hq import pipeline_log  # noqa: E402
from kira_hq.pipeline_log import log_execution  # noqa: E402


def test_log_execution_writes_both_local_and_global(tmp_path):
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    fake_global = tmp_path / ".kira-hq" / "global-pipeline.log.md"

    with patch.object(pipeline_log, "GLOBAL_LOG", fake_global):
        log_execution(
            project_path=project_a, project="project-a", skill="renderer",
            provider="sonnet-4.6", expand_used=False, tokens_in=0, tokens_out=0,
            status="ok", duration_s=1.1,
        )
        log_execution(
            project_path=project_b, project="project-b", skill="night-crew",
            provider="kimi-2.6", expand_used=True, tokens_in=12000, tokens_out=3500,
            status="ok", duration_s=45.2, notes="3 subtasks",
        )

    # Local logs have only their own project rows
    a_log = (project_a / "pipeline.log.md").read_text()
    b_log = (project_b / "pipeline.log.md").read_text()
    assert "project-a" in a_log and "project-b" not in a_log
    assert "project-b" in b_log and "project-a" not in b_log

    # Global has both
    g_log = fake_global.read_text()
    assert "project-a" in g_log and "project-b" in g_log

    # Header appears exactly once per file
    for log_text in (a_log, b_log, g_log):
        assert log_text.count("| timestamp") == 1


def test_timestamp_auto_filled_when_omitted(tmp_path):
    fake_global = tmp_path / "global.log.md"
    with patch.object(pipeline_log, "GLOBAL_LOG", fake_global):
        log_execution(
            project_path=tmp_path, project="x", skill="y",
            provider="sonnet-4.6", expand_used=False, tokens_in=0, tokens_out=0,
            status="ok", duration_s=0.1,
        )
    # Should have an ISO-8601-looking row (e.g. 2026-04-18T...)
    content = fake_global.read_text()
    row = [line for line in content.split("\n") if "| x |" in line][0]
    assert "2026-" in row or "2027-" in row  # future-proof
