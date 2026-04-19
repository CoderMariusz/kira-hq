"""Smoke tests for kira_hq.pipeline_log — PRD §6.1."""
from __future__ import annotations

import sys
from pathlib import Path

# Allow `import kira_hq` from src/ layout without install step
SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kira_hq.pipeline_log import append_entry, HEADER, COLUMNS  # noqa: E402


def test_append_creates_header_and_row(tmp_path):
    p = tmp_path / "pipeline.log.md"
    append_entry(
        p,
        timestamp="2026-04-18T03:00:12",
        project="kira-hq",
        skill="kira-hq-render-kanban",
        provider="sonnet-4.6",
        expand_used=False,
        tokens_in=0,
        tokens_out=0,
        status="ok",
        duration_s=1.2,
        notes="6 tasks rendered",
    )
    content = p.read_text()
    assert content.startswith("| timestamp"), "header must be on first append"
    assert "| 2026-04-18T03:00:12 | kira-hq | kira-hq-render-kanban | sonnet-4.6 | false |" in content


def test_append_no_header_on_second_call(tmp_path):
    p = tmp_path / "pipeline.log.md"
    for i in range(2):
        append_entry(
            p,
            timestamp=f"2026-04-18T03:00:{i:02d}",
            project="kira-hq",
            skill="test",
            provider="sonnet-4.6",
            expand_used=False,
            tokens_in=100,
            tokens_out=50,
            status="ok",
            duration_s=0.5,
        )
    # Exactly one header occurrence
    assert p.read_text().count("| timestamp") == 1


def test_expand_used_renders_as_boolean_string(tmp_path):
    p = tmp_path / "log.md"
    append_entry(
        p, timestamp="T1", project="p", skill="s", provider="kimi-2.6",
        expand_used=True, tokens_in=0, tokens_out=0, status="ok", duration_s=0.0,
    )
    assert "| true |" in p.read_text()


def test_schema_has_10_columns():
    assert len(COLUMNS) == 10
    # First pipe segment count in HEADER row matches
    header_line = HEADER.split("\n")[0]
    cells = [c for c in header_line.split("|") if c.strip()]
    assert len(cells) == 10
