"""Integration tests for HTTPBasic auth gate — T-17, PRD §4/§6.12.

Verifies the full matrix:
  - KIRA_HQ_EXPOSED off → no auth required, 200 everywhere
  - Flag on + valid creds → 200
  - Flag on + no creds → 401 with WWW-Authenticate: Basic
  - Flag on + bad password → 401
  - Flag on + bad username (same-length) → 401 (constant-time check)
  - Flag on + creds missing in .env → 503 fail-loud
  - /health stays open regardless of flag
"""
from __future__ import annotations

import base64
from typing import Dict

import pytest
from fastapi.testclient import TestClient

from kira_hq.api.app import make_app

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Shared fake loaders: no real disk, no real task-master
# ---------------------------------------------------------------------------

_FAKE_DOC = {
    "version": 2,
    "projects": [{
        "name": "alpha", "path": "/tmp/alpha-noop", "status": "active",
        "priority": "high", "cron": "0 */2 * * *",
        "added_at": "2026-04-19",
        "skills": ["kira-hq-render-kanban"],
        "budget_tokens_monthly": 500_000,
        "budget_tokens_per_run": 50_000,
        "notes": "",
    }],
}


def _noop_runner(_path):
    return []


def _basic_header(user: str, password: str) -> Dict[str, str]:
    raw = f"{user}:{password}".encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}


# ---------------------------------------------------------------------------
# Test matrix
# ---------------------------------------------------------------------------

def _build(exposed: bool, *, user: str = "mariusz", password: str = "topsecret"):
    secrets = {}
    if user is not None:
        secrets["KIRA_HQ_USER"] = user
    if password is not None:
        secrets["KIRA_HQ_PASS"] = password
    app = make_app(
        projects_loader=lambda: _FAKE_DOC,
        taskmaster_runner=_noop_runner,
        auth_secrets_loader=lambda: dict(secrets),
        auth_exposed_probe=lambda: exposed,
    )
    return TestClient(app)


def test_localhost_mode_no_auth_required():
    """KIRA_HQ_EXPOSED off → every endpoint reachable without creds."""
    client = _build(exposed=False)
    for path in [
        "/projects",
        "/views/blockers",
        "/metrics/tokens",
        "/metrics/pipeline",
    ]:
        r = client.get(path)
        assert r.status_code == 200, f"{path} → {r.status_code} in localhost mode"


def test_health_open_regardless_of_flag():
    for exposed in (False, True):
        client = _build(exposed=exposed)
        r = client.get("/health")
        assert r.status_code == 200, f"/health blocked with exposed={exposed}"


def test_exposed_with_valid_creds_allows():
    client = _build(exposed=True, user="mariusz", password="topsecret")
    r = client.get("/projects", headers=_basic_header("mariusz", "topsecret"))
    assert r.status_code == 200


def test_exposed_without_creds_returns_401():
    client = _build(exposed=True)
    r = client.get("/projects")
    assert r.status_code == 401
    assert r.headers.get("WWW-Authenticate", "").lower().startswith("basic")


def test_exposed_with_bad_password_returns_401():
    client = _build(exposed=True, user="mariusz", password="topsecret")
    r = client.get("/projects", headers=_basic_header("mariusz", "wrong"))
    assert r.status_code == 401


def test_exposed_with_bad_username_returns_401():
    """Username mismatch MUST also 401, not 200. Regression for off-by-one
    in `hmac.compare_digest` on unequal-length strings."""
    client = _build(exposed=True, user="mariusz", password="topsecret")
    r = client.get("/projects", headers=_basic_header("root", "topsecret"))
    assert r.status_code == 401


def test_exposed_constant_time_compare_on_same_length_wrong_user():
    """Same-length username that differs should still 401."""
    client = _build(exposed=True, user="mariusz", password="topsecret")
    r = client.get("/projects", headers=_basic_header("hackerx", "topsecret"))
    assert r.status_code == 401


def test_exposed_missing_credentials_in_env_returns_503():
    """Fail-loud: flag on but creds absent → 503 not 200."""
    client = _build(exposed=True, user="", password="")
    r = client.get("/projects", headers=_basic_header("anyone", "anything"))
    assert r.status_code == 503
    assert "KIRA_HQ_EXPOSED" in r.text


def test_exposed_health_still_open_with_missing_creds():
    """/health must not leak 503 due to broken config — liveness stays green."""
    client = _build(exposed=True, user="", password="")
    r = client.get("/health")
    assert r.status_code == 200


def test_auth_uses_hmac_compare_digest():
    """Smoke: implementation imports hmac.compare_digest (module inspection)."""
    import inspect
    from kira_hq.api import auth
    src = inspect.getsource(auth)
    assert "hmac.compare_digest" in src, \
        "auth.py must use hmac.compare_digest for constant-time compare"


def test_is_exposed_reads_env_live(monkeypatch):
    """Regression: is_exposed() must not cache — tests flip the flag."""
    from kira_hq.api.auth import is_exposed

    monkeypatch.delenv("KIRA_HQ_EXPOSED", raising=False)
    assert is_exposed() is False

    for truthy in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("KIRA_HQ_EXPOSED", truthy)
        assert is_exposed() is True, f"{truthy!r} should be truthy"

    for falsy in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("KIRA_HQ_EXPOSED", falsy)
        assert is_exposed() is False, f"{falsy!r} should be falsy"
