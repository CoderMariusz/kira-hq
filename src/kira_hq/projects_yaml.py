"""projects.yaml v2 schema — PRD §6.6.

Loads and validates ~/.kira-hq/projects.yaml. Uses pydantic for validation.
Migration from v1 provided via scripts/migrate_projects_yaml.py (imports from here).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import List, Literal, Optional, Union

import yaml
from pydantic import BaseModel, Field, field_validator

DEFAULT_PROJECTS_YAML = Path.home() / ".kira-hq" / "projects.yaml"

# Defaults used by migration and new entries
DEFAULT_BUDGET_MONTHLY = 500_000
DEFAULT_BUDGET_PER_RUN = 50_000
DEFAULT_SKILLS = ["kira-hq-render-kanban"]
DEFAULT_PRIORITY = "medium"


class ProjectEntryV2(BaseModel):
    """One entry under `projects:` in projects.yaml v2."""

    name: str
    path: str
    status: Literal["active", "stale", "archived"] = "active"
    priority: Literal["high", "medium", "low"] = DEFAULT_PRIORITY  # type: ignore[assignment]
    cron: str = "0 */1 * * *"
    added_at: Union[date, str] = Field(default_factory=lambda: date.today().isoformat())
    skills: List[str] = Field(default_factory=lambda: list(DEFAULT_SKILLS))
    budget_tokens_monthly: int = DEFAULT_BUDGET_MONTHLY
    budget_tokens_per_run: int = DEFAULT_BUDGET_PER_RUN
    notes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be empty")
        return v

    @field_validator("added_at")
    @classmethod
    def added_at_iso(cls, v) -> str:
        """Normalize to YYYY-MM-DD string regardless of input (date or str)."""
        if isinstance(v, date):
            return v.isoformat()
        return str(v)


class ProjectsYamlV2(BaseModel):
    """Top-level schema for projects.yaml v2."""

    version: Literal[2] = 2  # type: ignore[assignment]
    projects: List[ProjectEntryV2]


def load(path: Union[str, Path] = DEFAULT_PROJECTS_YAML) -> ProjectsYamlV2:
    """Load and validate projects.yaml. Raises pydantic.ValidationError on mismatch."""
    p = Path(path).expanduser()
    data = yaml.safe_load(p.read_text()) or {}
    return ProjectsYamlV2.model_validate(data)


def detect_version(path: Union[str, Path] = DEFAULT_PROJECTS_YAML) -> int:
    """Returns 1 or 2 based on presence of `version` field."""
    p = Path(path).expanduser()
    data = yaml.safe_load(p.read_text()) or {}
    return int(data.get("version", 1))


def migrate_entry_v1_to_v2(entry: dict) -> dict:
    """Pure function: single v1 entry → v2 entry dict. Uses defaults for missing fields."""
    return {
        "name": entry["name"],
        "path": entry["path"],
        "status": entry.get("status", "active"),
        "priority": entry.get("priority", DEFAULT_PRIORITY),
        # v1 had night_crew_cron; v2 renames to cron
        "cron": entry.get("cron") or entry.get("night_crew_cron") or "0 */1 * * *",
        "added_at": entry.get("added_at", date.today().isoformat()),
        "skills": entry.get("skills", list(DEFAULT_SKILLS)),
        "budget_tokens_monthly": entry.get("budget_tokens_monthly", DEFAULT_BUDGET_MONTHLY),
        "budget_tokens_per_run": entry.get("budget_tokens_per_run", DEFAULT_BUDGET_PER_RUN),
        "notes": entry.get("notes"),
    }


def migrate_v1_to_v2(v1_data: dict) -> dict:
    """Pure function: whole v1 document → v2 document dict."""
    return {
        "version": 2,
        "projects": [migrate_entry_v1_to_v2(e) for e in v1_data.get("projects", [])],
    }
