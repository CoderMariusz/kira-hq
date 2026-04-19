"""Integration test: spin up real uvicorn on 127.0.0.1:3100, hit endpoints.

Uses the real `~/.kira-hq/projects.yaml` if present (skip otherwise).
Spawns uvicorn in a subprocess, waits for /health to be ready, exercises
each endpoint via httpx, then terminates. The point is to catch wiring
bugs that TestClient hides — actual ASGI server, real socket binding,
real subprocess for `task-master list --json`.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.integration

PROJECTS_YAML = Path.home() / ".kira-hq" / "projects.yaml"
PORT = 3100  # PRD §4 Module 2 — verified free
HOST = "127.0.0.1"


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((HOST, port)) != 0


@pytest.fixture(scope="module")
def server():
    if not PROJECTS_YAML.exists():
        pytest.skip("real ~/.kira-hq/projects.yaml missing — integration N/A")
    if not _port_free(PORT):
        pytest.skip(f"port {PORT} occupied — skipping (Module 2 dev server already up?)")

    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    # Strip the 4 trigger vars in the spawned uvicorn (PRD §6.4)
    for var in ("CLAUDECODE", "CLAUDE_CODE_ENTRYPOINT",
                "CLAUDE_CODE_EXECPATH", "ANTHROPIC_API_KEY"):
        env.pop(var, None)

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn",
         "kira_hq.api.app:app",
         "--host", HOST, "--port", str(PORT),
         "--log-level", "warning"],
        env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )

    # Wait up to 15s for /health to come up
    deadline = time.monotonic() + 15
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read() if proc.stdout else ""
            pytest.fail(f"uvicorn exited early (rc={proc.returncode}): {out[-500:]}")
        try:
            r = httpx.get(f"http://{HOST}:{PORT}/health", timeout=1.0)
            if r.status_code == 200:
                break
        except Exception as e:
            last_err = e
        time.sleep(0.2)
    else:
        proc.terminate()
        pytest.fail(f"uvicorn did not become ready in 15s; last={last_err}")

    yield f"http://{HOST}:{PORT}"

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def test_health_real(server):
    r = httpx.get(f"{server}/health", timeout=5)
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_projects_real(server):
    r = httpx.get(f"{server}/projects", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # If user has projects, they MUST have name + tasks_summary
    for p in data:
        assert "name" in p
        assert "tasks_summary" in p
        assert "total" in p["tasks_summary"]


def test_views_blockers_real(server):
    r = httpx.get(f"{server}/views/blockers", timeout=15)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_views_needs_attention_real(server):
    r = httpx.get(f"{server}/views/needs-attention", timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert "generated_at" in body


def test_metrics_pipeline_real(server):
    r = httpx.get(f"{server}/metrics/pipeline", timeout=10)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_metrics_tokens_real(server):
    r = httpx.get(f"{server}/metrics/tokens", timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "projects" in body
    assert isinstance(body["projects"], dict)
