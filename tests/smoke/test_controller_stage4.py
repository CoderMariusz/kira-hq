"""Smoke tests for Task 33 Stage 4 controller token-efficiency metrics."""
from __future__ import annotations

import importlib
import json

import pytest

pytestmark = pytest.mark.smoke


REQUIRED_FIELDS = {
    "task_id",
    "phase",
    "controller_tokens_per_task",
    "avg_file_count_inspected",
    "avg_diff_size_inspected",
    "artifact_count",
    "artifact_bytes",
    "fail_loop_count",
    "integrity_check_failure_count",
    "exception_path_rate",
    "thresholds",
}


def _controller_stage4_module():
    return importlib.import_module("kira_hq.controller_stage4")


def test_write_task_metrics_records_all_required_stage4_fields(tmp_path):
    module = _controller_stage4_module()
    artifact_dir = tmp_path / ".hermes" / "artifacts" / "33"
    artifact_dir.mkdir(parents=True)
    report = artifact_dir / "review.txt"
    report.write_text("review ok\n")
    diff = artifact_dir / "diff.patch"
    diff.write_text("+hello\n-world\n")
    log_path = tmp_path / "controller-stage4-metrics.jsonl"

    record = module.build_task_metrics(
        task_id="33",
        phase="post-rollout",
        controller_tokens=1440,
        file_count_inspected=3,
        diff_size_inspected=48,
        artifacts=[report, diff],
        fail_loop_count=2,
        integrity_check_failed=True,
        exception_path=True,
    )

    module.write_task_metrics(log_path, record)

    rows = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    assert len(rows) == 1
    payload = rows[0]
    assert REQUIRED_FIELDS.issubset(payload)
    assert payload["task_id"] == "33"
    assert payload["phase"] == "post-rollout"
    assert payload["controller_tokens_per_task"] == 1440
    assert payload["avg_file_count_inspected"] == 3
    assert payload["avg_diff_size_inspected"] == 48
    assert payload["artifact_count"] == 2
    assert payload["artifact_bytes"] == len("review ok\n") + len("+hello\n-world\n")
    assert payload["fail_loop_count"] == 2
    assert payload["integrity_check_failure_count"] == 1
    assert payload["exception_path_rate"] == 1.0
    assert payload["thresholds"] == {"touched_files": 8, "fail_loop": 2}
