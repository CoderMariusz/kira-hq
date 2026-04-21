"""Smoke tests for Task 32 Stage 3 controller worktree orchestration."""
from __future__ import annotations

import importlib
from dataclasses import asdict, is_dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.smoke


def _controller_stage3_module():
    return importlib.import_module("kira_hq.controller_stage3")


def _call(name: str, /, *args, **kwargs):
    module = _controller_stage3_module()
    fn = getattr(module, name)
    return fn(*args, **kwargs)


def _as_dict(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    return value


def test_prepare_worktree_uses_deterministic_local_branch_and_sibling_path(tmp_path):
    repo = tmp_path / "kira-hq"
    repo.mkdir()

    registration = _as_dict(
        _call(
            "prepare_worktree",
            repo_root=repo,
            task_id="31",
            lane="default",
            controller_branch="controller/task-31",
            create_remote_branch=False,
        )
    )

    assert registration == {
        "task_id": "31",
        "lane": "default",
        "controller_branch": "controller/task-31",
        "local_branch": "kira/task-31/default",
        "worktree_path": str(tmp_path / "kira-hq-task-31-default"),
        "remote_branch": None,
    }


def test_prepare_parallel_lanes_assigns_one_local_lane_branch_per_lane(tmp_path):
    repo = tmp_path / "kira-hq"
    repo.mkdir()

    lanes = _as_dict(
        _call(
            "prepare_parallel_lanes",
            repo_root=repo,
            task_id="31",
            lanes=["default", "lane-a", "lane-b"],
            controller_branch="controller/task-31",
            create_remote_branches=False,
        )
    )

    assert [entry["lane"] for entry in lanes] == ["default", "lane-a", "lane-b"]
    assert [entry["local_branch"] for entry in lanes] == [
        "kira/task-31/default",
        "kira/task-31/lane-a",
        "kira/task-31/lane-b",
    ]
    assert [entry["worktree_path"] for entry in lanes] == [
        str(tmp_path / "kira-hq-task-31-default"),
        str(tmp_path / "kira-hq-task-31-lane-a"),
        str(tmp_path / "kira-hq-task-31-lane-b"),
    ]
    assert all(not Path(entry["worktree_path"]).is_relative_to(repo) for entry in lanes)


def test_build_handoff_context_includes_stage3_worktree_and_lane_metadata(tmp_path):
    repo = tmp_path / "kira-hq"
    repo.mkdir()
    registration = {
        "task_id": "31",
        "lane": "lane-a",
        "controller_branch": "controller/task-31",
        "local_branch": "kira/task-31/lane-a",
        "worktree_path": str(tmp_path / "kira-hq-task-31-lane-a"),
        "remote_branch": None,
    }

    handoff = _call(
        "build_handoff_context",
        task_id="31",
        registration=registration,
        worker="red",
        step=3,
        files=[{"path": "src/kira_hq/controller_stage3.py", "intent": "create"}],
        artifacts=[".hermes/artifacts/31/red/worktree-setup.log"],
        next_step="parallel_review",
        status="completed",
    )

    assert handoff["task_id"] == "31"
    assert handoff["step"] == 3
    assert handoff["worker"] == "red"
    assert handoff["lane"] == "lane-a"
    assert handoff["worktree"] == str(tmp_path / "kira-hq-task-31-lane-a")
    assert handoff["branch"] == "kira/task-31/lane-a"
    assert handoff["controller_branch"] == "controller/task-31"
    assert handoff["artifacts"] == [".hermes/artifacts/31/red/worktree-setup.log"]
    assert handoff["next"] == "parallel_review"
    assert handoff["status"] == "completed"


def test_closeout_task_reports_worktree_and_branch_cleanup_for_losing_lanes(tmp_path):
    repo = tmp_path / "kira-hq"
    repo.mkdir()

    result = _as_dict(
        _call(
            "closeout_task",
            repo_root=repo,
            task_id="31",
            controller_branch="controller/task-31",
            lane_registrations=[
                {
                    "task_id": "31",
                    "lane": "default",
                    "controller_branch": "controller/task-31",
                    "local_branch": "kira/task-31/default",
                    "worktree_path": str(tmp_path / "kira-hq-task-31-default"),
                    "remote_branch": None,
                },
                {
                    "task_id": "31",
                    "lane": "lane-a",
                    "controller_branch": "controller/task-31",
                    "local_branch": "kira/task-31/lane-a",
                    "worktree_path": str(tmp_path / "kira-hq-task-31-lane-a"),
                    "remote_branch": None,
                },
            ],
            keep_lanes=["default"],
        )
    )

    assert result == {
        "task_id": "31",
        "controller_branch": "controller/task-31",
        "kept_lanes": ["default"],
        "closed_lanes": ["lane-a"],
        "removed_worktrees": [str(tmp_path / "kira-hq-task-31-lane-a")],
        "removed_branches": ["kira/task-31/lane-a"],
    }
