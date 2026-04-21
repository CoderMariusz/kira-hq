"""Smoke tests for Task 29 Stage 2 controller policy."""
from __future__ import annotations

import importlib
from dataclasses import asdict, is_dataclass
from pathlib import Path

import pytest

pytestmark = pytest.mark.smoke


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


OPERATIONAL_NOISE = [
    ".taskmaster/tasks/tasks.json",
    "kanban_board.md",
    "pipeline.log.md",
]


def test_artifact_root_for_uses_task_scoped_hermes_prefix():
    assert _call("artifact_root_for", "29") == ".hermes/artifacts/29/"
    assert _call("artifact_root_for", "T-29") == ".hermes/artifacts/T-29/"


def test_normalize_changed_files_trims_relative_markers_and_deduplicates_in_order():
    changed = [
        " ./src/kira_hq/controller_stage2.py ",
        "tests/smoke/test_controller_stage2.py",
        "src/kira_hq/controller_stage2.py",
        "./kanban_board.md",
    ]

    assert _call("normalize_changed_files", changed) == [
        "src/kira_hq/controller_stage2.py",
        "tests/smoke/test_controller_stage2.py",
        "kanban_board.md",
    ]


def test_classify_changed_files_marks_operational_noise_out_of_semantic_review_by_default():
    result = _as_dict(
        _call(
            "classify_changed_files",
            [
                "src/kira_hq/controller_stage2.py",
                *OPERATIONAL_NOISE,
            ],
            explicitly_targeted=[],
        )
    )

    assert result["semantic_files"] == ["src/kira_hq/controller_stage2.py"]
    assert result["operational_files"] == OPERATIONAL_NOISE
    assert result["targeted_operational_files"] == []


def test_classify_changed_files_reenters_targeted_noise_into_semantic_scope():
    result = _as_dict(
        _call(
            "classify_changed_files",
            [
                "src/kira_hq/controller_stage2.py",
                "kanban_board.md",
                "pipeline.log.md",
            ],
            explicitly_targeted=["kanban_board.md"],
        )
    )

    assert result["semantic_files"] == [
        "src/kira_hq/controller_stage2.py",
        "kanban_board.md",
    ]
    assert result["operational_files"] == ["pipeline.log.md"]
    assert result["targeted_operational_files"] == ["kanban_board.md"]


@pytest.mark.parametrize(
    ("changed_files", "kwargs", "expected_reason"),
    [
        ([f"src/module_{n}.py" for n in range(9)], {}, "touched_files>8"),
        (["src/kira_hq/auth.py"], {}, "sensitive_path"),
        (["src/kira_hq/controller_stage2.py"], {"fail_loop_count": 2}, "fail_loop>=2"),
        (["src/kira_hq/controller_stage2.py"], {"risk_level": "HIGH"}, "risk:HIGH"),
        (["src/kira_hq/controller_stage2.py"], {"prd_ambiguity": True}, "prd_ambiguity"),
        (["src/kira_hq/controller_stage2.py"], {"review_failed": True}, "review_failed"),
        (["src/kira_hq/controller_stage2.py"], {"qa_failed": True}, "qa_failed"),
        (
            [
                "src/pkg_alpha/a.py",
                "src/pkg_beta/b.py",
                "tests/test_gamma.py",
            ],
            {},
            "modules_touched>2",
        ),
    ],
)
def test_evaluate_exception_triggers_reports_each_policy_trigger(changed_files, kwargs, expected_reason):
    result = _as_dict(
        _call(
            "evaluate_exception_triggers",
            changed_files,
            **{
                "fail_loop_count": 0,
                "risk_level": "LOW",
                "prd_ambiguity": False,
                "review_failed": False,
                "qa_failed": False,
                **kwargs,
            },
        )
    )

    assert expected_reason in result["reasons"]
    assert result["requires_full_diff"] is True


def test_plan_controller_inspection_defaults_to_diff_first_and_summary_first_reads():
    handoff = {
        "task_id": "29",
        "worktree": str(Path.cwd()),
        "files": [
            {"path": "src/kira_hq/controller_stage2.py", "intent": "create"},
            {"path": "kanban_board.md", "intent": "modify"},
        ],
        "artifacts": [
            ".hermes/artifacts/29/review.txt",
            ".hermes/artifacts/29/green-test.log",
        ],
        "risks": ["normal policy coverage"],
        "next": "controller_review",
        "status": "completed",
    }
    git_summary = {
        "name_only": ["src/kira_hq/controller_stage2.py", "kanban_board.md"],
        "stat": " src/kira_hq/controller_stage2.py | 42 +++++++++++++++++++++++++++++\n kanban_board.md | 3 ++-",
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

    assert plan["inspection_mode"] == "diff-first"
    assert plan["git_commands"] == ["git diff --name-only", "git diff --stat"]
    assert plan["artifact_root"] == ".hermes/artifacts/29/"
    assert plan["semantic_files"] == ["src/kira_hq/controller_stage2.py"]
    assert plan["operational_files"] == ["kanban_board.md"]
    assert plan["read_artifacts"] == []
    assert plan["exception_reasons"] == []


def test_plan_controller_inspection_does_not_escalate_for_operational_noise_only_module_spread():
    handoff = {
        "task_id": "29",
        "worktree": str(Path.cwd()),
        "files": [
            {"path": "src/kira_hq/controller_stage2.py", "intent": "create"},
            {"path": "kanban_board.md", "intent": "modify"},
            {"path": "pipeline.log.md", "intent": "modify"},
        ],
        "artifacts": [".hermes/artifacts/29/review.txt"],
        "risks": [],
        "next": "controller_review",
        "status": "completed",
    }
    git_summary = {
        "name_only": [
            "src/kira_hq/controller_stage2.py",
            "kanban_board.md",
            "pipeline.log.md",
        ],
        "stat": " src/kira_hq/controller_stage2.py | 4 ++--\n kanban_board.md | 2 +-\n pipeline.log.md | 2 +-",
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

    assert plan["inspection_mode"] == "diff-first"
    assert plan["git_commands"] == ["git diff --name-only", "git diff --stat"]
    assert plan["exception_reasons"] == []
