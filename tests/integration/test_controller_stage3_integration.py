"""Integration tests for Task 32 Stage 3 controller worktree orchestration."""
from __future__ import annotations

import importlib
import subprocess
from dataclasses import asdict, is_dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


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


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write(repo: Path, relative_path: str, content: str) -> None:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _init_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "kira-hq"
    repo.mkdir()
    _git(repo, "init", "-b", "controller/task-31")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    _write(repo, "README.md", "# kira-hq\n")
    _write(repo, "src/pkg/module.py", "def value():\n    return 1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    return repo


def _init_bare_remote(tmp_path: Path) -> Path:
    remote = tmp_path / "origin.git"
    _git(tmp_path, "init", "--bare", str(remote))
    return remote


def test_prepare_parallel_lanes_creates_real_sibling_worktrees_and_local_branches(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path)
    monkeypatch.chdir(repo)

    registrations = _as_dict(
        _call(
            "prepare_parallel_lanes",
            repo_root=repo,
            task_id="31",
            lanes=["default", "lane-a"],
            controller_branch="controller/task-31",
            create_remote_branches=False,
        )
    )

    assert [entry["local_branch"] for entry in registrations] == [
        "kira/task-31/default",
        "kira/task-31/lane-a",
    ]
    assert [entry["worktree_path"] for entry in registrations] == [
        str(tmp_path / "kira-hq-task-31-default"),
        str(tmp_path / "kira-hq-task-31-lane-a"),
    ]
    assert all(Path(entry["worktree_path"]).parent == tmp_path for entry in registrations)
    assert _git(repo, "branch", "--show-current") == "controller/task-31"
    assert _git(repo, "rev-parse", "--verify", "kira/task-31/default")
    assert _git(repo, "rev-parse", "--verify", "kira/task-31/lane-a")
    assert Path(registrations[0]["worktree_path"], ".git").exists()
    assert Path(registrations[1]["worktree_path"], ".git").exists()
    assert _git(Path(registrations[0]["worktree_path"]), "branch", "--show-current") == "kira/task-31/default"
    assert _git(Path(registrations[1]["worktree_path"]), "branch", "--show-current") == "kira/task-31/lane-a"


def test_prepare_worktree_rejects_existing_path_that_is_not_registered_for_lane_branch(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path)
    monkeypatch.chdir(repo)
    invalid_worktree_path = tmp_path / "kira-hq-task-31-lane-a"
    invalid_worktree_path.mkdir()
    _git(repo, "branch", "kira/task-31/lane-a")

    with pytest.raises(RuntimeError, match="registered git worktree"):
        _call(
            "prepare_worktree",
            repo_root=repo,
            task_id="31",
            lane="lane-a",
            controller_branch="controller/task-31",
            create_remote_branch=False,
        )

    assert invalid_worktree_path.exists()
    assert _git(repo, "branch", "--list", "kira/task-31/lane-a") == "kira/task-31/lane-a"


def test_merge_selected_lanes_back_merges_selected_lanes_and_cleans_up_ephemeral_state(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path)
    monkeypatch.chdir(repo)
    registrations = _as_dict(
        _call(
            "prepare_parallel_lanes",
            repo_root=repo,
            task_id="31",
            lanes=["default", "lane-a", "lane-b"],
            controller_branch="controller/task-31",
            create_remote_branches=False,
        )
    )

    default_worktree = Path(registrations[0]["worktree_path"])
    lane_b_worktree = Path(registrations[2]["worktree_path"])
    _write(default_worktree, "src/pkg/default_only.py", "DEFAULT = True\n")
    _git(default_worktree, "add", ".")
    _git(default_worktree, "commit", "-m", "default change")
    _write(lane_b_worktree, "src/pkg/lane_b_only.py", "LANE_B = True\n")
    _git(lane_b_worktree, "add", ".")
    _git(lane_b_worktree, "commit", "-m", "lane-b change")

    plan = _as_dict(
        _call(
            "merge_selected_lanes_back",
            repo_root=repo,
            task_id="31",
            controller_branch="controller/task-31",
            lane_registrations=registrations,
            selected_lanes=["default", "lane-b"],
            merge_order=["default", "lane-b"],
        )
    )

    assert plan == {
        "task_id": "31",
        "controller_branch": "controller/task-31",
        "selected_lanes": ["default", "lane-b"],
        "merge_order": ["default", "lane-b"],
        "merge_branches": ["kira/task-31/default", "kira/task-31/lane-b"],
        "cleanup_worktrees": [
            str(tmp_path / "kira-hq-task-31-lane-a"),
            str(tmp_path / "kira-hq-task-31-default"),
            str(tmp_path / "kira-hq-task-31-lane-b"),
        ],
        "cleanup_branches": [
            "kira/task-31/lane-a",
            "kira/task-31/default",
            "kira/task-31/lane-b",
        ],
    }
    assert _git(repo, "branch", "--show-current") == "controller/task-31"
    assert (repo / "src/pkg/default_only.py").read_text() == "DEFAULT = True\n"
    assert (repo / "src/pkg/lane_b_only.py").read_text() == "LANE_B = True\n"
    assert _git(repo, "branch", "--list", "kira/task-31/default") == ""
    assert _git(repo, "branch", "--list", "kira/task-31/lane-a") == ""
    assert _git(repo, "branch", "--list", "kira/task-31/lane-b") == ""
    assert not Path(registrations[0]["worktree_path"]).exists()
    assert not Path(registrations[1]["worktree_path"]).exists()
    assert not Path(registrations[2]["worktree_path"]).exists()


def test_merge_selected_lanes_back_rejects_merge_order_that_drops_selected_lanes(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path)
    monkeypatch.chdir(repo)
    registrations = _as_dict(
        _call(
            "prepare_parallel_lanes",
            repo_root=repo,
            task_id="31",
            lanes=["default", "lane-a", "lane-b"],
            controller_branch="controller/task-31",
            create_remote_branches=False,
        )
    )

    default_worktree = Path(registrations[0]["worktree_path"])
    lane_b_worktree = Path(registrations[2]["worktree_path"])
    _write(default_worktree, "src/pkg/default_only.py", "DEFAULT = True\n")
    _git(default_worktree, "add", ".")
    _git(default_worktree, "commit", "-m", "default change")
    _write(lane_b_worktree, "src/pkg/lane_b_only.py", "LANE_B = True\n")
    _git(lane_b_worktree, "add", ".")
    _git(lane_b_worktree, "commit", "-m", "lane-b change")

    with pytest.raises(RuntimeError, match="selected lanes"):
        _call(
            "merge_selected_lanes_back",
            repo_root=repo,
            task_id="31",
            controller_branch="controller/task-31",
            lane_registrations=registrations,
            selected_lanes=["default", "lane-b"],
            merge_order=["default"],
        )

    assert _git(repo, "branch", "--show-current") == "controller/task-31"
    assert not (repo / "src/pkg/default_only.py").exists()
    assert not (repo / "src/pkg/lane_b_only.py").exists()
    assert "kira/task-31/default" in _git(repo, "branch", "--list", "kira/task-31/default")
    assert "kira/task-31/lane-b" in _git(repo, "branch", "--list", "kira/task-31/lane-b")
    assert Path(registrations[0]["worktree_path"]).exists()
    assert Path(registrations[2]["worktree_path"]).exists()


def test_closeout_lane_removes_single_losing_lane_worktree_and_branch(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path)
    monkeypatch.chdir(repo)

    registration = _as_dict(
        _call(
            "prepare_worktree",
            repo_root=repo,
            task_id="31",
            lane="lane-a",
            controller_branch="controller/task-31",
            create_remote_branch=False,
        )
    )

    result = _as_dict(
        _call(
            "closeout_lane",
            repo_root=repo,
            task_id="31",
            lane_registration=registration,
        )
    )

    assert result == {
        "task_id": "31",
        "lane": "lane-a",
        "controller_branch": "controller/task-31",
        "removed_worktrees": [str(tmp_path / "kira-hq-task-31-lane-a")],
        "removed_branches": ["kira/task-31/lane-a"],
    }
    assert _git(repo, "branch", "--list", "kira/task-31/lane-a") == ""
    assert not Path(registration["worktree_path"]).exists()


def test_closeout_task_removes_real_losing_lane_worktrees_and_branches(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path)
    monkeypatch.chdir(repo)
    registrations = _as_dict(
        _call(
            "prepare_parallel_lanes",
            repo_root=repo,
            task_id="32",
            lanes=["default", "lane-a", "lane-b"],
            controller_branch="controller/task-31",
            create_remote_branches=False,
        )
    )

    result = _as_dict(
        _call(
            "closeout_task",
            repo_root=repo,
            task_id="32",
            controller_branch="controller/task-31",
            lane_registrations=registrations,
            keep_lanes=["default"],
        )
    )

    assert result == {
        "task_id": "32",
        "controller_branch": "controller/task-31",
        "kept_lanes": ["default"],
        "closed_lanes": ["lane-a", "lane-b"],
        "removed_worktrees": [
            str(tmp_path / "kira-hq-task-32-lane-a"),
            str(tmp_path / "kira-hq-task-32-lane-b"),
        ],
        "removed_branches": [
            "kira/task-32/lane-a",
            "kira/task-32/lane-b",
        ],
    }
    assert Path(registrations[0]["worktree_path"]).exists()
    assert "kira/task-32/default" in _git(repo, "branch", "--list", "kira/task-32/default")
    assert not Path(registrations[1]["worktree_path"]).exists()
    assert not Path(registrations[2]["worktree_path"]).exists()
    assert _git(repo, "branch", "--list", "kira/task-32/lane-a") == ""
    assert _git(repo, "branch", "--list", "kira/task-32/lane-b") == ""


def test_prepare_worktree_refuses_remote_branch_creation_without_origin(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path)
    monkeypatch.chdir(repo)

    with pytest.raises(RuntimeError, match="origin"):
        _call(
            "prepare_worktree",
            repo_root=repo,
            task_id="31",
            lane="lane-a",
            controller_branch="controller/task-31",
            create_remote_branch=True,
        )

    assert _git(repo, "branch", "--list", "kira/task-31/lane-a") == ""
    assert not (tmp_path / "kira-hq-task-31-lane-a").exists()


def test_prepare_parallel_lanes_does_not_publish_remote_branches_by_default(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path)
    remote = _init_bare_remote(tmp_path)
    _git(repo, "remote", "add", "origin", str(remote))
    monkeypatch.chdir(repo)

    registrations = _as_dict(
        _call(
            "prepare_parallel_lanes",
            repo_root=repo,
            task_id="31",
            lanes=["default", "lane-a"],
            controller_branch="controller/task-31",
            create_remote_branches=False,
        )
    )

    assert [entry["remote_branch"] for entry in registrations] == [None, None]
    assert _git(remote, "for-each-ref", "--format=%(refname:short)", "refs/heads") == ""
    assert _git(repo, "branch", "--list", "-r", "origin/kira/task-31/*") == ""


def test_merge_selected_lanes_back_aborts_conflicts_and_raises_clear_error(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path)
    monkeypatch.chdir(repo)
    registrations = _as_dict(
        _call(
            "prepare_parallel_lanes",
            repo_root=repo,
            task_id="31",
            lanes=["default", "lane-b"],
            controller_branch="controller/task-31",
            create_remote_branches=False,
        )
    )

    default_worktree = Path(registrations[0]["worktree_path"])
    lane_b_worktree = Path(registrations[1]["worktree_path"])
    _write(default_worktree, "src/pkg/module.py", "def value():\n    return 10\n")
    _git(default_worktree, "add", "src/pkg/module.py")
    _git(default_worktree, "commit", "-m", "default conflict")
    _write(lane_b_worktree, "src/pkg/module.py", "def value():\n    return 20\n")
    _git(lane_b_worktree, "add", "src/pkg/module.py")
    _git(lane_b_worktree, "commit", "-m", "lane-b conflict")

    with pytest.raises(RuntimeError, match="merge-back failed"):
        _call(
            "merge_selected_lanes_back",
            repo_root=repo,
            task_id="31",
            controller_branch="controller/task-31",
            lane_registrations=registrations,
            selected_lanes=["default", "lane-b"],
            merge_order=["default", "lane-b"],
        )

    assert _git(repo, "branch", "--show-current") == "controller/task-31"
    assert not (repo / ".git" / "MERGE_HEAD").exists()
    assert (repo / "src/pkg/module.py").read_text() == "def value():\n    return 1\n"
    assert _git(repo, "branch", "--list", "kira/task-31/default") == ""
    assert _git(repo, "branch", "--list", "kira/task-31/lane-b") == ""
    assert not default_worktree.exists()
    assert not lane_b_worktree.exists()
