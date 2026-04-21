"""Integration tests for `kira-hq archive-project` — PRD §6.9 inverse."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
import yaml

from kira_hq.cli.archive_project import (
    ArchiveArgs,
    archive_project,
    EXIT_ALREADY_ARCHIVED,
    EXIT_NOT_FOUND,
)
from kira_hq.cli.add_project import AddProjectArgs, add_project

pytestmark = pytest.mark.integration


def _bootstrap_project(tmp_path: Path) -> tuple[Path, Path]:
    """Create a fake project + populated projects.yaml via add_project, return (project_path, yaml_path)."""
    proj = tmp_path / "demo"
    proj.mkdir()
    subprocess.run(
        ["git", "init", "-q", str(proj)], check=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null"},
    )
    (proj / ".taskmaster" / "tasks").mkdir(parents=True)
    (proj / ".taskmaster" / "tasks" / "tasks.json").write_text(
        '{"master": {"tasks": [], "metadata": {"tag": "master"}}}\n'
    )
    yaml_path = tmp_path / "projects.yaml"
    rc = add_project(AddProjectArgs(
        path=proj, non_interactive=True, skills=[], projects_yaml=yaml_path,
        render_kanban=False, deploy_skills=False,
    ))
    assert rc == 0
    return proj, yaml_path


def test_archive_happy_path(tmp_path):
    proj, yaml_path = _bootstrap_project(tmp_path)
    files_before = sorted(p.relative_to(proj).as_posix() for p in proj.rglob("*") if ".git" not in p.parts)

    calls = []
    rc = archive_project(ArchiveArgs(
        name="demo", projects_yaml=yaml_path,
        cron_uninstaller=lambda n: (calls.append(n), True)[1],
    ))
    assert rc == 0
    assert calls == ["demo"], "cron uninstaller should be invoked with the project name"

    data = yaml.safe_load(yaml_path.read_text())
    entry = next(p for p in data["projects"] if p["name"] == "demo")
    assert entry["status"] == "archived"
    # entry still present (no delete)
    assert len(data["projects"]) == 1
    # files untouched
    files_after = sorted(p.relative_to(proj).as_posix() for p in proj.rglob("*") if ".git" not in p.parts)
    assert files_before == files_after


def test_archive_not_found(tmp_path):
    _, yaml_path = _bootstrap_project(tmp_path)
    rc = archive_project(ArchiveArgs(
        name="nope", projects_yaml=yaml_path, cron_uninstaller=lambda _: False,
    ))
    assert rc == EXIT_NOT_FOUND


def test_archive_already_archived_refused(tmp_path):
    _, yaml_path = _bootstrap_project(tmp_path)
    # First archive OK
    assert archive_project(ArchiveArgs(
        name="demo", projects_yaml=yaml_path, cron_uninstaller=lambda _: False,
    )) == 0
    # Second archive → 6
    rc = archive_project(ArchiveArgs(
        name="demo", projects_yaml=yaml_path, cron_uninstaller=lambda _: False,
    ))
    assert rc == EXIT_ALREADY_ARCHIVED


def test_archive_preserves_other_active_projects(tmp_path):
    # First project via bootstrap
    proj_a, yaml_path = _bootstrap_project(tmp_path)

    # Second project, same yaml
    proj_b = tmp_path / "other"
    proj_b.mkdir()
    subprocess.run(
        ["git", "init", "-q", str(proj_b)], check=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null"},
    )
    (proj_b / ".taskmaster" / "tasks").mkdir(parents=True)
    (proj_b / ".taskmaster" / "tasks" / "tasks.json").write_text(
        '{"master": {"tasks": [], "metadata": {"tag": "master"}}}\n'
    )
    add_project(AddProjectArgs(
        path=proj_b, non_interactive=True, skills=[], projects_yaml=yaml_path,
        render_kanban=False, deploy_skills=False,
    ))

    rc = archive_project(ArchiveArgs(
        name="demo", projects_yaml=yaml_path, cron_uninstaller=lambda _: False,
    ))
    assert rc == 0
    data = yaml.safe_load(yaml_path.read_text())
    by_name = {p["name"]: p for p in data["projects"]}
    assert by_name["demo"]["status"] == "archived"
    assert by_name["other"]["status"] == "active"


def test_archived_skipped_by_renderer(tmp_path):
    """T-13 Step 4: renderer should skip archived projects in global board.

    We don't invoke the real renderer here — we assert the contract at the
    projects.yaml level. Renderer's T-8 logic iterates `projects` and
    is expected to filter on status=='active'. See scripts/render_kanban.py.
    """
    from kira_hq.projects_yaml import load as load_projects

    _, yaml_path = _bootstrap_project(tmp_path)
    archive_project(ArchiveArgs(
        name="demo", projects_yaml=yaml_path, cron_uninstaller=lambda _: False,
    ))
    doc = load_projects(yaml_path)
    active = [p for p in doc.projects if p.status == "active"]
    assert active == []
    archived = [p for p in doc.projects if p.status == "archived"]
    assert len(archived) == 1
