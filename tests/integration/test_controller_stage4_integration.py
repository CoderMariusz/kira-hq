"""Integration tests for Task 33 Stage 4 controller token-efficiency comparisons."""
from __future__ import annotations

import importlib

import pytest

pytestmark = pytest.mark.integration


def _controller_stage4_module():
    return importlib.import_module("kira_hq.controller_stage4")


def test_compare_baseline_window_to_post_rollout_produces_weekly_review_summary(tmp_path):
    module = _controller_stage4_module()
    metrics_path = tmp_path / "controller-stage4-metrics.jsonl"

    for index in range(10):
        module.write_task_metrics(
            metrics_path,
            module.build_task_metrics(
                task_id=f"baseline-{index}",
                phase="baseline",
                controller_tokens=1200,
                file_count_inspected=6,
                diff_size_inspected=110,
                artifacts=[],
                fail_loop_count=1,
                integrity_check_failed=False,
                exception_path=False,
            ),
        )

    for index in range(2):
        module.write_task_metrics(
            metrics_path,
            module.build_task_metrics(
                task_id=f"post-{index}",
                phase="post-rollout",
                controller_tokens=1180,
                file_count_inspected=4,
                diff_size_inspected=70,
                artifacts=[],
                fail_loop_count=1,
                integrity_check_failed=False,
                exception_path=False,
            ),
        )

    summary = module.compare_baseline_to_post_rollout(metrics_path, baseline_window=10)

    assert summary["baseline"]["task_count"] == 10
    assert summary["post_rollout"]["task_count"] == 2
    assert summary["baseline"]["controller_tokens_per_task"] == 1200
    assert summary["post_rollout"]["controller_tokens_per_task"] == 1180
    assert summary["baseline"]["avg_file_count_inspected"] == 6
    assert summary["post_rollout"]["avg_file_count_inspected"] == 4
    assert summary["baseline"]["avg_diff_size_inspected"] == 110
    assert summary["post_rollout"]["avg_diff_size_inspected"] == 70
    assert summary["deltas"]["controller_tokens_per_task"]["absolute"] == -20
    assert summary["deltas"]["exception_path_rate"]["absolute"] == 0.0
    assert summary["threshold_tuning"]["action"] == "relax_diff_escalation"
    assert summary["threshold_tuning"]["recommended_thresholds"] == {"touched_files": 9, "fail_loop": 2}
    assert "controller tokens/task 1200.0 → 1180.0" in summary["weekly_review_summary"]
    assert summary["dashboard_summary"] == {
        "baseline_tasks": 10,
        "post_rollout_tasks": 2,
        "controller_tokens_delta_pct": -1.67,
        "exception_path_rate_delta_pct": 0.0,
        "recommended_touched_files_threshold": 9,
        "recommended_fail_loop_threshold": 2,
    }


def test_recommend_threshold_tuning_tightens_when_risk_indicators_rise():
    module = _controller_stage4_module()

    summary = module.recommend_threshold_tuning(
        baseline_summary={
            "controller_tokens_per_task": 1200,
            "exception_path_rate": 0.10,
            "integrity_check_failure_count": 0.0,
            "fail_loop_count": 1.0,
        },
        post_rollout_summary={
            "controller_tokens_per_task": 1000,
            "exception_path_rate": 0.35,
            "integrity_check_failure_count": 0.0,
            "fail_loop_count": 3.0,
        },
        current_thresholds={"touched_files": 8, "fail_loop": 2},
    )

    assert summary["action"] == "tighten_diff_escalation"
    assert summary["recommended_thresholds"] == {"touched_files": 7, "fail_loop": 1}


def test_recommend_threshold_tuning_tightens_fail_loop_threshold_when_fail_loops_rise():
    module = _controller_stage4_module()

    summary = module.recommend_threshold_tuning(
        baseline_summary={
            "controller_tokens_per_task": 1200,
            "exception_path_rate": 0.10,
            "integrity_check_failure_count": 0.0,
            "fail_loop_count": 1.0,
        },
        post_rollout_summary={
            "controller_tokens_per_task": 1000,
            "exception_path_rate": 0.10,
            "integrity_check_failure_count": 0.0,
            "fail_loop_count": 3.0,
        },
        current_thresholds={"touched_files": 8, "fail_loop": 2},
    )

    assert summary["action"] == "tighten_diff_escalation"
    assert summary["recommended_thresholds"] == {"touched_files": 8, "fail_loop": 1}


def test_compare_baseline_window_uses_prior_tasks_only_when_non_post_records_follow_rollout(tmp_path):
    module = _controller_stage4_module()
    metrics_path = tmp_path / "controller-stage4-metrics.jsonl"

    module.write_task_metrics(
        metrics_path,
        module.build_task_metrics(
            task_id="baseline-early",
            phase="baseline",
            controller_tokens=800,
            file_count_inspected=4,
            diff_size_inspected=90,
            artifacts=[],
            fail_loop_count=1,
            integrity_check_failed=False,
            exception_path=False,
        ),
    )
    module.write_task_metrics(
        metrics_path,
        module.build_task_metrics(
            task_id="baseline-late",
            phase="baseline",
            controller_tokens=1000,
            file_count_inspected=5,
            diff_size_inspected=95,
            artifacts=[],
            fail_loop_count=1,
            integrity_check_failed=False,
            exception_path=False,
        ),
    )
    module.write_task_metrics(
        metrics_path,
        module.build_task_metrics(
            task_id="post-0",
            phase="post-rollout",
            controller_tokens=900,
            file_count_inspected=3,
            diff_size_inspected=60,
            artifacts=[],
            fail_loop_count=1,
            integrity_check_failed=False,
            exception_path=False,
        ),
    )
    module.write_task_metrics(
        metrics_path,
        module.build_task_metrics(
            task_id="baseline-after-rollout",
            phase="baseline",
            controller_tokens=4000,
            file_count_inspected=20,
            diff_size_inspected=500,
            artifacts=[],
            fail_loop_count=4,
            integrity_check_failed=True,
            exception_path=True,
        ),
    )

    summary = module.compare_baseline_to_post_rollout(metrics_path, baseline_window=2)

    assert summary["baseline"]["task_count"] == 2
    assert summary["baseline"]["controller_tokens_per_task"] == 900
    assert summary["baseline"]["avg_file_count_inspected"] == 4.5
