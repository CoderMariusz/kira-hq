"""Smoke tests for scripts/render_adr_index.py — PRD §6.8."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from render_adr_index import (
    ADRParseError,
    collect,
    last_n,
    parse_adr,
    render_global,
    render_index,
)

pytestmark = pytest.mark.smoke


def _write_adr(dir_: Path, number: int, title: str,
               status: str = "accepted",
               date: str = "2026-04-18",
               slug: str | None = None) -> Path:
    slug = slug or title.lower().replace(" ", "-")
    name = f"{number:04d}-{slug}.md"
    p = dir_ / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"# ADR {number:04d}: {title}\n\n"
        f"- **Date:** {date}\n"
        f"- **Status:** {status}\n\n"
        "## Context\nctx\n\n## Decision\ndec\n\n## Consequences\ncons\n"
    )
    return p


def test_parse_adr_happy_path(tmp_path):
    p = _write_adr(tmp_path, 1, "Use FastAPI")
    adr = parse_adr(p)
    assert adr.number == 1
    assert adr.title == "Use FastAPI"
    assert adr.status == "accepted"
    assert adr.date == "2026-04-18"


def test_parse_adr_rejects_bad_filename(tmp_path):
    bad = tmp_path / "random.md"
    bad.write_text("# ADR 0001: Nope\n- **Date:** 2026-04-18\n- **Status:** proposed\n")
    with pytest.raises(ADRParseError, match="filename must match"):
        parse_adr(bad)


def test_parse_adr_heading_mismatch(tmp_path):
    p = tmp_path / "0002-wrong.md"
    p.write_text("# ADR 0005: Wrong\n- **Date:** 2026-04-18\n- **Status:** proposed\n")
    with pytest.raises(ADRParseError, match="mismatches filename"):
        parse_adr(p)


def test_parse_adr_missing_fields(tmp_path):
    p = tmp_path / "0003-incomplete.md"
    p.write_text("# ADR 0003: Incomplete\n\nno fields\n")
    with pytest.raises(ADRParseError):
        parse_adr(p)


def test_collect_sorts_by_number_and_ignores_non_adr(tmp_path):
    _write_adr(tmp_path, 3, "Three")
    _write_adr(tmp_path, 1, "One")
    _write_adr(tmp_path, 2, "Two")
    (tmp_path / "README.md").write_text("not an ADR\n")
    (tmp_path / "INDEX.md").write_text("would be overwritten\n")
    adrs = collect(tmp_path)
    assert [a.number for a in adrs] == [1, 2, 3]


def test_render_index_writes_sorted_table(tmp_path):
    _write_adr(tmp_path, 1, "Use FastAPI", status="accepted")
    _write_adr(tmp_path, 2, "Localhost first", status="proposed",
               date="2026-04-17")
    out = render_index(tmp_path)
    assert out == tmp_path / "INDEX.md"
    content = out.read_text()
    assert "| 0001 |" in content
    assert "| 0002 |" in content
    # Order: 0001 before 0002
    assert content.index("0001") < content.index("0002")
    assert "Use FastAPI" in content
    assert "accepted" in content and "proposed" in content


def test_last_n_returns_highest_numbers_desc(tmp_path):
    for i in range(1, 8):
        _write_adr(tmp_path, i, f"Adr {i}")
    last = last_n(tmp_path, n=5)
    assert [a.number for a in last] == [7, 6, 5, 4, 3]


def test_render_index_on_empty_dir(tmp_path):
    out = render_index(tmp_path)
    assert "_No ADRs yet._" in out.read_text()


def test_render_global_aggregates_across_projects(tmp_path):
    # Two fake projects, each with its own ADR dir
    proj_a = tmp_path / "alpha"
    proj_b = tmp_path / "beta"
    (proj_a / "docs" / "ADR").mkdir(parents=True)
    (proj_b / "docs" / "ADR").mkdir(parents=True)
    _write_adr(proj_a / "docs" / "ADR", 1, "A-one")
    _write_adr(proj_b / "docs" / "ADR", 1, "B-one")
    _write_adr(proj_b / "docs" / "ADR", 2, "B-two")

    yaml_path = tmp_path / "projects.yaml"
    yaml_path.write_text(yaml.safe_dump({
        "version": 2,
        "projects": [
            {"name": "alpha", "path": str(proj_a), "status": "active",
             "priority": "high", "cron": "0 */2 * * *", "added_at": "2026-04-18",
             "skills": ["kira-hq-render-kanban"],
             "budget_tokens_monthly": 500_000, "budget_tokens_per_run": 50_000},
            {"name": "beta", "path": str(proj_b), "status": "active",
             "priority": "medium", "cron": "0 */4 * * *", "added_at": "2026-04-18",
             "skills": ["kira-hq-render-kanban"],
             "budget_tokens_monthly": 500_000, "budget_tokens_per_run": 50_000},
        ],
    }))
    out = render_global(yaml_path, tmp_path / "global-adrs.md")
    content = out.read_text()
    assert "## alpha" in content and "## beta" in content
    assert "A-one" in content and "B-one" in content and "B-two" in content


def test_render_global_skips_archived(tmp_path):
    proj = tmp_path / "archived-proj"
    (proj / "docs" / "ADR").mkdir(parents=True)
    _write_adr(proj / "docs" / "ADR", 1, "Should not appear")

    yaml_path = tmp_path / "projects.yaml"
    yaml_path.write_text(yaml.safe_dump({
        "version": 2,
        "projects": [{
            "name": "archived-proj", "path": str(proj), "status": "archived",
            "priority": "low", "cron": "0 */6 * * *", "added_at": "2026-04-18",
            "skills": ["kira-hq-render-kanban"],
            "budget_tokens_monthly": 500_000, "budget_tokens_per_run": 50_000,
        }],
    }))
    out = render_global(yaml_path, tmp_path / "global-adrs.md")
    assert "Should not appear" not in out.read_text()
    assert "## archived-proj" not in out.read_text()


def test_render_global_links_are_navigable_from_out_dir(tmp_path):
    """PR#1 P2 regression: global-adrs.md must link each ADR via a path that
    resolves, not via the bare filename."""
    proj = tmp_path / "alpha"
    adr_dir = proj / "docs" / "ADR"
    adr_dir.mkdir(parents=True)
    _write_adr(adr_dir, 1, "Use FastAPI")

    yaml_path = tmp_path / "projects.yaml"
    yaml_path.write_text(yaml.safe_dump({
        "version": 2,
        "projects": [{
            "name": "alpha", "path": str(proj), "status": "active",
            "priority": "high", "cron": "0 */2 * * *",
            "added_at": "2026-04-18",
            "skills": ["kira-hq-render-kanban"],
            "budget_tokens_monthly": 500_000, "budget_tokens_per_run": 50_000,
        }],
    }))

    # Place global-adrs.md in a neutral dir that is NOT an ancestor of adr_dir
    global_dir = tmp_path / "global-home"
    global_dir.mkdir()
    out = render_global(yaml_path, global_dir / "global-adrs.md")
    content = out.read_text()

    # Extract the markdown link target for "Use FastAPI"
    import re
    m = re.search(r"\[Use FastAPI\]\(([^)]+)\)", content)
    assert m, f"link for Use FastAPI not found in: {content}"
    link = m.group(1)

    # Resolve the link relative to the global-adrs.md directory and verify
    # it points to the actual ADR file on disk.
    resolved = (global_dir / link).resolve()
    expected = (adr_dir / "0001-use-fastapi.md").resolve()
    assert resolved == expected, f"link {link!r} → {resolved} != {expected}"
    # Must NOT be just the bare filename (the old broken behaviour).
    assert link != "0001-use-fastapi.md"
