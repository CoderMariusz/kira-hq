"""Smoke tests for Module 2 FastAPI endpoints — PRD §4 Module 2.

Uses TestClient (httpx-based) + the make_app(...) dependency-injection
seams so no real disk / subprocess is touched. Each endpoint asserts:
  - 200 (or 201/422 where appropriate)
  - expected JSON keys / shape
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from kira_hq.api.app import default_taskmaster_add_task, make_app

pytestmark = pytest.mark.smoke


# ---------------------------------------------------------------------------
# Fixture: app with fake projects + fake tasks
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_yaml(tmp_path) -> Path:
    """Write a v2 projects.yaml with 2 entries and matching tasks.json files."""
    import yaml

    projects = []
    for name, status in [("alpha", "active"), ("beta", "active")]:
        proot = tmp_path / name
        (proot / ".taskmaster" / "tasks").mkdir(parents=True)
        tasks = [
            {"id": "1", "title": "T1", "description": "d", "priority": "high",
             "status": "pending", "dependencies": []},
            {"id": "2", "title": "T2", "description": "d", "priority": "low",
             "status": "blocked", "dependencies": ["1"]},
            {"id": "3", "title": "T3", "description": "d", "priority": "medium",
             "status": "done", "dependencies": []},
        ]
        (proot / ".taskmaster" / "tasks" / "tasks.json").write_text(
            json.dumps({"master": {"tasks": tasks}})
        )
        projects.append({
            "name": name, "path": str(proot), "status": status,
            "priority": "high", "cron": "0 */2 * * *",
            "added_at": "2026-04-19",
            "skills": ["kira-hq-render-kanban"],
            "budget_tokens_monthly": 500_000,
            "budget_tokens_per_run": 50_000,
            "notes": "",
        })
    yaml_path = tmp_path / "projects.yaml"
    yaml_path.write_text(yaml.safe_dump({"version": 2, "projects": projects}))
    return yaml_path


def _runner_for(yaml_path: Path):
    """Build a fake task-master runner that reads tasks.json directly."""
    def _run(project_path: Path) -> List[dict]:
        f = Path(project_path) / ".taskmaster" / "tasks" / "tasks.json"
        if not f.exists():
            return []
        return json.loads(f.read_text())["master"]["tasks"]
    return _run


@pytest.fixture
def client(fake_yaml, tmp_path) -> TestClient:
    import yaml
    doc = yaml.safe_load(fake_yaml.read_text())

    pipeline_log = tmp_path / "pipeline.log.md"
    pipeline_log.write_text(
        "| timestamp | project | skill | provider | expand_used | tokens_in | tokens_out | status | duration_s | notes |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
        "| 2026-04-19T08:00:00 | alpha | k1 | sonnet | false | 100 | 50 | ok | 1.0 |  |\n"
        "| 2026-04-19T08:01:00 | beta  | k1 | sonnet | false | 200 | 80 | ok | 2.0 |  |\n"
    )

    app = make_app(
        projects_loader=lambda: doc,
        projects_yaml_path=fake_yaml,
        taskmaster_runner=_runner_for(fake_yaml),
        pipeline_log_loader=lambda: pipeline_log,
        tokens_dir_loader=lambda: tmp_path / "metrics",
    )
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_get_projects(client):
    r = client.get("/projects")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    names = {p["name"] for p in data}
    assert names == {"alpha", "beta"}
    for p in data:
        assert {"name", "path", "status", "priority", "tasks_summary"} <= set(p)
        # 3 tasks per project: 1 pending + 1 blocked + 1 done
        assert p["tasks_summary"]["total"] == 3
        assert p["tasks_summary"]["pending"] == 1
        assert p["tasks_summary"]["blocked"] == 1
        assert p["tasks_summary"]["done"] == 1


def test_get_project_tasks_no_filter(client):
    r = client.get("/projects/alpha/tasks")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_get_project_tasks_status_filter(client):
    r = client.get("/projects/alpha/tasks?status=blocked")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["status"] == "blocked"


def test_get_project_tasks_priority_filter(client):
    r = client.get("/projects/alpha/tasks?priority=high")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["priority"] == "high"


def test_get_project_tasks_unknown_project(client):
    r = client.get("/projects/nonesuch/tasks")
    assert r.status_code == 404


def test_post_project_tasks(client, fake_yaml):
    payload = {
        "title": "New from API",
        "description": "smoke test",
        "priority": "high",
    }
    r = client.post("/projects/alpha/tasks", json=payload)
    assert r.status_code == 201, r.text
    new = r.json()
    assert new["title"] == "New from API"
    assert new["priority"] == "high"
    assert new["status"] == "pending"
    # Round-trip: GET tasks must include it
    r2 = client.get("/projects/alpha/tasks?status=pending")
    titles = [t["title"] for t in r2.json()]
    assert "New from API" in titles


def test_post_project_tasks_invalid_priority(client):
    r = client.post(
        "/projects/alpha/tasks",
        json={"title": "x", "priority": "URGENT"},
    )
    assert r.status_code == 422


def test_get_views_blockers(client):
    r = client.get("/views/blockers")
    assert r.status_code == 200
    data = r.json()
    # Each project has exactly one blocked task
    assert len(data) == 2
    for entry in data:
        assert {"project", "id", "title", "priority", "dependencies"} <= set(entry)


def test_get_views_needs_attention(client):
    r = client.get("/views/needs-attention")
    assert r.status_code == 200
    body = r.json()
    # Shape from NeedsAttentionReport dataclass
    assert "generated_at" in body
    assert "blocked" in body
    assert "stale_high" in body or "high_prio_stale" in body
    assert "needs_human" in body
    assert "failed_crons" in body
    assert "budgets" in body or "budget_exceeded" in body


def test_get_metrics_tokens(client):
    r = client.get("/metrics/tokens?since=2026-04-19")
    assert r.status_code == 200
    body = r.json()
    assert body["since"] == "2026-04-19"
    assert "alpha" in body["projects"]
    assert body["projects"]["alpha"]["tokens_in"] == 100
    assert body["projects"]["beta"]["tokens_out"] == 80


def test_get_metrics_tokens_invalid_since(client):
    r = client.get("/metrics/tokens?since=not-a-date")
    assert r.status_code == 422


def test_get_metrics_pipeline(client):
    r = client.get("/metrics/pipeline?since=2026-04-19T00:00:00")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    assert rows[0]["project"] == "alpha"
    assert rows[1]["project"] == "beta"
    assert rows[0]["tokens_in"] == 100


def test_get_metrics_pipeline_filters_old(client):
    r = client.get("/metrics/pipeline?since=2026-05-01T00:00:00")
    assert r.status_code == 200
    assert r.json() == []


def test_post_project_tasks_sanitizes_missing_store_path(tmp_path):
    app = make_app(
        projects_loader=lambda: {
            "projects": [{"name": "alpha", "path": str(tmp_path / "alpha"), "status": "active", "priority": "high"}]
        },
        taskmaster_add_task=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            FileNotFoundError(f"tasks.json missing at {tmp_path / 'alpha' / '.taskmaster' / 'tasks' / 'tasks.json'}")
        ),
    )
    client = TestClient(app)

    r = client.post("/projects/alpha/tasks", json={"title": "x", "priority": "high"})

    assert r.status_code == 409
    assert str(tmp_path) not in r.text


def test_list_projects_does_not_swallow_unexpected_runner_errors(tmp_path):
    app = make_app(
        projects_loader=lambda: {
            "projects": [{"name": "alpha", "path": str(tmp_path / "alpha"), "status": "active", "priority": "high"}]
        },
        taskmaster_runner=lambda _path: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/projects")

    assert r.status_code == 500


def test_blockers_does_not_swallow_unexpected_runner_errors(tmp_path):
    app = make_app(
        projects_loader=lambda: {
            "projects": [{"name": "alpha", "path": str(tmp_path / "alpha"), "status": "active", "priority": "high"}]
        },
        taskmaster_runner=lambda _path: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get("/views/blockers")

    assert r.status_code == 500


def test_default_taskmaster_add_task_discovers_non_master_tag(tmp_path):
    project_path = tmp_path / "alpha"
    tasks_dir = project_path / ".taskmaster" / "tasks"
    tasks_dir.mkdir(parents=True)
    tasks_file = tasks_dir / "tasks.json"
    tasks_file.write_text(json.dumps({"release": {"tasks": []}}))

    created = default_taskmaster_add_task(
        project_path,
        title="Ship it",
        description="",
        priority="high",
    )

    data = json.loads(tasks_file.read_text())
    assert created["id"] == "1"
    assert data["release"]["tasks"][0]["title"] == "Ship it"


def test_default_taskmaster_add_task_supports_top_level_tasks_schema(tmp_path):
    project_path = tmp_path / "alpha"
    tasks_dir = project_path / ".taskmaster" / "tasks"
    tasks_dir.mkdir(parents=True)
    tasks_file = tasks_dir / "tasks.json"
    tasks_file.write_text(json.dumps({"tasks": []}))

    created = default_taskmaster_add_task(
        project_path,
        title="Ship top-level",
        description="",
        priority="high",
    )

    data = json.loads(tasks_file.read_text())
    assert created["id"] == "1"
    assert data["tasks"][0]["title"] == "Ship top-level"


def test_default_taskmaster_add_task_is_lock_safe(tmp_path):
    project_path = tmp_path / "alpha"
    tasks_dir = project_path / ".taskmaster" / "tasks"
    tasks_dir.mkdir(parents=True)
    tasks_file = tasks_dir / "tasks.json"
    tasks_file.write_text(json.dumps({"master": {"tasks": []}}))

    def _create(i: int) -> str:
        return default_taskmaster_add_task(
            project_path,
            title=f"task-{i}",
            description="",
            priority="medium",
        )["id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = sorted(pool.map(_create, range(12)), key=int)

    data = json.loads(tasks_file.read_text())
    assert ids == [str(i) for i in range(1, 13)]
    assert [task["id"] for task in data["master"]["tasks"]] == ids
