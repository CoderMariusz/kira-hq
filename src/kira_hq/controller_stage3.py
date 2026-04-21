"""Task 32 Stage 3 controller worktree orchestration and merge-back planning."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


class Stage3GitError(RuntimeError):
    """Raised when Stage 3 git automation cannot complete safely."""


@dataclass
class WorktreeRegistration:
    task_id: str
    lane: str
    controller_branch: str
    local_branch: str
    worktree_path: str
    remote_branch: str | None


@dataclass
class LaneCloseout:
    task_id: str
    lane: str
    controller_branch: str
    removed_worktrees: list[str]
    removed_branches: list[str]


@dataclass
class TaskCloseout:
    task_id: str
    controller_branch: str
    kept_lanes: list[str]
    closed_lanes: list[str]
    removed_worktrees: list[str]
    removed_branches: list[str]


@dataclass
class MergeBackPlan:
    task_id: str
    controller_branch: str
    selected_lanes: list[str]
    merge_order: list[str]
    merge_branches: list[str]
    cleanup_worktrees: list[str]
    cleanup_branches: list[str]


def prepare_worktree(
    repo_root: str | Path,
    task_id: str,
    lane: str,
    controller_branch: str,
    create_remote_branch: bool = False,
) -> WorktreeRegistration:
    repo_path = Path(repo_root).expanduser().resolve()
    worktree_path = _sibling_worktree_path(repo_path=repo_path, task_id=task_id, lane=lane)
    local_branch = _lane_branch(task_id=task_id, lane=lane)
    remote_branch = f"origin/{local_branch}" if create_remote_branch else None
    _ensure_worktree(
        repo_path=repo_path,
        worktree_path=worktree_path,
        local_branch=local_branch,
        controller_branch=str(controller_branch),
        create_remote_branch=create_remote_branch,
    )
    return WorktreeRegistration(
        task_id=str(task_id),
        lane=str(lane),
        controller_branch=str(controller_branch),
        local_branch=local_branch,
        worktree_path=str(worktree_path),
        remote_branch=remote_branch,
    )


def prepare_parallel_lanes(
    repo_root: str | Path,
    task_id: str,
    lanes: Iterable[str],
    controller_branch: str,
    create_remote_branches: bool = False,
) -> list[dict]:
    return [
        _registration_to_dict(
            prepare_worktree(
                repo_root=repo_root,
                task_id=task_id,
                lane=lane,
                controller_branch=controller_branch,
                create_remote_branch=create_remote_branches,
            )
        )
        for lane in lanes
    ]


def build_handoff_context(
    task_id: str,
    registration: WorktreeRegistration | Mapping[str, object],
    worker: str,
    step: int,
    files: list[dict],
    artifacts: list[str],
    next_step: str,
    status: str,
) -> dict:
    lane_registration = _coerce_registration(registration)
    return {
        "task_id": str(task_id),
        "step": step,
        "worker": str(worker),
        "worktree": lane_registration.worktree_path,
        "lane": lane_registration.lane,
        "branch": lane_registration.local_branch,
        "controller_branch": lane_registration.controller_branch,
        "files": files,
        "tests": [],
        "risks": [],
        "artifacts": artifacts,
        "next": str(next_step),
        "status": str(status),
    }


def closeout_lane(
    repo_root: str | Path,
    task_id: str,
    lane_registration: WorktreeRegistration | Mapping[str, object],
) -> LaneCloseout:
    registration = _coerce_registration(lane_registration)
    repo_path = Path(repo_root).expanduser().resolve()
    _remove_worktree(repo_path=repo_path, worktree_path=Path(registration.worktree_path))
    _delete_branch(repo_path=repo_path, branch=registration.local_branch)
    return LaneCloseout(
        task_id=str(task_id),
        lane=registration.lane,
        controller_branch=registration.controller_branch,
        removed_worktrees=[registration.worktree_path],
        removed_branches=[registration.local_branch],
    )


def closeout_task(
    repo_root: str | Path,
    task_id: str,
    controller_branch: str,
    lane_registrations: Iterable[WorktreeRegistration | Mapping[str, object]],
    keep_lanes: Iterable[str],
) -> TaskCloseout:
    repo_path = Path(repo_root).expanduser().resolve()
    keep_lane_list = [str(lane) for lane in keep_lanes]
    keep_lane_set = set(keep_lane_list)
    registrations = [_coerce_registration(entry) for entry in lane_registrations]
    closed = [entry for entry in registrations if entry.lane not in keep_lane_set]
    for entry in closed:
        _remove_worktree(repo_path=repo_path, worktree_path=Path(entry.worktree_path))
    for entry in closed:
        _delete_branch(repo_path=repo_path, branch=entry.local_branch)
    return TaskCloseout(
        task_id=str(task_id),
        controller_branch=str(controller_branch),
        kept_lanes=keep_lane_list,
        closed_lanes=[entry.lane for entry in closed],
        removed_worktrees=[entry.worktree_path for entry in closed],
        removed_branches=[entry.local_branch for entry in closed],
    )


def merge_selected_lanes_back(
    repo_root: str | Path,
    task_id: str,
    controller_branch: str,
    lane_registrations: Iterable[WorktreeRegistration | Mapping[str, object]],
    selected_lanes: Iterable[str],
    merge_order: Iterable[str],
) -> MergeBackPlan:
    repo_path = Path(repo_root).expanduser().resolve()
    registrations = [_coerce_registration(entry) for entry in lane_registrations]
    by_lane = {entry.lane: entry for entry in registrations}
    selected_lane_list = [str(lane) for lane in selected_lanes]
    merge_order_list = [str(lane) for lane in merge_order]

    if len(selected_lane_list) != len(set(selected_lane_list)):
        raise Stage3GitError("selected lanes must be unique")
    if len(merge_order_list) != len(set(merge_order_list)):
        raise Stage3GitError("merge order lanes must be unique")

    known_lanes = set(by_lane)
    missing_selected = [lane for lane in selected_lane_list if lane not in known_lanes]
    if missing_selected:
        raise Stage3GitError(
            f"selected lanes must exist in lane registrations: {', '.join(missing_selected)}"
        )

    selected_lane_set = set(selected_lane_list)
    invalid_merge_order = [lane for lane in merge_order_list if lane not in selected_lane_set]
    if invalid_merge_order:
        raise Stage3GitError(
            f"merge order lanes must be selected lanes: {', '.join(invalid_merge_order)}"
        )
    if set(merge_order_list) != selected_lane_set:
        raise Stage3GitError("merge order must include all selected lanes exactly once")

    losing_lanes = [entry for entry in registrations if entry.lane not in selected_lane_set]
    selected_registrations = [by_lane[lane] for lane in merge_order_list]
    cleanup_registrations = losing_lanes + selected_registrations

    if _is_git_repo(repo_path):
        _git(repo_path, "checkout", str(controller_branch))
        original_head = _git(repo_path, "rev-parse", "HEAD")
        try:
            for entry in selected_registrations:
                _git(repo_path, "merge", "--no-ff", "--no-edit", entry.local_branch)
        except subprocess.CalledProcessError as exc:
            _abort_merge(repo_path)
            _git(repo_path, "reset", "--hard", original_head)
            for entry in cleanup_registrations:
                _remove_worktree(repo_path=repo_path, worktree_path=Path(entry.worktree_path))
            for entry in cleanup_registrations:
                _delete_branch(repo_path=repo_path, branch=entry.local_branch)
            raise Stage3GitError(
                f"merge-back failed for lane '{entry.lane}' into '{controller_branch}'"
            ) from exc

    for entry in cleanup_registrations:
        _remove_worktree(repo_path=repo_path, worktree_path=Path(entry.worktree_path))
    for entry in cleanup_registrations:
        _delete_branch(repo_path=repo_path, branch=entry.local_branch)
    return MergeBackPlan(
        task_id=str(task_id),
        controller_branch=str(controller_branch),
        selected_lanes=selected_lane_list,
        merge_order=merge_order_list,
        merge_branches=[entry.local_branch for entry in selected_registrations],
        cleanup_worktrees=[entry.worktree_path for entry in cleanup_registrations],
        cleanup_branches=[entry.local_branch for entry in cleanup_registrations],
    )


def _sibling_worktree_path(repo_path: Path, task_id: str, lane: str) -> Path:
    return repo_path.parent / f"{repo_path.name}-task-{str(task_id).strip()}-{str(lane).strip()}"


def _lane_branch(task_id: str, lane: str) -> str:
    return f"kira/task-{str(task_id).strip()}/{str(lane).strip()}"


def _coerce_registration(registration: WorktreeRegistration | Mapping[str, object]) -> WorktreeRegistration:
    if isinstance(registration, WorktreeRegistration):
        return registration
    return WorktreeRegistration(
        task_id=str(registration.get("task_id", "")).strip(),
        lane=str(registration.get("lane", "")).strip(),
        controller_branch=str(registration.get("controller_branch", "")).strip(),
        local_branch=str(registration.get("local_branch", "")).strip(),
        worktree_path=str(registration.get("worktree_path", "")).strip(),
        remote_branch=(
            None
            if registration.get("remote_branch") is None
            else str(registration.get("remote_branch", "")).strip()
        ),
    )


def _registration_to_dict(registration: WorktreeRegistration) -> dict:
    return {
        "task_id": registration.task_id,
        "lane": registration.lane,
        "controller_branch": registration.controller_branch,
        "local_branch": registration.local_branch,
        "worktree_path": registration.worktree_path,
        "remote_branch": registration.remote_branch,
    }


def _ensure_worktree(
    repo_path: Path,
    worktree_path: Path,
    local_branch: str,
    controller_branch: str,
    create_remote_branch: bool,
) -> None:
    if not _is_git_repo(repo_path):
        return
    if create_remote_branch and not _remote_exists(repo_path, "origin"):
        raise Stage3GitError("cannot create remote branch: git remote 'origin' is not configured")
    if worktree_path.exists() and _branch_exists(repo_path=repo_path, branch=local_branch):
        registered_branch = _registered_worktree_branch(repo_path=repo_path, worktree_path=worktree_path)
        if registered_branch == local_branch:
            return
        raise Stage3GitError(
            f"existing path is not a registered git worktree for branch '{local_branch}': {worktree_path}"
        )
    if worktree_path.exists() and not _branch_exists(repo_path=repo_path, branch=local_branch):
        raise FileExistsError(f"Worktree path already exists without expected branch: {worktree_path}")
    args = ["worktree", "add"]
    if _branch_exists(repo_path=repo_path, branch=local_branch):
        args.extend([str(worktree_path), local_branch])
    else:
        args.extend(["-b", local_branch, str(worktree_path), controller_branch])
    _git(repo_path, *args)
    if create_remote_branch:
        _git(repo_path, "push", "-u", "origin", f"{local_branch}:{local_branch}")


def _remove_worktree(repo_path: Path, worktree_path: Path) -> None:
    if _is_git_repo(repo_path) and worktree_path.exists():
        _git(repo_path, "worktree", "remove", "--force", str(worktree_path))


def _delete_branch(repo_path: Path, branch: str) -> None:
    if _is_git_repo(repo_path) and _branch_exists(repo_path=repo_path, branch=branch):
        _git(repo_path, "branch", "-D", branch)


def _abort_merge(repo_path: Path) -> None:
    completed = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        subprocess.run(
            ["git", "merge", "--abort"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )


def _remote_exists(repo_path: Path, remote: str) -> bool:
    completed = subprocess.run(
        ["git", "remote", "get-url", remote],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0


def _branch_exists(repo_path: Path, branch: str) -> bool:
    completed = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0


def _registered_worktree_branch(repo_path: Path, worktree_path: Path) -> str | None:
    completed = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    current_path: Path | None = None
    for line in completed.stdout.splitlines():
        if line.startswith("worktree "):
            current_path = Path(line.removeprefix("worktree ")).resolve()
            continue
        if current_path != worktree_path.resolve():
            continue
        if line.startswith("branch refs/heads/"):
            return line.removeprefix("branch refs/heads/")
        if not line:
            return None
    return None


def _is_git_repo(repo_path: Path) -> bool:
    completed = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def _git(repo_path: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


__all__ = [
    "LaneCloseout",
    "MergeBackPlan",
    "TaskCloseout",
    "WorktreeRegistration",
    "build_handoff_context",
    "closeout_lane",
    "closeout_task",
    "merge_selected_lanes_back",
    "prepare_parallel_lanes",
    "prepare_worktree",
]
