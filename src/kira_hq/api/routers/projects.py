"""GET /projects, GET /projects/{name}/tasks, POST /projects/{name}/tasks."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/projects", tags=["projects"])


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    priority: str = Field("medium", pattern="^(high|medium|low)$")
    parent_id: Optional[str] = None


class ProjectSummary(BaseModel):
    name: str
    path: str
    status: str
    priority: str
    tasks_summary: Dict[str, int]


def _summarize(tasks: List[dict]) -> Dict[str, int]:
    """Per-status counter + total."""
    counts = Counter(str(t.get("status", "unknown")) for t in tasks)
    counts["total"] = len(tasks)
    return dict(counts)


def _find_entry(projects: List[dict], name: str) -> dict:
    for p in projects:
        if p.get("name") == name:
            return p
    raise HTTPException(status_code=404, detail=f"project {name!r} not found")


@router.get("", response_model=List[ProjectSummary])
def list_projects(request: Request) -> List[ProjectSummary]:
    doc = request.app.state.projects_loader()
    out: List[ProjectSummary] = []
    runner = request.app.state.taskmaster_runner
    for p in doc.get("projects", []):
        path = Path(p["path"]).expanduser()
        tasks = runner(path)
        out.append(
            ProjectSummary(
                name=p["name"],
                path=str(path),
                status=p.get("status", "active"),
                priority=p.get("priority", "medium"),
                tasks_summary=_summarize(tasks),
            )
        )
    return out


@router.get("/{name}/tasks")
def list_tasks(
    name: str,
    request: Request,
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
) -> List[Dict[str, Any]]:
    doc = request.app.state.projects_loader()
    entry = _find_entry(doc.get("projects", []), name)
    path = Path(entry["path"]).expanduser()
    tasks = request.app.state.taskmaster_runner(path)
    if status:
        tasks = [t for t in tasks if str(t.get("status")) == status]
    if priority:
        tasks = [t for t in tasks if str(t.get("priority")) == priority]
    return tasks


@router.post("/{name}/tasks", status_code=201)
def add_task(
    name: str,
    payload: TaskCreate,
    request: Request,
) -> Dict[str, Any]:
    doc = request.app.state.projects_loader()
    entry = _find_entry(doc.get("projects", []), name)
    path = Path(entry["path"]).expanduser()
    try:
        new = request.app.state.taskmaster_add_task(
            path,
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            parent_id=payload.parent_id,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail="project task store is missing") from e
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return new
