"""Integration: cron retry + incidents + stale + /unstale — PRD §6.3."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kira_hq.cron_handler import (
    SkillFailure,
    dispatch,
    is_stale,
    mark_stale,
    notifier,
    retry_then_log,
    unstale,
)
from kira_hq.incidents import list_recent

pytestmark = pytest.mark.integration


@pytest.fixture
def yaml_path(tmp_path):
    p = tmp_path / "projects.yaml"
    p.write_text(yaml.safe_dump({
        "version": 2,
        "projects": [{
            "name": "kira-hq", "path": str(tmp_path), "status": "active",
            "priority": "high", "cron": "0 */2 * * *",
            "added_at": "2026-04-18",
            "skills": ["kira-hq-render-kanban"],
            "budget_tokens_monthly": 500_000,
            "budget_tokens_per_run": 50_000,
        }],
    }))
    return p


@pytest.fixture
def incidents_dir(tmp_path):
    d = tmp_path / "incidents"
    d.mkdir()
    return d


@pytest.fixture(autouse=True)
def _reset_notifier():
    notifier.alerts.clear()
    yield
    notifier.alerts.clear()


# --- Policy clause 1: retry once on failure -------------------------------

def test_retry_succeeds_on_second_attempt(tmp_path, yaml_path, incidents_dir,
                                          monkeypatch):
    monkeypatch.setattr("kira_hq.pipeline_log.GLOBAL_LOG",
                        tmp_path / "gpl.md")

    calls = {"n": 0}
    slept: list[float] = []

    def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise SkillFailure("transient", stderr="boom")
        # second call succeeds

    res = retry_then_log(
        flaky, project="kira-hq", skill="test-skill",
        project_path=tmp_path, projects_yaml=yaml_path,
        retry_delay_s=60.0, sleep=slept.append,
        incidents_dir=incidents_dir,
    )
    assert res.status == "ok"
    assert res.attempts == 2
    assert slept == [60.0]         # slept between attempt 1 and 2
    assert not is_stale("kira-hq", yaml_path)   # still active
    assert list(incidents_dir.iterdir()) == []  # no incident on recovery
    assert notifier.alerts == []                # no alert either


# --- Clauses 2 + 3 + 4: second failure writes incident, alerts, stales ----

def test_double_failure_writes_incident_alerts_and_stales(
    tmp_path, yaml_path, incidents_dir, monkeypatch,
):
    monkeypatch.setattr("kira_hq.pipeline_log.GLOBAL_LOG",
                        tmp_path / "gpl.md")

    def always_fail():
        raise SkillFailure("permanent", stderr="full stderr",
                           stdout="a\nb\nc\n")

    res = retry_then_log(
        always_fail, project="kira-hq", skill="render",
        project_path=tmp_path, projects_yaml=yaml_path,
        retry_delay_s=0.0, sleep=lambda s: None,
        incidents_dir=incidents_dir,
    )
    assert res.status == "fail"
    assert res.attempts == 2

    # Incident written
    files = list(incidents_dir.iterdir())
    assert len(files) == 1
    body = files[0].read_text()
    assert "permanent" in body
    assert "full stderr" in body
    assert "## Stdout (last 50 lines)" in body
    assert res.incident is not None
    assert res.incident.path == files[0]

    # Pipeline log row status=fail
    gpl = (tmp_path / "gpl.md").read_text()
    assert "| fail |" in gpl
    assert "incident=" in gpl

    # Project marked stale
    assert is_stale("kira-hq", yaml_path)

    # Alert emitted
    assert len(notifier.alerts) == 1
    assert "failed twice" in notifier.alerts[0]


# --- Clause 5: stale projects skipped by dispatcher ------------------------

def test_dispatch_skips_stale_projects(tmp_path, yaml_path, incidents_dir,
                                       monkeypatch):
    monkeypatch.setattr("kira_hq.pipeline_log.GLOBAL_LOG",
                        tmp_path / "gpl.md")
    mark_stale("kira-hq", yaml_path)
    assert is_stale("kira-hq", yaml_path)

    called = {"n": 0}
    def skill(entry):
        called["n"] += 1

    report = dispatch(
        skill, projects_yaml=yaml_path,
        retry_delay_s=0.0, sleep=lambda s: None,
        incidents_dir=incidents_dir,
    )
    assert called["n"] == 0
    assert report.n_skipped == 1
    assert report.n_ok == 0
    assert report.results[0].status == "skip-stale"


# --- /unstale round-trip --------------------------------------------------

def test_unstale_reactivates_project(yaml_path):
    mark_stale("kira-hq", yaml_path)
    assert is_stale("kira-hq", yaml_path)
    assert unstale("kira-hq", yaml_path) is True
    assert not is_stale("kira-hq", yaml_path)
    # No-op if already active
    assert unstale("kira-hq", yaml_path) is False


def test_unstale_unknown_project_returns_false(yaml_path):
    assert unstale("ghost", yaml_path) is False


# --- Full dispatch happy path ---------------------------------------------

def test_dispatch_happy_path_writes_ok_row(tmp_path, yaml_path, incidents_dir,
                                           monkeypatch):
    monkeypatch.setattr("kira_hq.pipeline_log.GLOBAL_LOG",
                        tmp_path / "gpl.md")

    def skill(entry):
        assert entry["name"] == "kira-hq"

    report = dispatch(
        skill, projects_yaml=yaml_path,
        retry_delay_s=0.0, sleep=lambda s: None,
        incidents_dir=incidents_dir,
    )
    assert report.n_ok == 1
    assert report.n_fail == 0
    gpl = (tmp_path / "gpl.md").read_text()
    assert "| ok |" in gpl
    assert not is_stale("kira-hq", yaml_path)


def test_incident_list_recent_returns_fresh(tmp_path, incidents_dir):
    from kira_hq.incidents import write_incident
    write_incident(
        project="p", skill="s", error="boom",
        incidents_dir=incidents_dir,
    )
    recent = list_recent(since_hours=1, incidents_dir=incidents_dir)
    assert len(recent) == 1
