"""Task 27 Stage 1 handoff parsing and validation."""
from __future__ import annotations

import json
import re
import textwrap
from pathlib import PurePosixPath
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, field_validator


LANE_LABEL_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class HandoffFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    intent: str

    @field_validator("path", "intent")
    @classmethod
    def trim_required_strings(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value must not be empty")
        return trimmed

    @field_validator("path")
    @classmethod
    def normalize_path(cls, value: str) -> str:
        normalized = str(PurePosixPath(value.replace("\\", "/")))
        if normalized == ".":
            raise ValueError("path must not be empty")
        return normalized


class HandoffDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    step: int
    worker: str
    worktree: str
    lane: str
    files: list[HandoffFile]
    tests: list[str]
    risks: list[str]
    artifacts: list[str]
    next: str
    status: str

    @field_validator("task_id", "worker", "worktree", "lane", "next", "status")
    @classmethod
    def trim_scalar_strings(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("value must not be empty")
        return trimmed

    @field_validator("tests", "risks", "artifacts")
    @classmethod
    def trim_string_lists(cls, values: list[str]) -> list[str]:
        trimmed = [value.strip() for value in values]
        if any(not value for value in trimmed):
            raise ValueError("list values must not be empty")
        return trimmed

    @field_validator("lane")
    @classmethod
    def validate_lane_label(cls, value: str) -> str:
        if not LANE_LABEL_RE.fullmatch(value):
            raise ValueError("lane must be a simple label")
        return value

    @field_validator("artifacts")
    @classmethod
    def validate_artifact_paths(cls, values: list[str], info: Any) -> list[str]:
        task_id = info.data.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("task_id must be set before artifacts")

        expected_root = (".hermes", "artifacts", task_id)
        validated: list[str] = []
        for value in values:
            path = PurePosixPath(value.replace("\\", "/"))
            parts = path.parts
            if path.is_absolute() or any(part in {"..", "."} for part in parts[1:]):
                raise ValueError("artifact path must stay within the task artifact root")
            if len(parts) < 4 or parts[:3] != expected_root:
                raise ValueError("artifact path must be under .hermes/artifacts/<task_id>/")
            validated.append(str(path))

        return validated


def _extract_front_matter(raw: str) -> tuple[str, str] | None:
    text = raw.lstrip()
    if not text.startswith("---"):
        return None

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    raise ValueError("handoff markdown front matter is malformed")


def _load_raw_document(raw: str) -> Any:
    text = textwrap.dedent(raw).strip()
    if not text:
        raise ValueError("handoff payload is empty")

    front_matter = _extract_front_matter(text)
    if front_matter is not None:
        front_matter_text, trailing_body = front_matter
        if trailing_body.strip():
            raise ValueError("handoff markdown front matter must not include free-form body content")
        text = textwrap.dedent(front_matter_text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        data = yaml.safe_load(text)
        if data is None:
            raise ValueError("handoff payload is empty")
        return data


def parse_handoff(raw: str) -> HandoffDocument:
    """Parse Stage 1 handoff payload from JSON, YAML, or markdown front matter."""
    data = _load_raw_document(raw)
    if not isinstance(data, dict):
        raise ValueError("handoff payload must be a mapping")
    return HandoffDocument.model_validate(data)
