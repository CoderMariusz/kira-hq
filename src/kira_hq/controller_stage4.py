"""Task 33 Stage 4 controller token-efficiency metrics and threshold tuning."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

DEFAULT_THRESHOLDS = {"touched_files": 8, "fail_loop": 2}
REQUIRED_METRIC_FIELDS = (
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
)


def build_task_metrics(
    *,
    task_id: str,
    phase: str,
    controller_tokens: int,
    file_count_inspected: int,
    diff_size_inspected: int,
    artifacts: Iterable[str | Path],
    fail_loop_count: int,
    integrity_check_failed: bool,
    exception_path: bool,
    thresholds: Mapping[str, int] | None = None,
    captured_at: str | None = None,
) -> dict:
    """Build one task-level metrics record for the Stage 4 tuning log."""
    artifact_paths = [Path(path).expanduser() for path in artifacts]
    metric = {
        "captured_at": captured_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "task_id": str(task_id),
        "phase": str(phase),
        "controller_tokens_per_task": int(controller_tokens),
        "avg_file_count_inspected": int(file_count_inspected),
        "avg_diff_size_inspected": int(diff_size_inspected),
        "artifact_count": len(artifact_paths),
        "artifact_bytes": sum(_artifact_size(path) for path in artifact_paths),
        "fail_loop_count": int(fail_loop_count),
        "integrity_check_failure_count": 1 if integrity_check_failed else 0,
        "exception_path_rate": 1.0 if exception_path else 0.0,
        "thresholds": _normalize_thresholds(thresholds),
    }
    return metric


def write_task_metrics(path: str | Path, record: Mapping[str, object]) -> Path:
    """Append one JSONL metrics record."""
    payload = dict(record)
    missing = [field for field in REQUIRED_METRIC_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"missing required Stage 4 metric fields: {', '.join(missing)}")
    metrics_path = Path(path).expanduser()
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    with metrics_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return metrics_path


def load_task_metrics(path: str | Path) -> list[dict]:
    metrics_path = Path(path).expanduser()
    if not metrics_path.exists():
        return []
    records: list[dict] = []
    for raw_line in metrics_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def compare_baseline_to_post_rollout(
    path: str | Path,
    *,
    baseline_window: int = 10,
    current_thresholds: Mapping[str, int] | None = None,
) -> dict:
    """Compare the pre-rollout baseline window to post-rollout task runs."""
    records = load_task_metrics(path)
    post_rollout = [record for record in records if record.get("phase") == "post-rollout"]
    first_post_rollout_index = next(
        (index for index, record in enumerate(records) if record.get("phase") == "post-rollout"),
        None,
    )
    baseline_candidates = (
        records[:first_post_rollout_index]
        if first_post_rollout_index is not None
        else [record for record in records if record.get("phase") != "post-rollout"]
    )
    baseline = baseline_candidates[-int(baseline_window) :] if baseline_window > 0 else baseline_candidates

    baseline_summary = _summarize_window(baseline)
    post_summary = _summarize_window(post_rollout)
    deltas = {
        metric: {
            "absolute": _round_metric(post_summary[metric] - baseline_summary[metric]),
            "percent": _percent_delta(baseline_summary[metric], post_summary[metric]),
        }
        for metric in _SUMMARY_METRICS
    }
    threshold_tuning = recommend_threshold_tuning(
        baseline_summary=baseline_summary,
        post_rollout_summary=post_summary,
        current_thresholds=current_thresholds,
    )
    return {
        "baseline_window": int(baseline_window),
        "baseline": baseline_summary,
        "post_rollout": post_summary,
        "deltas": deltas,
        "threshold_tuning": threshold_tuning,
        "weekly_review_summary": _weekly_review_summary(
            baseline_summary=baseline_summary,
            post_summary=post_summary,
            threshold_tuning=threshold_tuning,
        ),
        "dashboard_summary": {
            "baseline_tasks": baseline_summary["task_count"],
            "post_rollout_tasks": post_summary["task_count"],
            "controller_tokens_delta_pct": deltas["controller_tokens_per_task"]["percent"],
            "exception_path_rate_delta_pct": deltas["exception_path_rate"]["percent"],
            "recommended_touched_files_threshold": threshold_tuning["recommended_thresholds"]["touched_files"],
            "recommended_fail_loop_threshold": threshold_tuning["recommended_thresholds"]["fail_loop"],
        },
    }


def recommend_threshold_tuning(
    *,
    baseline_summary: Mapping[str, float | int],
    post_rollout_summary: Mapping[str, float | int],
    current_thresholds: Mapping[str, int] | None = None,
) -> dict:
    thresholds = _normalize_thresholds(current_thresholds)
    recommended = dict(thresholds)
    baseline_tokens = float(baseline_summary["controller_tokens_per_task"])
    post_tokens = float(post_rollout_summary["controller_tokens_per_task"])
    baseline_exception_rate = float(baseline_summary["exception_path_rate"])
    post_exception_rate = float(post_rollout_summary["exception_path_rate"])
    baseline_integrity_rate = float(baseline_summary["integrity_check_failure_count"])
    post_integrity_rate = float(post_rollout_summary["integrity_check_failure_count"])
    baseline_fail_loops = float(baseline_summary.get("fail_loop_count", 0) or 0)
    post_fail_loops = float(post_rollout_summary.get("fail_loop_count", 0) or 0)

    safe_exception_ceiling = max(baseline_exception_rate + 0.05, baseline_exception_rate * 1.10)
    insufficient_token_gain = baseline_tokens > 0 and post_tokens > baseline_tokens * 0.95
    fail_loop_risk_rose = post_fail_loops > max(baseline_fail_loops, float(thresholds["fail_loop"]))

    action = "hold"
    rationale = [
        f"controller tokens/task {baseline_tokens:.1f} -> {post_tokens:.1f}",
        f"exception-path rate {baseline_exception_rate:.2f} -> {post_exception_rate:.2f}",
        f"fail loops/task {baseline_fail_loops:.2f} -> {post_fail_loops:.2f}",
    ]
    if post_integrity_rate > baseline_integrity_rate or post_exception_rate > max(0.25, baseline_exception_rate * 1.25):
        recommended["touched_files"] = max(1, thresholds["touched_files"] - 1)
        if fail_loop_risk_rose:
            recommended["fail_loop"] = max(1, thresholds["fail_loop"] - 1)
        action = "tighten_diff_escalation"
        rationale.append("post-rollout risk indicators rose, so route full diff earlier")
    elif fail_loop_risk_rose:
        recommended["fail_loop"] = max(1, thresholds["fail_loop"] - 1)
        action = "tighten_diff_escalation"
        rationale.append("fail-loop frequency rose above the current trigger, so escalate sooner on repeated retries")
    elif insufficient_token_gain and post_exception_rate <= safe_exception_ceiling and post_integrity_rate <= baseline_integrity_rate:
        recommended["touched_files"] = thresholds["touched_files"] + 1
        action = "relax_diff_escalation"
        rationale.append("token savings are marginal while exception-path and integrity rates stay bounded")
    else:
        rationale.append("keep current thresholds until another weekly comparison window is available")

    return {
        "action": action,
        "current_thresholds": thresholds,
        "recommended_thresholds": recommended,
        "rationale": rationale,
    }


def validate_end_to_end_rollout(
    path: str | Path,
    *,
    task_runs: Iterable[Mapping[str, object]],
    baseline_window: int = 10,
    current_thresholds: Mapping[str, int] | None = None,
) -> dict:
    """Record validated Stage 1-4 rollout runs and summarize rollout proof points."""
    run_summaries: list[dict] = []

    for raw_run in task_runs:
        lanes = _coerce_lanes(raw_run.get("lanes"))
        if not lanes:
            raise ValueError("task runs must include at least one lane summary")
        if not bool(raw_run.get("cleanup_verified")):
            raise ValueError("cleanup verification is required before recording rollout validation")
        if not bool(raw_run.get("merge_verified")):
            raise ValueError("merge verification is required before recording rollout validation")

        merge_plan = raw_run.get("merge_plan")
        merge_back_local = merge_plan is not None
        if merge_back_local:
            selected_lanes = [str(lane) for lane in _mapping_get(merge_plan, "selected_lanes", [])]
            merge_order = [str(lane) for lane in _mapping_get(merge_plan, "merge_order", [])]
            if set(selected_lanes) != set(merge_order):
                raise ValueError("merge plan must include the same selected lanes and merge order lanes")

        exception_path = any(
            lane["inspection_mode"] in {"full-diff", "handoff-invalid"} or bool(lane["exception_reasons"])
            for lane in lanes
        )
        integrity_failed = any(
            lane["inspection_mode"] == "handoff-invalid" or not lane["handoff_integrity_ok"]
            for lane in lanes
        )
        artifact_paths = [path for lane in lanes for path in lane["artifact_paths"]]
        artifact_routing_ok = all(_artifact_routing_ok(lane) for lane in lanes)
        if integrity_failed:
            raise ValueError("handoff integrity validation failed for one or more lanes")
        if not artifact_routing_ok:
            raise ValueError("artifact routing validation failed for one or more lanes")
        controller_path = "exception-path" if exception_path else "fast-path"

        record = build_task_metrics(
            task_id=str(raw_run.get("task_id", "")).strip(),
            phase="post-rollout",
            controller_tokens=int(raw_run.get("controller_tokens", 0) or 0),
            file_count_inspected=int(raw_run.get("file_count_inspected", 0) or 0),
            diff_size_inspected=int(raw_run.get("diff_size_inspected", 0) or 0),
            artifacts=artifact_paths,
            fail_loop_count=int(raw_run.get("fail_loop_count", 0) or 0),
            integrity_check_failed=integrity_failed,
            exception_path=exception_path,
            thresholds=current_thresholds,
        )
        write_task_metrics(path, record)
        run_summaries.append(
            {
                "task_id": record["task_id"],
                "controller_path": controller_path,
                "parallel_lanes": len(lanes) > 1,
                "integrity_check_passed": not integrity_failed,
                "artifact_routing_ok": artifact_routing_ok,
                "merge_back_local": merge_back_local,
                "cleanup_verified": bool(raw_run.get("cleanup_verified")),
                "inspection_modes": [lane["inspection_mode"] for lane in lanes],
                "artifact_count": record["artifact_count"],
                "exception_reasons": [reason for lane in lanes for reason in lane["exception_reasons"]],
            }
        )

    comparison = compare_baseline_to_post_rollout(
        path,
        baseline_window=baseline_window,
        current_thresholds=current_thresholds,
    )
    baseline_tokens = comparison["baseline"]["controller_tokens_per_task"]
    post_tokens = comparison["post_rollout"]["controller_tokens_per_task"]
    token_savings = {
        "baseline_avg_tokens": baseline_tokens,
        "post_rollout_avg_tokens": post_tokens,
        "tokens_saved_per_task": _round_metric(float(baseline_tokens) - float(post_tokens)),
        "percent_reduction": _percent_reduction(float(baseline_tokens), float(post_tokens)),
    }
    validation_summary = {
        "tasks_validated": len(run_summaries),
        "fast_path_tasks": sum(run["controller_path"] == "fast-path" for run in run_summaries),
        "exception_path_tasks": sum(run["controller_path"] == "exception-path" for run in run_summaries),
        "parallel_tasks": sum(run["parallel_lanes"] for run in run_summaries),
        "all_merges_local": all(run["merge_back_local"] for run in run_summaries),
        "all_cleanups_verified": all(run["cleanup_verified"] for run in run_summaries),
    }
    return {
        "task_runs": run_summaries,
        "comparison": comparison,
        "token_savings": token_savings,
        "validation_summary": validation_summary,
    }


_SUMMARY_METRICS = (
    "controller_tokens_per_task",
    "avg_file_count_inspected",
    "avg_diff_size_inspected",
    "artifact_count",
    "artifact_bytes",
    "fail_loop_count",
    "integrity_check_failure_count",
    "exception_path_rate",
)


def _summarize_window(records: Iterable[Mapping[str, object]]) -> dict:
    entries = list(records)
    task_count = len(entries)
    summary = {"task_count": task_count}
    for metric in _SUMMARY_METRICS:
        values = [float(entry.get(metric, 0) or 0) for entry in entries]
        summary[metric] = _round_metric(sum(values) / task_count) if task_count else 0.0
    return summary


def _weekly_review_summary(
    *,
    baseline_summary: Mapping[str, float | int],
    post_summary: Mapping[str, float | int],
    threshold_tuning: Mapping[str, object],
) -> str:
    recommended = threshold_tuning["recommended_thresholds"]
    return (
        "Stage 4 token-efficiency comparison: "
        f"controller tokens/task {float(baseline_summary['controller_tokens_per_task']):.1f} → "
        f"{float(post_summary['controller_tokens_per_task']):.1f}; "
        f"files inspected {float(baseline_summary['avg_file_count_inspected']):.1f} → "
        f"{float(post_summary['avg_file_count_inspected']):.1f}; "
        f"diff size {float(baseline_summary['avg_diff_size_inspected']):.1f} → "
        f"{float(post_summary['avg_diff_size_inspected']):.1f}. "
        f"Recommendation: {threshold_tuning['action']} with touched_files={recommended['touched_files']} "
        f"and fail_loop={recommended['fail_loop']}."
    )


def _artifact_size(path: Path) -> int:
    try:
        return path.stat().st_size if path.exists() and path.is_file() else 0
    except OSError:
        return 0


def _coerce_lanes(raw_lanes: object) -> list[dict]:
    lanes: list[dict] = []
    for raw_lane in raw_lanes or []:
        lane = dict(raw_lane)
        lanes.append(
            {
                "lane": str(lane.get("lane", "")).strip(),
                "inspection_mode": str(lane.get("inspection_mode", "")).strip(),
                "exception_reasons": [str(reason) for reason in lane.get("exception_reasons", [])],
                "read_artifacts": [str(path) for path in lane.get("read_artifacts", [])],
                "handoff_integrity_ok": bool(lane.get("handoff_integrity_ok", False)),
                "artifact_paths": [str(path) for path in lane.get("artifact_paths", [])],
            }
        )
    return lanes


def _artifact_routing_ok(lane: Mapping[str, object]) -> bool:
    inspection_mode = str(lane.get("inspection_mode", "")).strip()
    read_artifacts = [str(path) for path in lane.get("read_artifacts", [])]
    return bool(read_artifacts) if inspection_mode == "full-diff" else not read_artifacts


def _mapping_get(value: object, key: str, default: object) -> object:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _normalize_thresholds(thresholds: Mapping[str, int] | None) -> dict:
    merged = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        merged.update({key: int(value) for key, value in thresholds.items()})
    return {"touched_files": int(merged["touched_files"]), "fail_loop": int(merged["fail_loop"])}


def _percent_delta(before: float | int, after: float | int) -> float:
    baseline = float(before)
    current = float(after)
    if baseline == 0:
        return 0.0 if current == 0 else 100.0
    return round(((current - baseline) / baseline) * 100, 2)


def _percent_reduction(before: float, after: float) -> float:
    if before == 0:
        return 0.0
    return round(((before - after) / before) * 100, 2)


def _round_metric(value: float) -> float | int:
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return int(rounded)
    return rounded


__all__ = [
    "DEFAULT_THRESHOLDS",
    "REQUIRED_METRIC_FIELDS",
    "build_task_metrics",
    "write_task_metrics",
    "load_task_metrics",
    "compare_baseline_to_post_rollout",
    "recommend_threshold_tuning",
    "validate_end_to_end_rollout",
]
