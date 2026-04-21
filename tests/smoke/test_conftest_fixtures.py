"""Smoke: shared conftest fixtures behave as advertised — PRD §6.15."""
from __future__ import annotations

import json

import pytest
import yaml

pytestmark = pytest.mark.smoke


def test_fake_project_writes_tasks_json(fake_project):
    fp = fake_project("demo", tasks_n=10)
    assert fp.tasks_json.exists()
    data = json.loads(fp.tasks_json.read_text())
    tasks = data["master"]["tasks"]
    assert len(tasks) == 10
    assert tasks[0]["id"] == "1"
    assert (fp.path / "prd" / "master-prd.md").exists()


def test_fake_project_custom_size(fake_project):
    fp = fake_project("big", tasks_n=3)
    assert fp.tasks_n == 3
    tasks = json.loads(fp.tasks_json.read_text())["master"]["tasks"]
    assert len(tasks) == 3


def test_pipeline_log_tmp_writes_10col_row(pipeline_log_tmp):
    pipeline_log_tmp.append(project="kira-hq", skill="render", provider="sonnet")
    content = pipeline_log_tmp.path.read_text()
    # Header columns per PRD §6.1 / §6.19
    for col in ("timestamp", "project", "skill", "provider", "expand_used",
                "tokens_in", "tokens_out", "status", "duration_s", "notes"):
        assert col in content
    assert "sonnet" in content and "kira-hq" in content


def test_projects_yaml_tmp_v2_structure(projects_yaml_tmp):
    p = projects_yaml_tmp(entries=2)
    doc = yaml.safe_load(p.read_text())
    assert doc["version"] == 2
    assert len(doc["projects"]) == 2
    e = doc["projects"][0]
    for key in ("name", "path", "status", "priority", "cron", "added_at",
                "skills", "budget_tokens_monthly", "budget_tokens_per_run"):
        assert key in e
