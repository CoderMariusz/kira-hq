"""Smoke tests for kira_hq.projects_yaml (PRD §6.6)."""
from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import pytest  # noqa: E402
import yaml  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from kira_hq.projects_yaml import (  # noqa: E402
    detect_version,
    load,
    migrate_entry_v1_to_v2,
)


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def test_v2_load_happy_path(tmp_path):
    p = tmp_path / "projects.yaml"
    _write_yaml(p, {
        "version": 2,
        "projects": [{
            "name": "kira-hq",
            "path": "~/Projects/kira-hq",
            "status": "active",
            "priority": "high",
            "cron": "0 */2 * * *",
            "added_at": "2026-04-16",
            "skills": ["kira-hq-render-kanban", "kira-hq-execute"],
            "budget_tokens_monthly": 500000,
            "budget_tokens_per_run": 50000,
            "notes": "Self-managing",
        }],
    })
    doc = load(p)
    assert doc.version == 2
    assert len(doc.projects) == 1
    proj = doc.projects[0]
    assert proj.name == "kira-hq"
    assert proj.priority == "high"
    assert proj.budget_tokens_monthly == 500000


def test_v2_defaults_fill_in(tmp_path):
    p = tmp_path / "projects.yaml"
    _write_yaml(p, {
        "version": 2,
        "projects": [{"name": "x", "path": "/tmp/x"}],
    })
    proj = load(p).projects[0]
    assert proj.status == "active"
    assert proj.priority == "medium"
    assert proj.skills == ["kira-hq-render-kanban"]
    assert proj.budget_tokens_monthly == 500000


def test_invalid_priority_rejected(tmp_path):
    p = tmp_path / "projects.yaml"
    _write_yaml(p, {
        "version": 2,
        "projects": [{"name": "x", "path": "/tmp/x", "priority": "URGENT"}],
    })
    with pytest.raises(ValidationError):
        load(p)


def test_detect_version_v1(tmp_path):
    p = tmp_path / "projects.yaml"
    _write_yaml(p, {"projects": [{"name": "x", "path": "/tmp"}]})  # no version
    assert detect_version(p) == 1


def test_detect_version_v2(tmp_path):
    p = tmp_path / "projects.yaml"
    _write_yaml(p, {"version": 2, "projects": []})
    assert detect_version(p) == 2


def test_migrate_entry_keeps_night_crew_cron_as_cron():
    v1 = {"name": "old", "path": "/x", "night_crew_cron": "15 */3 * * *"}
    v2 = migrate_entry_v1_to_v2(v1)
    assert v2["cron"] == "15 */3 * * *"


def test_migrate_entry_fills_defaults():
    v1 = {"name": "old", "path": "/x"}
    v2 = migrate_entry_v1_to_v2(v1)
    assert v2["status"] == "active"
    assert v2["priority"] == "medium"
    assert v2["skills"] == ["kira-hq-render-kanban"]
    assert v2["budget_tokens_monthly"] == 500000
