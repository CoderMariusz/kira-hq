"""Smoke test for scripts/symlink_skills.py — PRD §6.11."""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from symlink_skills import deploy  # scripts/ on sys.path via conftest extension

pytestmark = pytest.mark.smoke


@pytest.fixture
def env(tmp_path):
    """Build a self-contained fake world: skills-shared + projects.yaml + dirs."""
    shared = tmp_path / "skills-shared"
    shared.mkdir()
    for name in ("kira-hq-render-kanban", "kira-hq-execute"):
        d = shared / name
        d.mkdir()
        (d / "SKILL.md").write_text(f"# {name}\n")

    project_path = tmp_path / "kira-hq"
    project_path.mkdir()
    yaml_path = tmp_path / "projects.yaml"
    yaml_path.write_text(yaml.safe_dump({
        "version": 2,
        "projects": [{
            "name": "kira-hq",
            "path": str(project_path),
            "status": "active",
            "priority": "high",
            "cron": "0 */2 * * *",
            "added_at": "2026-04-18",
            "skills": ["kira-hq-render-kanban", "kira-hq-execute"],
            "budget_tokens_monthly": 500_000,
            "budget_tokens_per_run": 50_000,
        }],
    }))
    claude_global = tmp_path / ".claude" / "skills"
    hermes_ns = tmp_path / ".hermes" / "skills" / "kira-hq"
    return {
        "yaml": yaml_path,
        "shared": shared,
        "claude_global": claude_global,
        "hermes_ns": hermes_ns,
        "project_path": project_path,
    }


def _kwargs(env):
    return dict(
        projects_yaml=env["yaml"],
        skills_shared=env["shared"],
        claude_global=env["claude_global"],
        hermes_ns=env["hermes_ns"],
    )


def test_deploy_creates_all_three_symlinks_per_skill(env):
    report, code = deploy(**_kwargs(env))
    assert code == 0
    # 2 skills × 3 targets = 6 created
    assert len(report.created) == 6
    # per-project
    for skill in ("kira-hq-render-kanban", "kira-hq-execute"):
        link = env["project_path"] / ".claude" / "skills" / skill
        assert link.is_symlink()
        assert Path(os.readlink(link)).resolve() == (env["shared"] / skill).resolve()
        # global
        link = env["claude_global"] / skill
        assert link.is_symlink()
        # hermes
        link = env["hermes_ns"] / skill
        assert link.is_symlink()


def test_deploy_is_idempotent(env):
    deploy(**_kwargs(env))
    report, code = deploy(**_kwargs(env))
    assert code == 0
    assert report.created == []
    assert report.repaired == []
    assert len(report.ok) == 6


def test_broken_symlink_is_repaired(env):
    # Create a broken symlink at a target path
    target = env["claude_global"] / "kira-hq-execute"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(env["shared"] / "does-not-exist")
    report, code = deploy(**_kwargs(env))
    assert code == 0
    assert any("kira-hq-execute" in r for r in report.repaired)
    assert Path(os.readlink(target)).resolve() == (env["shared"] / "kira-hq-execute").resolve()


def test_non_symlink_collision_reported_not_overwritten(env):
    collision = env["claude_global"] / "kira-hq-execute"
    collision.parent.mkdir(parents=True, exist_ok=True)
    collision.mkdir()
    (collision / "SKILL.md").write_text("# user content\n")
    report, code = deploy(**_kwargs(env))
    assert code == 1
    assert any("kira-hq-execute" in c for c in report.collisions)
    # User file untouched
    assert (collision / "SKILL.md").read_text() == "# user content\n"


def test_missing_source_reported(env):
    # Reference skill that doesn't exist under shared
    extra = env["shared"].parent / "projects-extra.yaml"
    import yaml as _y
    doc = _y.safe_load(env["yaml"].read_text())
    doc["projects"][0]["skills"].append("nonexistent-skill")
    env["yaml"].write_text(_y.safe_dump(doc))
    report, code = deploy(**_kwargs(env))
    assert code == 2
    assert any("nonexistent-skill" in m for m in report.missing_source)


def test_check_mode_does_not_mutate_fs(env):
    report, code = deploy(**_kwargs(env), check_only=True)
    assert code == 0
    # Nothing was actually created
    link = env["claude_global"] / "kira-hq-render-kanban"
    assert not link.exists() or link.is_symlink() is False
    # But report does mention them as would-be-created
    assert len(report.created) == 6


def test_prune_removes_orphan_symlink(env):
    deploy(**_kwargs(env))
    # Inject an orphan: a symlink into skills-shared that's not in projects.yaml
    orphan_target = env["shared"] / "ghost"
    orphan_target.mkdir()
    orphan_link = env["claude_global"] / "ghost"
    orphan_link.symlink_to(orphan_target)
    report, code = deploy(**_kwargs(env), prune=True)
    assert code == 0
    assert any("ghost" in p for p in report.pruned)
    assert not orphan_link.exists()
