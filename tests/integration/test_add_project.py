"""Integration tests for `kira-hq add-project` — PRD §6.9.

Covers:
- happy path (all flags, non-interactive) creates entry + .env + kanban
- name collision → exit 5
- not git repo → exit 3
- no .taskmaster/ → exit 4; with --init-taskmaster → auto-created
- path missing → exit 2
- PRD missing → soft-warn, exit 0
"""
from __future__ import annotations

import os
import subprocess
from datetime import date
from pathlib import Path

import pytest
import yaml

from kira_hq.cli.add_project import AddProjectArgs, add_project

pytestmark = pytest.mark.integration


def _mk_git_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q", str(root)],
        check=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null"},
    )


def _mk_taskmaster(root: Path) -> None:
    tm = root / ".taskmaster" / "tasks"
    tm.mkdir(parents=True, exist_ok=True)
    (tm / "tasks.json").write_text(
        '{"master": {"tasks": [], "metadata": {"tag": "master"}}}\n'
    )


def _mk_prd(root: Path) -> None:
    (root / "prd").mkdir(exist_ok=True)
    (root / "prd" / "master-prd.md").write_text("# PRD\n")


def _default_args(path: Path, yaml_path: Path, **overrides) -> AddProjectArgs:
    base = dict(
        path=path,
        name=None,
        priority="high",
        cron="0 */3 * * *",
        budget_monthly=400_000,
        budget_per_run=40_000,
        skills=["kira-hq-render-kanban"],
        init_taskmaster=False,
        non_interactive=True,
        projects_yaml=yaml_path,
        render_kanban=False,   # skip in tests to avoid heavy subprocess
        deploy_skills=False,   # skip symlink deploy in tests (side-effects)
    )
    base.update(overrides)
    return AddProjectArgs(**base)


def test_happy_path(tmp_path, capsys):
    proj = tmp_path / "demo"
    _mk_git_repo(proj)
    _mk_taskmaster(proj)
    _mk_prd(proj)
    yaml_path = tmp_path / "projects.yaml"

    rc = add_project(_default_args(proj, yaml_path))
    assert rc == 0

    data = yaml.safe_load(yaml_path.read_text())
    assert data["version"] == 2
    assert len(data["projects"]) == 1
    entry = data["projects"][0]
    assert entry["name"] == "demo"
    assert entry["path"] == str(proj.resolve())
    assert entry["priority"] == "high"
    assert entry["cron"] == "0 */3 * * *"
    assert entry["budget_tokens_monthly"] == 400_000
    assert entry["skills"] == ["kira-hq-render-kanban"]
    assert entry["added_at"] == date.today().isoformat()

    # .env skeleton + chmod 0600
    env = proj / ".env"
    assert env.exists()
    mode = env.stat().st_mode & 0o777
    assert mode == 0o600, f"expected 600, got {oct(mode)}"


def test_path_missing(tmp_path, capsys):
    rc = add_project(_default_args(tmp_path / "nonexistent", tmp_path / "p.yaml"))
    assert rc == 2


def test_not_git_repo(tmp_path):
    proj = tmp_path / "noisy"
    proj.mkdir()
    _mk_taskmaster(proj)
    rc = add_project(_default_args(proj, tmp_path / "p.yaml"))
    assert rc == 3


def test_no_taskmaster(tmp_path):
    proj = tmp_path / "fresh"
    _mk_git_repo(proj)
    # no .taskmaster/
    rc = add_project(_default_args(proj, tmp_path / "p.yaml"))
    assert rc == 4


def test_init_taskmaster_flag_bootstraps(tmp_path):
    proj = tmp_path / "fresh"
    _mk_git_repo(proj)
    rc = add_project(_default_args(proj, tmp_path / "p.yaml", init_taskmaster=True))
    assert rc == 0
    assert (proj / ".taskmaster" / "tasks" / "tasks.json").exists()


def test_name_collision(tmp_path):
    proj = tmp_path / "demo"
    _mk_git_repo(proj)
    _mk_taskmaster(proj)
    yaml_path = tmp_path / "projects.yaml"
    # First add succeeds
    assert add_project(_default_args(proj, yaml_path)) == 0
    # Second with same name → collision
    rc = add_project(_default_args(proj, yaml_path))
    assert rc == 5


def test_missing_prd_is_soft_warn(tmp_path, capsys):
    proj = tmp_path / "demo"
    _mk_git_repo(proj)
    _mk_taskmaster(proj)
    # No prd/master-prd.md
    rc = add_project(_default_args(proj, tmp_path / "p.yaml"))
    assert rc == 0
    captured = capsys.readouterr()
    assert "WARN" in captured.out or "WARN" in captured.err


def test_idempotent_collision_does_not_corrupt_yaml(tmp_path):
    proj = tmp_path / "demo"
    _mk_git_repo(proj)
    _mk_taskmaster(proj)
    yaml_path = tmp_path / "projects.yaml"
    assert add_project(_default_args(proj, yaml_path)) == 0
    size_before = yaml_path.stat().st_size
    mtime_before = yaml_path.stat().st_mtime_ns

    rc = add_project(_default_args(proj, yaml_path))
    assert rc == 5
    # yaml not rewritten (or at worst unchanged) on collision
    assert yaml_path.stat().st_size == size_before
    # mtime might equal; what matters is no duplicate entry
    data = yaml.safe_load(yaml_path.read_text())
    assert len([p for p in data["projects"] if p["name"] == "demo"]) == 1
    assert yaml_path.stat().st_mtime_ns >= mtime_before  # sanity


def test_all_flags_non_interactive_no_prompts_needed(tmp_path, monkeypatch):
    """Confirm non-interactive path never calls input()."""
    def _fail_input(_prompt=""):
        raise AssertionError("input() was called in non-interactive mode")
    monkeypatch.setattr("builtins.input", _fail_input)

    proj = tmp_path / "demo"
    _mk_git_repo(proj)
    _mk_taskmaster(proj)
    rc = add_project(_default_args(proj, tmp_path / "p.yaml"))
    assert rc == 0
