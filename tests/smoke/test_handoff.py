"""Smoke tests for Task 27 handoff schema contract."""
from __future__ import annotations

import importlib
import json

import pytest

pytestmark = pytest.mark.smoke


REQUIRED_FIELDS = {
    "task_id",
    "step",
    "worker",
    "worktree",
    "lane",
    "files",
    "tests",
    "risks",
    "artifacts",
    "next",
    "status",
}


def _parse_handoff(raw: str):
    module = importlib.import_module("kira_hq.handoff")
    parse_handoff = getattr(module, "parse_handoff")
    return parse_handoff(raw)


def _as_dict(document):
    return document.model_dump() if hasattr(document, "model_dump") else document


def test_parse_handoff_validates_required_stage1_fields():
    payload = {
        "task_id": "27",
        "step": 1,
        "worker": "red",
        "worktree": "/tmp/kira-hq-task-27",
        "lane": "task-27",
        "files": [
            {"path": "tests/smoke/test_handoff.py", "intent": "create"},
            {"path": "tests/integration/test_handoff_integration.py", "intent": "create"},
        ],
        "tests": [
            "pytest tests/smoke/test_handoff.py -q",
            "pytest tests/integration/test_handoff_integration.py -q",
        ],
        "risks": ["schema drift"],
        "artifacts": [".hermes/artifacts/27/handoff.md"],
        "next": "Implement handoff parsing and validation.",
        "status": "ready",
    }

    parsed = _as_dict(_parse_handoff(json.dumps(payload)))

    assert REQUIRED_FIELDS <= set(parsed)
    assert parsed["task_id"] == "27"
    assert parsed["step"] == 1
    assert parsed["files"][0]["path"] == "tests/smoke/test_handoff.py"
    assert parsed["tests"][0].startswith("pytest ")
    assert parsed["status"] == "ready"


def test_parse_handoff_rejects_missing_required_field():
    payload = {
        "task_id": "27",
        "step": 1,
        "worker": "red",
        "worktree": "/tmp/kira-hq-task-27",
        "lane": "task-27",
        "files": [],
        "tests": [],
        "risks": [],
        "artifacts": [],
        "next": "Implement handoff parsing and validation.",
    }

    with pytest.raises(Exception):
        _parse_handoff(json.dumps(payload))


def test_parse_handoff_rejects_undeclared_extra_fields():
    payload = {
        "task_id": "27",
        "step": 1,
        "worker": "red",
        "worktree": "/tmp/kira-hq-task-27",
        "lane": "task-27",
        "files": [
            {
                "path": "tests/smoke/test_handoff.py",
                "intent": "create",
                "unexpected": "value",
            }
        ],
        "tests": ["pytest tests/smoke/test_handoff.py -q"],
        "risks": ["schema drift"],
        "artifacts": [".hermes/artifacts/27/handoff.md"],
        "next": "Implement handoff parsing and validation.",
        "status": "ready",
        "unexpected": "value",
    }

    with pytest.raises(Exception):
        _parse_handoff(json.dumps(payload))



def test_parse_handoff_rejects_unterminated_markdown_front_matter():
    payload = """---
task_id: \"27\"
step: 1
worker: red
worktree: /tmp/kira-hq-task-27
lane: task-27
files:
  - path: tests/smoke/test_handoff.py
    intent: create
tests:
  - pytest tests/smoke/test_handoff.py -q
risks:
  - schema drift
artifacts:
  - .hermes/artifacts/27/handoff.md
next: Implement handoff parsing and validation.
status: ready
"""

    with pytest.raises(ValueError, match="front matter is malformed"):
        _parse_handoff(payload)
