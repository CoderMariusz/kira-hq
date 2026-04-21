"""Smoke tests for kira_hq.pipeline_log — PRD §6.1."""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
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


def test_pipe_in_notes_escaped_roundtrip(tmp_path):
    """Regression: free-form `notes` containing `|` must NOT split the row.

    PR#1 P2 review: raw `|` in a cell created extra columns, which
    `tokens.parse_log` dropped silently (len(cells) != 10), losing data.
    Fix escapes as `\\|` on write and un-escapes on parse.
    """
    from kira_hq.tokens import parse_log  # late import

    p = tmp_path / "pipeline.log.md"
    tricky = "task #5 | fell back to sonnet | retry=2"
    append_entry(
        p, timestamp="2026-04-19T10:00:00", project="kira-hq",
        skill="test", provider="sonnet", expand_used=False,
        tokens_in=123, tokens_out=45, status="ok", duration_s=1.0,
        notes=tricky,
    )
    # 1. Raw file keeps each row as one line; 2 pipes in `notes` are escaped
    line = [ln for ln in p.read_text().splitlines() if "task #5" in ln][0]
    assert line.count(r"\|") == 2  # the two `|` inside notes got escaped
    # Subtract escaped pipes to get real column boundaries
    real_pipes = line.count("|") - line.count(r"\|")
    assert real_pipes == 11  # 10 cells → 11 real pipes
    # 2. Parser round-trips the original notes
    rows = parse_log(p)
    assert len(rows) == 1
    assert rows[0].tokens_in == 123
    assert rows[0].notes == tricky


def test_newline_in_notes_does_not_break_table(tmp_path):
    """Regression: notes with literal \\n must not span table rows."""
    from kira_hq.tokens import parse_log

    p = tmp_path / "log.md"
    append_entry(
        p, timestamp="2026-04-19T10:00:00", project="x", skill="s",
        provider="sonnet", expand_used=False, tokens_in=1, tokens_out=1,
        status="ok", duration_s=0.1, notes="line1\nline2",
    )
    rows = parse_log(p)
    assert len(rows) == 1
    assert "↵" in rows[0].notes


def test_concurrent_appends_keep_single_header(tmp_path):
    p = tmp_path / "parallel.log.md"

    def _append(i: int) -> None:
        append_entry(
            p,
            timestamp=f"2026-04-19T10:00:{i:02d}",
            project="kira-hq",
            skill=f"task-{i}",
            provider="sonnet",
            expand_used=False,
            tokens_in=i,
            tokens_out=i,
            status="ok",
            duration_s=0.1,
            notes=f"row-{i}",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_append, range(12)))

    content = p.read_text()
    assert content.count("| timestamp") == 1
    assert sum(1 for line in content.splitlines() if "| kira-hq | task-" in line) == 12
