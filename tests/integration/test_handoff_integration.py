"""Integration tests for Stage 1 handoff parser and contract enforcement."""
from __future__ import annotations

import importlib
import json

import pytest

pytestmark = pytest.mark.integration


def _parse_handoff(raw: str):
    module = importlib.import_module("kira_hq.handoff")
    parse_handoff = getattr(module, "parse_handoff")
    return parse_handoff(raw)


def _as_dict(document):
    return document.model_dump() if hasattr(document, "model_dump") else document


def _valid_payload(**overrides):
    payload = {
        "task_id": "28",
        "step": 1,
        "worker": "red",
        "worktree": "/tmp/kira-hq-task-28",
        "lane": "default",
        "files": [{"path": "tests/integration/test_handoff_integration.py", "intent": "modify"}],
        "tests": ["pytest tests/integration/test_handoff_integration.py -q"],
        "risks": ["validator gaps"],
        "artifacts": [".hermes/artifacts/28/red-handoff.log"],
        "next": "controller_review",
        "status": "completed",
    }
    payload.update(overrides)
    return payload


def test_parse_handoff_accepts_json_and_normalizes_scalars():
    payload = {
        "task_id": "28",
        "step": "1",
        "worker": "  red  ",
        "worktree": "  /tmp/kira-hq-task-28  ",
        "lane": "  default  ",
        "files": [{"path": " tests/smoke/test_handoff.py ", "intent": "create"}],
        "tests": [" pytest tests/smoke/test_handoff.py -q "],
        "risks": [" schema drift "],
        "artifacts": [" .hermes/artifacts/28/handoff.md "],
        "next": " controller_review ",
        "status": " completed ",
    }

    parsed = _as_dict(_parse_handoff(json.dumps(payload)))

    assert parsed["step"] == 1
    assert parsed["worker"] == "red"
    assert parsed["worktree"] == "/tmp/kira-hq-task-28"
    assert parsed["lane"] == "default"
    assert parsed["files"][0]["path"] == "tests/smoke/test_handoff.py"
    assert parsed["tests"] == ["pytest tests/smoke/test_handoff.py -q"]
    assert parsed["risks"] == ["schema drift"]
    assert parsed["artifacts"] == [".hermes/artifacts/28/handoff.md"]
    assert parsed["next"] == "controller_review"
    assert parsed["status"] == "completed"


def test_parse_handoff_accepts_yaml():
    raw = """
    task_id: "28"
    step: 1
    worker: red
    worktree: /tmp/kira-hq-task-28
    lane: default
    files:
      - path: tests/integration/test_handoff_integration.py
        intent: create
    tests:
      - pytest tests/integration/test_handoff_integration.py -q
    risks:
      - schema drift
    artifacts:
      - .hermes/artifacts/28/handoff.md
    next: controller_review
    status: completed
    """

    parsed = _as_dict(_parse_handoff(raw))

    assert parsed["task_id"] == "28"
    assert parsed["files"][0]["path"] == "tests/integration/test_handoff_integration.py"
    assert parsed["status"] == "completed"


def test_parse_handoff_accepts_markdown_front_matter():
    raw = """
    ---
    task_id: "28"
    step: 1
    worker: red
    worktree: /tmp/kira-hq-task-28
    lane: default
    files:
      - path: tests/smoke/test_handoff.py
        intent: create
    tests:
      - pytest tests/smoke/test_handoff.py -q
    risks:
      - schema drift
    artifacts:
      - .hermes/artifacts/28/handoff.md
    next: controller_review
    status: completed
    ---
    """

    parsed = _as_dict(_parse_handoff(raw))

    assert parsed["task_id"] == "28"
    assert parsed["step"] == 1
    assert parsed["status"] == "completed"


@pytest.mark.parametrize("missing_key", ["task_id", "lane", "next", "status"])
def test_parse_handoff_rejects_missing_required_top_level_keys(missing_key: str):
    payload = _valid_payload()
    payload.pop(missing_key)

    with pytest.raises(Exception):
        _parse_handoff(json.dumps(payload))


def test_parse_handoff_rejects_missing_required_nested_file_key():
    payload = _valid_payload(files=[{"path": "tests/integration/test_handoff_integration.py"}])

    with pytest.raises(Exception):
        _parse_handoff(json.dumps(payload))


@pytest.mark.parametrize(
    "artifact_path",
    [
        "handoff.md",
        "/tmp/handoff.md",
        "artifacts/28/handoff.md",
        ".hermes/artifacts/99/handoff.md",
    ],
)
def test_parse_handoff_rejects_artifacts_outside_task_root(artifact_path: str):
    payload = _valid_payload(artifacts=[artifact_path])

    with pytest.raises(Exception):
        _parse_handoff(json.dumps(payload))


@pytest.mark.parametrize("lane", ["feature/red", "lane with spaces", "../escape"])
def test_parse_handoff_rejects_invalid_lane_metadata(lane: str):
    payload = _valid_payload(lane=lane)

    with pytest.raises(Exception):
        _parse_handoff(json.dumps(payload))


def test_parse_handoff_rejects_markdown_front_matter_with_freeform_summary_body():
    raw = """
    ---
    task_id: "28"
    step: 1
    worker: red
    worktree: /tmp/kira-hq-task-28
    lane: default
    files:
      - path: tests/integration/test_handoff_integration.py
        intent: modify
    tests:
      - pytest tests/integration/test_handoff_integration.py -q
    risks:
      - validator gaps
    artifacts:
      - .hermes/artifacts/28/red-handoff.log
    next: controller_review
    status: completed
    ---

    Summary: parser worked and tests were added.
    Details: this free-form body should make Stage 1 fail closed.
    """

    with pytest.raises(Exception):
        _parse_handoff(raw)
