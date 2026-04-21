"""Task 29 Stage 2 controller inspection decisions."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


ARTIFACT_ROOT_PREFIX = ".hermes/artifacts"
OPERATIONAL_NOISE_FILES = {
    ".taskmaster/tasks/tasks.json",
    "kanban_board.md",
    "pipeline.log.md",
}
SENSITIVE_PATH_MARKERS = (
    "/auth",
    "/secrets",
    "/token",
    "/credential",
)


@dataclass
class ChangedFileClassification:
    semantic_files: list[str]
    operational_files: list[str]
    targeted_operational_files: list[str]


@dataclass
class ExceptionTriggerEvaluation:
    reasons: list[str]
    requires_full_diff: bool


@dataclass
class ControllerInspectionPlan:
    inspection_mode: str
    git_commands: list[str]
    artifact_root: str
    semantic_files: list[str]
    operational_files: list[str]
    targeted_operational_files: list[str]
    read_artifacts: list[str]
    exception_reasons: list[str]
    handoff_failure_reasons: list[str]


def artifact_root_for(task_id: str) -> str:
    return f"{ARTIFACT_ROOT_PREFIX}/{str(task_id).strip()}/"


def normalize_changed_files(changed_files: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for raw_path in changed_files:
        path = str(raw_path).strip().replace("\\", "/")
        while path.startswith("./"):
            path = path[2:]
        normalized_path = str(PurePosixPath(path)) if path else ""
        if not normalized_path or normalized_path == "." or normalized_path in seen:
            continue
        seen.add(normalized_path)
        normalized.append(normalized_path)

    return normalized


def classify_changed_files(
    changed_files: Iterable[str],
    explicitly_targeted: Iterable[str],
) -> ChangedFileClassification:
    normalized_files = normalize_changed_files(changed_files)
    targeted = set(normalize_changed_files(explicitly_targeted))

    semantic_files: list[str] = []
    operational_files: list[str] = []
    targeted_operational_files: list[str] = []

    for path in normalized_files:
        if path in OPERATIONAL_NOISE_FILES:
            if path in targeted:
                semantic_files.append(path)
                targeted_operational_files.append(path)
            else:
                operational_files.append(path)
            continue
        semantic_files.append(path)

    return ChangedFileClassification(
        semantic_files=semantic_files,
        operational_files=operational_files,
        targeted_operational_files=targeted_operational_files,
    )


def evaluate_exception_triggers(
    changed_files: Iterable[str],
    fail_loop_count: int,
    risk_level: str,
    prd_ambiguity: bool,
    review_failed: bool,
    qa_failed: bool,
) -> ExceptionTriggerEvaluation:
    normalized_files = normalize_changed_files(changed_files)
    semantic_files = [path for path in normalized_files if path not in OPERATIONAL_NOISE_FILES]
    reasons: list[str] = []

    if len(normalized_files) > 8:
        reasons.append("touched_files>8")
    if any(_is_sensitive_path(path) for path in normalized_files):
        reasons.append("sensitive_path")
    if fail_loop_count >= 2:
        reasons.append("fail_loop>=2")
    if str(risk_level).upper() == "HIGH":
        reasons.append("risk:HIGH")
    if prd_ambiguity:
        reasons.append("prd_ambiguity")
    if review_failed:
        reasons.append("review_failed")
    if qa_failed:
        reasons.append("qa_failed")
    if len({_module_key(path) for path in semantic_files}) > 2:
        reasons.append("modules_touched>2")

    return ExceptionTriggerEvaluation(
        reasons=reasons,
        requires_full_diff=bool(reasons),
    )


def plan_controller_inspection(
    task_id: str,
    handoff: dict,
    git_summary: dict,
    explicitly_targeted: Iterable[str],
    fail_loop_count: int,
    risk_level: str,
    prd_ambiguity: bool,
    review_failed: bool,
    qa_failed: bool,
) -> ControllerInspectionPlan:
    git_name_only = git_summary.get("name_only") or []
    handoff_files = [entry.get("path", "") for entry in handoff.get("files", [])]
    changed_files = normalize_changed_files(git_name_only or handoff_files)
    handoff_failure_reasons = evaluate_handoff_integrity(
        task_id=task_id,
        handoff=handoff,
        git_changed_files=git_name_only,
    )

    if handoff_failure_reasons:
        return ControllerInspectionPlan(
            inspection_mode="handoff-invalid",
            git_commands=["git diff --name-only", "git diff --stat"],
            artifact_root=artifact_root_for(task_id),
            semantic_files=[],
            operational_files=[],
            targeted_operational_files=[],
            read_artifacts=[],
            exception_reasons=[],
            handoff_failure_reasons=handoff_failure_reasons,
        )

    classification = classify_changed_files(changed_files, explicitly_targeted=explicitly_targeted)
    exception_state = evaluate_exception_triggers(
        changed_files,
        fail_loop_count=fail_loop_count,
        risk_level=risk_level,
        prd_ambiguity=prd_ambiguity,
        review_failed=review_failed,
        qa_failed=qa_failed,
    )

    git_commands = ["git diff --name-only", "git diff --stat"]
    if exception_state.requires_full_diff:
        git_commands.append("git diff")

    return ControllerInspectionPlan(
        inspection_mode="full-diff" if exception_state.requires_full_diff else "diff-first",
        git_commands=git_commands,
        artifact_root=artifact_root_for(task_id),
        semantic_files=classification.semantic_files,
        operational_files=classification.operational_files,
        targeted_operational_files=classification.targeted_operational_files,
        read_artifacts=list(handoff.get("artifacts", [])) if exception_state.requires_full_diff else [],
        exception_reasons=exception_state.reasons,
        handoff_failure_reasons=[],
    )


def evaluate_handoff_integrity(
    task_id: str,
    handoff: dict,
    git_changed_files: Iterable[str],
) -> list[str]:
    reasons: list[str] = []
    declared_files = normalize_changed_files(entry.get("path", "") for entry in handoff.get("files", []))
    actual_files = normalize_changed_files(git_changed_files)

    if set(declared_files) != set(actual_files):
        reasons.append("declared_files_mismatch")

    if str(handoff.get("task_id", "")).strip() != str(task_id).strip():
        reasons.append("task_id_mismatch")

    handoff_worktree = str(handoff.get("worktree", "")).strip()
    if not handoff_worktree:
        reasons.append("worktree_missing")
    elif _normalize_worktree(handoff_worktree) != _normalize_worktree(_current_worktree()):
        reasons.append("worktree_mismatch")

    return reasons


def _is_sensitive_path(path: str) -> bool:
    lowered = f"/{path.lower().strip('/')}"
    return any(marker in lowered for marker in SENSITIVE_PATH_MARKERS)


def _module_key(path: str) -> str:
    pure_path = PurePosixPath(path)
    parts = pure_path.parts
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return path


def _current_worktree() -> str:
    current = Path.cwd().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return str(candidate)
    return str(current)


def _normalize_worktree(path: str) -> str:
    return str(Path(path).expanduser().resolve())


__all__ = [
    "ChangedFileClassification",
    "ControllerInspectionPlan",
    "ExceptionTriggerEvaluation",
    "artifact_root_for",
    "classify_changed_files",
    "evaluate_handoff_integrity",
    "evaluate_exception_triggers",
    "normalize_changed_files",
    "plan_controller_inspection",
]
