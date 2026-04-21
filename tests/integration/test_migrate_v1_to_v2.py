"""Integration: migration script on real v1 yaml → v2, idempotent."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "migrate_projects_yaml.py"
SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kira_hq.projects_yaml import detect_version, load  # noqa: E402


V1_SAMPLE = {
    "version": 1,
    "global": {
        "cron_default": "0 */1 * * *",
        "fallback_provider": "openrouter",
    },
    "projects": [
        {
            "name": "kira-hq",
            "path": "~/Projects/kira-hq",
            "stack": "python-nextjs",
            "status": "active",
            "priority": "high",
            "night_crew_cron": "0 */2 * * *",
        },
    ],
}


def _run_script(path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_migrate_v1_to_v2_full_cycle(tmp_path):
    p = tmp_path / "projects.yaml"
    p.write_text(yaml.safe_dump(V1_SAMPLE, sort_keys=False))
    assert detect_version(p) == 1

    result = _run_script(p)
    assert result.returncode == 0, result.stderr
    assert (p.parent / "projects.yaml.v1.bak").exists()

    # Re-validates as v2
    doc = load(p)
    assert doc.version == 2
    assert len(doc.projects) == 1
    assert doc.projects[0].name == "kira-hq"
    # night_crew_cron migrated to cron
    assert doc.projects[0].cron == "0 */2 * * *"
    # Defaults filled
    assert doc.projects[0].budget_tokens_monthly == 500000
    assert doc.projects[0].skills == ["kira-hq-render-kanban"]


def test_migrate_is_idempotent(tmp_path):
    p = tmp_path / "projects.yaml"
    p.write_text(yaml.safe_dump(V1_SAMPLE, sort_keys=False))

    result1 = _run_script(p)
    assert result1.returncode == 0
    first_content = p.read_text()

    result2 = _run_script(p)
    assert result2.returncode == 0
    assert "Already v2" in result2.stdout
    assert p.read_text() == first_content


def test_check_flag_does_not_modify(tmp_path):
    p = tmp_path / "projects.yaml"
    original = yaml.safe_dump(V1_SAMPLE, sort_keys=False)
    p.write_text(original)

    result = _run_script(p, "--check")
    assert result.returncode == 0
    assert "v1 detected" in result.stdout
    assert p.read_text() == original
    assert not (p.parent / "projects.yaml.v1.bak").exists()
