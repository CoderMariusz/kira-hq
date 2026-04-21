"""End-to-end rollout validation across Stages 1-4 for Task 34."""
from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


HANDOFF_KEYS = (
    "task_id",
    "step",
    "worker",
    "worktree",
    "lane",
    "files",
    "tests",
    "risks",
    "artifacts",
    "next",
    "status",
)


def _handoff_module():
    return importlib.import_module("kira_hq.handoff")


def _stage2_module():
    return importlib.import_module("kira_hq.controller_stage2")


def _stage3_module():
    return importlib.import_module("kira_hq.controller_stage3")


def _stage4_module():
    return importlib.import_module("kira_hq.controller_stage4")


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write(repo: Path, relative_path: str, content: str) -> Path:
    path = repo / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _git_summary(repo: Path) -> dict[str, object]:
    return {
        "name_only": [line for line in _git(repo, "diff", "--name-only").splitlines() if line],
        "stat": _git(repo, "diff", "--stat"),
    }


def _init_git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "kira-hq"
    repo.mkdir()
    _git(repo, "init", "-b", "controller/task-34")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")
    _write(repo, "README.md", "# kira-hq\n")
    _write(repo, "src/pkg/module.py", "def value():\n    return 1\n")
    _write(repo, "src/kira_hq/auth.py", "def authenticate():\n    return True\n")
    _write(repo, "kanban_board.md", "# Board\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    return repo


def _stage1_parse(context: dict[str, object]) -> dict[str, object]:
    payload = {key: context[key] for key in HANDOFF_KEYS}
    document = _handoff_module().parse_handoff(json.dumps(payload))
    return document.model_dump() if hasattr(document, "model_dump") else dict(document)


def _artifact(worktree: Path, task_id: str, name: str, content: str) -> tuple[str, str]:
    path = _write(worktree, f".hermes/artifacts/{task_id}/{name}", content)
    return f".hermes/artifacts/{task_id}/{name}", str(path)


def test_validate_end_to_end_rollout_captures_fast_path_parallel_merge_cleanup_and_token_savings(tmp_path, monkeypatch):
    stage2 = _stage2_module()
    stage3 = _stage3_module()
    stage4 = _stage4_module()
    repo = _init_git_repo(tmp_path)
    metrics_path = tmp_path / "controller-stage4-metrics.jsonl"

    for index in range(2):
        stage4.write_task_metrics(
            metrics_path,
            stage4.build_task_metrics(
                task_id=f"baseline-{index}",
                phase="baseline",
                controller_tokens=1500,
                file_count_inspected=5,
                diff_size_inspected=100,
                artifacts=[],
                fail_loop_count=0,
                integrity_check_failed=False,
                exception_path=False,
            ),
        )

    normal_registration = stage3.prepare_worktree(
        repo_root=repo,
        task_id="34-normal",
        lane="default",
        controller_branch="controller/task-34",
        create_remote_branch=False,
    )
    normal_worktree = Path(normal_registration.worktree_path)
    _write(normal_worktree, "src/pkg/module.py", "def value():\n    return 2\n")
    _write(normal_worktree, "kanban_board.md", "# Board\n- normal task\n")
    normal_artifact_rel, normal_artifact_abs = _artifact(
        normal_worktree,
        "34-normal",
        "review.txt",
        "normal review ok\n",
    )
    normal_context = stage3.build_handoff_context(
        task_id="34-normal",
        registration=normal_registration,
        worker="hermes-worker",
        step=1,
        files=[
            {"path": "src/pkg/module.py", "intent": "modify"},
            {"path": "kanban_board.md", "intent": "modify"},
        ],
        artifacts=[normal_artifact_rel],
        next_step="controller_review",
        status="completed",
    )
    normal_handoff = _stage1_parse(normal_context)
    monkeypatch.chdir(normal_worktree)
    normal_plan = stage2.plan_controller_inspection(
        task_id="34-normal",
        handoff=normal_handoff,
        git_summary=_git_summary(normal_worktree),
        explicitly_targeted=[],
        fail_loop_count=0,
        risk_level="LOW",
        prd_ambiguity=False,
        review_failed=False,
        qa_failed=False,
    )
    _git(normal_worktree, "add", ".")
    _git(normal_worktree, "commit", "-m", "normal task change")
    normal_merge = stage3.merge_selected_lanes_back(
        repo_root=repo,
        task_id="34-normal",
        controller_branch="controller/task-34",
        lane_registrations=[normal_registration],
        selected_lanes=["default"],
        merge_order=["default"],
    )

    parallel_registrations = stage3.prepare_parallel_lanes(
        repo_root=repo,
        task_id="34-parallel",
        lanes=["default", "lane-a"],
        controller_branch="controller/task-34",
        create_remote_branches=False,
    )
    parallel_default = Path(parallel_registrations[0]["worktree_path"])
    parallel_lane_a = Path(parallel_registrations[1]["worktree_path"])
    _write(parallel_default, "src/kira_hq/auth.py", "def authenticate():\n    return False\n")
    _write(parallel_lane_a, "README.md", "# kira-hq\n\nparallel lane a\n")
    default_artifact_rel, default_artifact_abs = _artifact(
        parallel_default,
        "34-parallel",
        "review-default.txt",
        "auth lane review\n",
    )
    lane_a_artifact_rel, lane_a_artifact_abs = _artifact(
        parallel_lane_a,
        "34-parallel",
        "review-lane-a.txt",
        "lane a review\n",
    )
    default_context = stage3.build_handoff_context(
        task_id="34-parallel",
        registration=parallel_registrations[0],
        worker="hermes-worker",
        step=1,
        files=[{"path": "src/kira_hq/auth.py", "intent": "modify"}],
        artifacts=[default_artifact_rel],
        next_step="controller_review",
        status="completed",
    )
    lane_a_context = stage3.build_handoff_context(
        task_id="34-parallel",
        registration=parallel_registrations[1],
        worker="hermes-worker",
        step=1,
        files=[{"path": "README.md", "intent": "modify"}],
        artifacts=[lane_a_artifact_rel],
        next_step="controller_review",
        status="completed",
    )
    default_handoff = _stage1_parse(default_context)
    lane_a_handoff = _stage1_parse(lane_a_context)
    monkeypatch.chdir(parallel_default)
    default_plan = stage2.plan_controller_inspection(
        task_id="34-parallel",
        handoff=default_handoff,
        git_summary=_git_summary(parallel_default),
        explicitly_targeted=[],
        fail_loop_count=0,
        risk_level="LOW",
        prd_ambiguity=False,
        review_failed=False,
        qa_failed=False,
    )
    monkeypatch.chdir(parallel_lane_a)
    lane_a_plan = stage2.plan_controller_inspection(
        task_id="34-parallel",
        handoff=lane_a_handoff,
        git_summary=_git_summary(parallel_lane_a),
        explicitly_targeted=[],
        fail_loop_count=0,
        risk_level="LOW",
        prd_ambiguity=False,
        review_failed=False,
        qa_failed=False,
    )
    _git(parallel_default, "add", ".")
    _git(parallel_default, "commit", "-m", "default lane change")
    _git(parallel_lane_a, "add", ".")
    _git(parallel_lane_a, "commit", "-m", "lane-a change")
    parallel_merge = stage3.merge_selected_lanes_back(
        repo_root=repo,
        task_id="34-parallel",
        controller_branch="controller/task-34",
        lane_registrations=parallel_registrations,
        selected_lanes=["default", "lane-a"],
        merge_order=["default", "lane-a"],
    )

    report = stage4.validate_end_to_end_rollout(
        metrics_path,
        task_runs=[
            {
                "task_id": "34-normal",
                "controller_tokens": 900,
                "file_count_inspected": len(normal_plan.semantic_files),
                "diff_size_inspected": 40,
                "fail_loop_count": 0,
                "merge_verified": (repo / "src/pkg/module.py").read_text(encoding="utf-8") == "def value():\n    return 2\n",
                "cleanup_verified": not normal_worktree.exists() and _git(repo, "branch", "--list", normal_registration.local_branch) == "",
                "merge_plan": normal_merge,
                "lanes": [
                    {
                        "lane": normal_handoff["lane"],
                        "inspection_mode": normal_plan.inspection_mode,
                        "exception_reasons": normal_plan.exception_reasons,
                        "read_artifacts": normal_plan.read_artifacts,
                        "handoff_integrity_ok": not normal_plan.handoff_failure_reasons,
                        "artifact_paths": [normal_artifact_abs],
                    }
                ],
            },
            {
                "task_id": "34-parallel",
                "controller_tokens": 1100,
                "file_count_inspected": len(default_plan.semantic_files) + len(lane_a_plan.semantic_files),
                "diff_size_inspected": 120,
                "fail_loop_count": 0,
                "merge_verified": (repo / "src/kira_hq/auth.py").read_text(encoding="utf-8") == "def authenticate():\n    return False\n" and (repo / "README.md").read_text(encoding="utf-8") == "# kira-hq\n\nparallel lane a\n",
                "cleanup_verified": not parallel_default.exists() and not parallel_lane_a.exists() and _git(repo, "branch", "--list", "kira/task-34-parallel/default") == "" and _git(repo, "branch", "--list", "kira/task-34-parallel/lane-a") == "",
                "merge_plan": parallel_merge,
                "lanes": [
                    {
                        "lane": default_handoff["lane"],
                        "inspection_mode": default_plan.inspection_mode,
                        "exception_reasons": default_plan.exception_reasons,
                        "read_artifacts": default_plan.read_artifacts,
                        "handoff_integrity_ok": not default_plan.handoff_failure_reasons,
                        "artifact_paths": [default_artifact_abs],
                    },
                    {
                        "lane": lane_a_handoff["lane"],
                        "inspection_mode": lane_a_plan.inspection_mode,
                        "exception_reasons": lane_a_plan.exception_reasons,
                        "read_artifacts": lane_a_plan.read_artifacts,
                        "handoff_integrity_ok": not lane_a_plan.handoff_failure_reasons,
                        "artifact_paths": [lane_a_artifact_abs],
                    },
                ],
            },
        ],
        baseline_window=2,
        current_thresholds={"touched_files": 8, "fail_loop": 2},
    )

    assert normal_plan.inspection_mode == "diff-first"
    assert normal_plan.read_artifacts == []
    assert default_plan.inspection_mode == "full-diff"
    assert default_plan.read_artifacts == [default_artifact_rel]
    assert lane_a_plan.inspection_mode == "diff-first"
    assert report["task_runs"][0]["controller_path"] == "fast-path"
    assert report["task_runs"][1]["controller_path"] == "exception-path"
    assert report["task_runs"][0]["parallel_lanes"] is False
    assert report["task_runs"][1]["parallel_lanes"] is True
    assert all(run["integrity_check_passed"] for run in report["task_runs"])
    assert all(run["artifact_routing_ok"] for run in report["task_runs"])
    assert all(run["merge_back_local"] for run in report["task_runs"])
    assert all(run["cleanup_verified"] for run in report["task_runs"])
    assert report["comparison"]["baseline"]["controller_tokens_per_task"] == 1500
    assert report["comparison"]["post_rollout"]["controller_tokens_per_task"] == 1000
    assert report["token_savings"] == {
        "baseline_avg_tokens": 1500,
        "post_rollout_avg_tokens": 1000,
        "tokens_saved_per_task": 500,
        "percent_reduction": 33.33,
    }
    assert report["validation_summary"] == {
        "tasks_validated": 2,
        "fast_path_tasks": 1,
        "exception_path_tasks": 1,
        "parallel_tasks": 1,
        "all_merges_local": True,
        "all_cleanups_verified": True,
    }
    rows = stage4.load_task_metrics(metrics_path)
    assert [row["phase"] for row in rows] == ["baseline", "baseline", "post-rollout", "post-rollout"]


def test_validate_end_to_end_rollout_rejects_runs_without_cleanup_verification(tmp_path):
    stage4 = _stage4_module()
    metrics_path = tmp_path / "controller-stage4-metrics.jsonl"

    stage4.write_task_metrics(
        metrics_path,
        stage4.build_task_metrics(
            task_id="baseline-0",
            phase="baseline",
            controller_tokens=1200,
            file_count_inspected=4,
            diff_size_inspected=80,
            artifacts=[],
            fail_loop_count=0,
            integrity_check_failed=False,
            exception_path=False,
        ),
    )

    with pytest.raises(ValueError, match="cleanup verification"):
        stage4.validate_end_to_end_rollout(
            metrics_path,
            task_runs=[
                {
                    "task_id": "34-bad",
                    "controller_tokens": 900,
                    "file_count_inspected": 1,
                    "diff_size_inspected": 10,
                    "fail_loop_count": 0,
                    "merge_verified": True,
                    "cleanup_verified": False,
                    "merge_plan": {"selected_lanes": ["default"], "merge_order": ["default"]},
                    "lanes": [
                        {
                            "lane": "default",
                            "inspection_mode": "diff-first",
                            "exception_reasons": [],
                            "read_artifacts": [],
                            "handoff_integrity_ok": True,
                            "artifact_paths": [],
                        }
                    ],
                }
            ],
            baseline_window=1,
        )


def test_validate_end_to_end_rollout_rejects_bad_artifact_routing(tmp_path):
    stage4 = _stage4_module()
    metrics_path = tmp_path / "controller-stage4-metrics.jsonl"

    stage4.write_task_metrics(
        metrics_path,
        stage4.build_task_metrics(
            task_id="baseline-0",
            phase="baseline",
            controller_tokens=1200,
            file_count_inspected=4,
            diff_size_inspected=80,
            artifacts=[],
            fail_loop_count=0,
            integrity_check_failed=False,
            exception_path=False,
        ),
    )

    with pytest.raises(ValueError, match="artifact routing"):
        stage4.validate_end_to_end_rollout(
            metrics_path,
            task_runs=[
                {
                    "task_id": "34-bad-routing",
                    "controller_tokens": 900,
                    "file_count_inspected": 1,
                    "diff_size_inspected": 10,
                    "fail_loop_count": 0,
                    "merge_verified": True,
                    "cleanup_verified": True,
                    "merge_plan": {"selected_lanes": ["default"], "merge_order": ["default"]},
                    "lanes": [
                        {
                            "lane": "default",
                            "inspection_mode": "diff-first",
                            "exception_reasons": [],
                            "read_artifacts": [".hermes/artifacts/34-bad-routing/review.txt"],
                            "handoff_integrity_ok": True,
                            "artifact_paths": [],
                        }
                    ],
                }
            ],
            baseline_window=1,
        )


def test_validate_end_to_end_rollout_rejects_handoff_invalid_lane_and_does_not_summarize_fast_path(tmp_path):
    stage4 = _stage4_module()
    metrics_path = tmp_path / "controller-stage4-metrics.jsonl"

    stage4.write_task_metrics(
        metrics_path,
        stage4.build_task_metrics(
            task_id="baseline-0",
            phase="baseline",
            controller_tokens=1200,
            file_count_inspected=4,
            diff_size_inspected=80,
            artifacts=[],
            fail_loop_count=0,
            integrity_check_failed=False,
            exception_path=False,
        ),
    )

    with pytest.raises(ValueError, match="handoff integrity"):
        stage4.validate_end_to_end_rollout(
            metrics_path,
            task_runs=[
                {
                    "task_id": "34-handoff-invalid",
                    "controller_tokens": 900,
                    "file_count_inspected": 0,
                    "diff_size_inspected": 10,
                    "fail_loop_count": 0,
                    "merge_verified": True,
                    "cleanup_verified": True,
                    "merge_plan": {"selected_lanes": ["default"], "merge_order": ["default"]},
                    "lanes": [
                        {
                            "lane": "default",
                            "inspection_mode": "handoff-invalid",
                            "exception_reasons": [],
                            "read_artifacts": [],
                            "handoff_integrity_ok": False,
                            "artifact_paths": [],
                        }
                    ],
                }
            ],
            baseline_window=1,
        )
