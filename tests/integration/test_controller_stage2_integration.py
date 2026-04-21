"""Integration tests for Stage 2 controller inspection planning and integrity gating."""
from __future__ import annotations

import importlib
import subprocess
from dataclasses import asdict, is_dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration


def _controller_stage2_module():
    return importlib.import_module("kira_hq.controller_stage2")


def _call(name: str, /, *args, **kwargs):
    module = _controller_stage2_module()
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
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "config", "user.email", "test@example.com")

    _write(repo, "src/pkg/module.py", "def value():\n    return 1\n")
    _write(repo, "src/kira_hq/auth.py", "def authenticate():\n    return True\n")
    _write(repo, "kanban_board.md", "# Board\n")

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    return repo


def _git_summary(repo: Path) -> dict[str, object]:
    return {
        "name_only": [line for line in _git(repo, "diff", "--name-only").splitlines() if line],
        "stat": _git(repo, "diff", "--stat"),
    }


def _handoff(task_id: str, worktree: str, files: list[str]) -> dict[str, object]:
    return {
        "task_id": task_id,
        "worktree": worktree,
        "files": [{"path": path, "intent": "modify"} for path in files],
        "artifacts": [f".hermes/artifacts/{task_id}/review.txt"],
        "risks": [],
        "next": "controller_review",
        "status": "completed",
    }


def test_plan_controller_inspection_routes_sensitive_or_failed_work_to_full_diff_review():
    handoff = {
        "task_id": "29",
        "worktree": str(Path.cwd()),
        "files": [
            {"path": "src/kira_hq/auth.py", "intent": "modify"},
            {"path": "pipeline.log.md", "intent": "modify"},
        ],
        "artifacts": [
            ".hermes/artifacts/29/review.txt",
            ".hermes/artifacts/29/qa-checklist.md",
        ],
        "risks": ["auth flow regression risk"],
        "next": "controller_review",
        "status": "completed",
    }
    git_summary = {
        "name_only": ["src/kira_hq/auth.py", "pipeline.log.md"],
        "stat": " src/kira_hq/auth.py | 18 ++++++++++----\n pipeline.log.md | 7 ++++++-",
    }

    plan = _as_dict(
        _call(
            "plan_controller_inspection",
            task_id="29",
            handoff=handoff,
            git_summary=git_summary,
            explicitly_targeted=[],
            fail_loop_count=2,
            risk_level="HIGH",
            prd_ambiguity=False,
            review_failed=True,
            qa_failed=False,
        )
    )

    assert plan["inspection_mode"] == "full-diff"
    assert plan["git_commands"] == [
        "git diff --name-only",
        "git diff --stat",
        "git diff",
    ]
    assert set(plan["exception_reasons"]) >= {
        "sensitive_path",
        "fail_loop>=2",
        "risk:HIGH",
        "review_failed",
    }
    assert plan["semantic_files"] == ["src/kira_hq/auth.py"]
    assert plan["operational_files"] == ["pipeline.log.md"]
    assert plan["read_artifacts"] == [
        ".hermes/artifacts/29/review.txt",
        ".hermes/artifacts/29/qa-checklist.md",
    ]


def test_plan_controller_inspection_keeps_explicitly_targeted_operational_files_in_review_scope():
    handoff = {
        "task_id": "29",
        "worktree": str(Path.cwd()),
        "files": [
            {"path": "kanban_board.md", "intent": "modify"},
            {"path": ".taskmaster/tasks/tasks.json", "intent": "modify"},
        ],
        "artifacts": [".hermes/artifacts/29/status-summary.md"],
        "risks": [],
        "next": "controller_review",
        "status": "completed",
    }
    git_summary = {
        "name_only": ["kanban_board.md", ".taskmaster/tasks/tasks.json"],
        "stat": " kanban_board.md | 4 ++--\n .taskmaster/tasks/tasks.json | 10 ++++++----",
    }

    plan = _as_dict(
        _call(
            "plan_controller_inspection",
            task_id="29",
            handoff=handoff,
            git_summary=git_summary,
            explicitly_targeted=["kanban_board.md"],
            fail_loop_count=0,
            risk_level="LOW",
            prd_ambiguity=False,
            review_failed=False,
            qa_failed=False,
        )
    )

    assert plan["inspection_mode"] == "diff-first"
    assert plan["semantic_files"] == ["kanban_board.md"]
    assert plan["operational_files"] == [".taskmaster/tasks/tasks.json"]
    assert plan["targeted_operational_files"] == ["kanban_board.md"]
    assert plan["read_artifacts"] == []


def test_plan_controller_inspection_escalates_when_more_than_two_modules_are_touched():
    handoff = {
        "task_id": "29",
        "worktree": str(Path.cwd()),
        "files": [
            {"path": "src/api/router.py", "intent": "modify"},
            {"path": "src/services/sync.py", "intent": "modify"},
            {"path": "tests/integration/test_sync.py", "intent": "modify"},
        ],
        "artifacts": [".hermes/artifacts/29/review.txt"],
        "risks": [],
        "next": "controller_review",
        "status": "completed",
    }
    git_summary = {
        "name_only": [
            "src/api/router.py",
            "src/services/sync.py",
            "tests/integration/test_sync.py",
        ],
        "stat": (
            " src/api/router.py | 6 +++---\n"
            " src/services/sync.py | 8 +++++---\n"
            " tests/integration/test_sync.py | 5 +++--"
        ),
    }

    plan = _as_dict(
        _call(
            "plan_controller_inspection",
            task_id="29",
            handoff=handoff,
            git_summary=git_summary,
            explicitly_targeted=[],
            fail_loop_count=0,
            risk_level="LOW",
            prd_ambiguity=False,
            review_failed=False,
            qa_failed=False,
        )
    )

    assert plan["inspection_mode"] == "full-diff"
    assert "modules_touched>2" in plan["exception_reasons"]
    assert plan["git_commands"][-1] == "git diff"


def test_plan_controller_inspection_fails_closed_when_declared_files_do_not_match_git_diff(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path)
    _write(repo, "src/pkg/module.py", "def value():\n    return 2\n")
    monkeypatch.chdir(repo)

    plan = _as_dict(
        _call(
            "plan_controller_inspection",
            task_id="30",
            handoff=_handoff("30", str(repo), ["src/pkg/other.py"]),
            git_summary=_git_summary(repo),
            explicitly_targeted=[],
            fail_loop_count=0,
            risk_level="LOW",
            prd_ambiguity=False,
            review_failed=False,
            qa_failed=False,
        )
    )

    assert plan["inspection_mode"] == "handoff-invalid"
    assert plan["semantic_files"] == []
    assert plan["read_artifacts"] == []
    assert plan["handoff_failure_reasons"] == ["declared_files_mismatch"]


def test_plan_controller_inspection_keeps_matching_small_git_diff_on_fast_path(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path)
    _write(repo, "src/pkg/module.py", "def value():\n    return 2\n")
    _write(repo, "kanban_board.md", "# Board\n- task 30\n")
    monkeypatch.chdir(repo)

    plan = _as_dict(
        _call(
            "plan_controller_inspection",
            task_id="30",
            handoff=_handoff("30", str(repo), ["src/pkg/module.py", "kanban_board.md"]),
            git_summary=_git_summary(repo),
            explicitly_targeted=[],
            fail_loop_count=0,
            risk_level="LOW",
            prd_ambiguity=False,
            review_failed=False,
            qa_failed=False,
        )
    )

    assert plan["inspection_mode"] == "diff-first"
    assert plan["git_commands"] == ["git diff --name-only", "git diff --stat"]
    assert plan["semantic_files"] == ["src/pkg/module.py"]
    assert plan["operational_files"] == ["kanban_board.md"]
    assert plan.get("handoff_failure_reasons", []) == []


def test_plan_controller_inspection_escalates_matching_sensitive_diff_to_full_review(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path)
    _write(repo, "src/kira_hq/auth.py", "def authenticate():\n    return False\n")
    monkeypatch.chdir(repo)

    plan = _as_dict(
        _call(
            "plan_controller_inspection",
            task_id="30",
            handoff=_handoff("30", str(repo), ["src/kira_hq/auth.py"]),
            git_summary=_git_summary(repo),
            explicitly_targeted=[],
            fail_loop_count=0,
            risk_level="LOW",
            prd_ambiguity=False,
            review_failed=False,
            qa_failed=False,
        )
    )

    assert plan["inspection_mode"] == "full-diff"
    assert plan["git_commands"] == ["git diff --name-only", "git diff --stat", "git diff"]
    assert plan["exception_reasons"] == ["sensitive_path"]
    assert plan.get("handoff_failure_reasons", []) == []


def test_plan_controller_inspection_fails_closed_on_task_id_mismatch(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path)
    _write(repo, "src/pkg/module.py", "def value():\n    return 2\n")
    monkeypatch.chdir(repo)

    plan = _as_dict(
        _call(
            "plan_controller_inspection",
            task_id="30",
            handoff=_handoff("999", str(repo), ["src/pkg/module.py"]),
            git_summary=_git_summary(repo),
            explicitly_targeted=[],
            fail_loop_count=0,
            risk_level="LOW",
            prd_ambiguity=False,
            review_failed=False,
            qa_failed=False,
        )
    )

    assert plan["inspection_mode"] == "handoff-invalid"
    assert plan["semantic_files"] == []
    assert plan["read_artifacts"] == []
    assert plan["handoff_failure_reasons"] == ["task_id_mismatch"]


def test_plan_controller_inspection_fails_closed_on_worktree_mismatch(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path)
    _write(repo, "src/pkg/module.py", "def value():\n    return 2\n")
    monkeypatch.chdir(repo)

    plan = _as_dict(
        _call(
            "plan_controller_inspection",
            task_id="30",
            handoff=_handoff("30", str(repo.parent / "wrong-worktree"), ["src/pkg/module.py"]),
            git_summary=_git_summary(repo),
            explicitly_targeted=[],
            fail_loop_count=0,
            risk_level="LOW",
            prd_ambiguity=False,
            review_failed=False,
            qa_failed=False,
        )
    )

    assert plan["inspection_mode"] == "handoff-invalid"
    assert plan["semantic_files"] == []
    assert plan["read_artifacts"] == []
    assert plan["handoff_failure_reasons"] == ["worktree_mismatch"]


def test_plan_controller_inspection_fails_closed_on_missing_worktree(tmp_path, monkeypatch):
    repo = _init_git_repo(tmp_path)
    _write(repo, "src/pkg/module.py", "def value():\n    return 2\n")
    monkeypatch.chdir(repo)

    handoff = _handoff("30", str(repo), ["src/pkg/module.py"])
    handoff.pop("worktree")

    plan = _as_dict(
        _call(
            "plan_controller_inspection",
            task_id="30",
            handoff=handoff,
            git_summary=_git_summary(repo),
            explicitly_targeted=[],
            fail_loop_count=0,
            risk_level="LOW",
            prd_ambiguity=False,
            review_failed=False,
            qa_failed=False,
        )
    )

    assert plan["inspection_mode"] == "handoff-invalid"
    assert plan["semantic_files"] == []
    assert plan["read_artifacts"] == []
    assert plan["handoff_failure_reasons"] == ["worktree_missing"]
