"""GET /views/needs-attention, GET /views/blockers — PRD §6.10 + §4."""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Request

router = APIRouter(prefix="/views", tags=["views"])


def _to_jsonable(obj: Any) -> Any:
    """Convert NeedsAttentionReport (dataclass) into plain dicts/lists."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(x) for x in obj]
    return obj


@router.get("/needs-attention")
def needs_attention(request: Request) -> Dict[str, Any]:
    """Run T-9 needs_attention.compute over current projects.yaml.

    `compute` reads projects.yaml from disk itself (via `kira_hq.projects_yaml.load`)
    so we pass the loader's source path, not a pre-parsed dict. To keep the
    test seam intact we expose the path through a helper attribute on
    `app.state.projects_loader` (set by make_app's defaults), falling back
    to the production default.
    """
    from datetime import datetime, timezone

    runner = request.app.state.taskmaster_runner
    compute = request.app.state.needs_attention_compute

    def _tasks_loader(project_path):
        return runner(Path(project_path))

    yaml_path = getattr(
        request.app.state, "projects_yaml_path", None
    )
    if yaml_path is None:
        from kira_hq.api.app import DEFAULT_PROJECTS_YAML
        yaml_path = DEFAULT_PROJECTS_YAML

    report = compute(
        datetime.now(timezone.utc),
        yaml_path,
        request.app.state.pipeline_log_loader(),
        metrics_dir=request.app.state.tokens_dir_loader(),
        tasks_loader=_tasks_loader,
    )
    return _to_jsonable(report)


@router.get("/blockers")
def blockers(request: Request) -> List[Dict[str, Any]]:
    """Flatten all `status: blocked` tasks across every active project."""
    doc = request.app.state.projects_loader()
    runner = request.app.state.taskmaster_runner
    out: List[Dict[str, Any]] = []
    for p in doc.get("projects", []):
        if p.get("status") == "archived":
            continue
        path = Path(p["path"]).expanduser()
        try:
            tasks = runner(path)
        except Exception:
            continue
        for t in tasks:
            if str(t.get("status")) == "blocked":
                out.append({
                    "project": p["name"],
                    "id": str(t.get("id")),
                    "title": t.get("title"),
                    "priority": t.get("priority"),
                    "dependencies": t.get("dependencies", []),
                })
    return out
