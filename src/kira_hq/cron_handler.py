"""Cron handler — PRD §6.3 retry + stale policy.

Implements the 5-clause policy:
  1. Skill fails (exception or non-zero exit) → retry once after `retry_delay_s`
  2. Second failure → write incident + append pipeline_log status=fail
  3. Telegram alert via notifier.alert() (placeholder; real wiring in T-21)
  4. Mark project `status: stale` in projects.yaml
  5. Stale projects skipped by cron dispatcher until `/unstale <project>`

Public API:
    retry_then_log(skill_fn, project, skill, *, ...) -> SkillResult
    mark_stale(project_name, projects_yaml=...)   -> None
    unstale(project_name, projects_yaml=...)      -> bool
    is_stale(project_name, projects_yaml=...)     -> bool
    dispatch(skill_fn, projects_yaml=..., ...)    -> list[SkillResult]
"""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Union

import yaml

from kira_hq.incidents import Incident, write_incident
from kira_hq.pipeline_log import log_execution
from kira_hq.projects_yaml import DEFAULT_PROJECTS_YAML

PathLike = Union[str, Path]


class SkillFailure(RuntimeError):
    """Signals a skill invocation that should be retried / escalated."""

    def __init__(self, message: str, *, stderr: str = "", stdout: str = ""):
        super().__init__(message)
        self.stderr = stderr
        self.stdout = stdout


@dataclass
class SkillResult:
    project: str
    skill: str
    status: str  # "ok" | "fail" | "skip-stale"
    attempts: int = 0
    incident: Optional[Incident] = None
    notes: str = ""


class _DefaultNotifier:
    """Placeholder notifier. Real Telegram wiring lands in T-21."""

    def __init__(self) -> None:
        self.alerts: List[str] = []

    def alert(self, message: str) -> None:
        self.alerts.append(message)
        # T-21 replaces this with a Telegram POST. Left as stdout so cron
        # logs surface it even without the gateway.
        print(f"[ALERT] {message}")


notifier = _DefaultNotifier()


def _load_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def _save_yaml(path: Path, doc: dict) -> None:
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def _find_entry(doc: dict, project_name: str) -> Optional[dict]:
    for e in doc.get("projects", []) or []:
        if e.get("name") == project_name:
            return e
    return None


def mark_stale(
    project_name: str,
    projects_yaml: PathLike = DEFAULT_PROJECTS_YAML,
) -> None:
    path = Path(projects_yaml).expanduser()
    doc = _load_yaml(path)
    entry = _find_entry(doc, project_name)
    if entry is None:
        return
    entry["status"] = "stale"
    _save_yaml(path, doc)


def unstale(
    project_name: str,
    projects_yaml: PathLike = DEFAULT_PROJECTS_YAML,
) -> bool:
    """Return True if a stale project was successfully reactivated."""
    path = Path(projects_yaml).expanduser()
    doc = _load_yaml(path)
    entry = _find_entry(doc, project_name)
    if entry is None or entry.get("status") != "stale":
        return False
    entry["status"] = "active"
    _save_yaml(path, doc)
    return True


def is_stale(
    project_name: str,
    projects_yaml: PathLike = DEFAULT_PROJECTS_YAML,
) -> bool:
    path = Path(projects_yaml).expanduser()
    if not path.exists():
        return False
    doc = _load_yaml(path)
    entry = _find_entry(doc, project_name)
    return bool(entry and entry.get("status") == "stale")


def retry_then_log(
    skill_fn: Callable[[], object],
    project: str,
    skill: str,
    *,
    project_path: PathLike = ".",
    projects_yaml: PathLike = DEFAULT_PROJECTS_YAML,
    retry_delay_s: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
    incidents_dir: Optional[PathLike] = None,
) -> SkillResult:
    """Run skill_fn. On failure retry once; on second failure escalate.

    Escalation: write incident (§6.3 clause 2), pipeline log status=fail
    (§6.1), Telegram alert (clause 3), mark project stale (clause 4).
    """
    last_error = ""
    last_stderr = ""
    last_stdout = ""
    start = time.monotonic()

    for attempt in (1, 2):
        try:
            skill_fn()
            duration = round(time.monotonic() - start, 3)
            log_execution(
                project_path=Path(project_path).expanduser(),
                project=project, skill=skill, provider="n/a",
                expand_used=False, tokens_in=0, tokens_out=0,
                status="ok", duration_s=duration,
                notes=f"attempt {attempt}/2",
            )
            return SkillResult(project=project, skill=skill, status="ok",
                               attempts=attempt, notes=f"ok on attempt {attempt}")
        except SkillFailure as e:
            last_error = str(e)
            last_stderr = e.stderr
            last_stdout = e.stdout
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            last_stderr = traceback.format_exc()
            last_stdout = ""

        if attempt == 1:
            sleep(retry_delay_s)

    # Both attempts failed — escalate.
    duration = round(time.monotonic() - start, 3)
    incident = write_incident(
        project=project, skill=skill, error=last_error,
        stderr=last_stderr, stdout=last_stdout,
        incidents_dir=incidents_dir,
    )
    log_execution(
        project_path=Path(project_path).expanduser(),
        project=project, skill=skill, provider="n/a",
        expand_used=False, tokens_in=0, tokens_out=0,
        status="fail", duration_s=duration,
        notes=f"2 attempts; incident={incident.path.name}",
    )
    notifier.alert(
        f"🔴 {project}/{skill} failed twice. See incident {incident.path.name}."
    )
    mark_stale(project, projects_yaml)
    return SkillResult(
        project=project, skill=skill, status="fail",
        attempts=2, incident=incident,
        notes=f"2 attempts; incident={incident.path.name}",
    )


@dataclass
class DispatchReport:
    results: List[SkillResult] = field(default_factory=list)

    @property
    def n_ok(self) -> int:
        return sum(1 for r in self.results if r.status == "ok")

    @property
    def n_fail(self) -> int:
        return sum(1 for r in self.results if r.status == "fail")

    @property
    def n_skipped(self) -> int:
        return sum(1 for r in self.results if r.status == "skip-stale")


def dispatch(
    skill_fn: Callable[[dict], object],
    *,
    projects_yaml: PathLike = DEFAULT_PROJECTS_YAML,
    retry_delay_s: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
    incidents_dir: Optional[PathLike] = None,
) -> DispatchReport:
    """For each active project, call skill_fn(entry). Stale projects skipped.

    `skill_fn(entry)` must raise SkillFailure (or any Exception) on failure.
    """
    path = Path(projects_yaml).expanduser()
    doc = _load_yaml(path)
    report = DispatchReport()
    for entry in doc.get("projects", []) or []:
        name = entry.get("name", "?")
        status = entry.get("status", "active")
        if status == "archived":
            continue
        if status == "stale":
            report.results.append(SkillResult(
                project=name, skill="(dispatch)", status="skip-stale",
                notes="project marked stale — /unstale to re-enable",
            ))
            continue
        project_path = Path(entry.get("path", ".")).expanduser()
        res = retry_then_log(
            lambda e=entry: skill_fn(e),
            project=name,
            skill=entry.get("_skill_name", "cron"),
            project_path=project_path,
            projects_yaml=path,
            retry_delay_s=retry_delay_s,
            sleep=sleep,
            incidents_dir=incidents_dir,
        )
        report.results.append(res)
    return report


__all__ = [
    "SkillFailure", "SkillResult", "DispatchReport",
    "retry_then_log", "dispatch",
    "mark_stale", "unstale", "is_stale",
    "notifier",
]
