"""Smoke test: installed SDK versions match versions.lock.md — PRD §6.4.

Parses the pinned-versions table in docs/versions.lock.md and asserts
each declared package is installed at exactly the pinned version.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.smoke

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_LOCK = REPO_ROOT / "docs" / "versions.lock.md"

# Map declared package name → how to probe the installed version
#   "cli":      run `<cmd> --version`, first version-looking token wins
#   "bundled":  Node require('<pkg>/package.json').version from inside
#              task-master-ai's bundle (where the SDK actually lives)
PROBES = {
    "task-master-ai": {"kind": "cli", "cmd": ["task-master", "--version"]},
    "@anthropic-ai/claude-agent-sdk": {
        "kind": "bundled",
        "host_pkg": "task-master-ai",
        "sub_pkg": "@anthropic-ai/claude-agent-sdk",
    },
}

SEMVER_RE = re.compile(r"\b\d+\.\d+\.\d+[\w.+-]*\b")


def _parse_lock_table(text: str) -> dict[str, str]:
    """Return {package_name: pinned_version} from the markdown table."""
    pins: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        pkg, ver = cells[0], cells[1]
        if pkg in ("package", "") or set(pkg) <= set("- "):
            continue
        if not SEMVER_RE.search(ver) and not ver.endswith("x"):
            continue
        pins[pkg] = ver
    return pins


def _probe_cli(cmd: list[str]) -> str:
    out = subprocess.run(
        cmd, check=True, capture_output=True, text=True,
        env={**os.environ, "CLAUDECODE": "", "ANTHROPIC_API_KEY": ""},
        timeout=30,
    ).stdout.strip()
    m = SEMVER_RE.search(out)
    if not m:
        raise AssertionError(f"no semver in `{' '.join(cmd)}` output: {out!r}")
    return m.group(0)


def _probe_bundled(host_pkg: str, sub_pkg: str) -> str:
    """Find <host>/node_modules/<sub>/package.json and read .version."""
    host_path = shutil.which(host_pkg) or shutil.which(host_pkg.replace("-ai", ""))
    # Resolve the host package's install root via node
    node_script = (
        "const p = require.resolve("
        f'"{host_pkg}/package.json", '
        "{ paths: ["
        '"/opt/homebrew/lib/node_modules",'
        '"/usr/local/lib/node_modules",'
        'require("os").homedir()+"/.nvm/versions/node"'
        "] }); "
        f'const sub = require(require("path").dirname(p)+"/node_modules/{sub_pkg}/package.json"); '
        "process.stdout.write(sub.version);"
    )
    try:
        ver = subprocess.run(
            ["node", "-e", node_script],
            check=True, capture_output=True, text=True, timeout=30,
        ).stdout.strip()
    except subprocess.CalledProcessError as e:
        # Fallback: glob the known homebrew path
        candidates = list(Path("/opt/homebrew/lib/node_modules").glob(
            f"{host_pkg}/node_modules/{sub_pkg}/package.json"
        ))
        if not candidates:
            raise AssertionError(
                f"cannot locate bundled {sub_pkg} under {host_pkg}: {e.stderr}"
            ) from e
        ver = json.loads(candidates[0].read_text())["version"]
    m = SEMVER_RE.search(ver)
    assert m, f"no semver in bundled version string {ver!r}"
    return m.group(0)


def _matches(pinned: str, installed: str) -> bool:
    """Allow wildcard minor like `0.43.x` or exact match."""
    if pinned.endswith(".x"):
        prefix = pinned[:-1]  # e.g. "0.43."
        return installed.startswith(prefix)
    return pinned == installed


@pytest.fixture(scope="module")
def pins() -> dict[str, str]:
    assert VERSIONS_LOCK.exists(), f"missing {VERSIONS_LOCK}"
    parsed = _parse_lock_table(VERSIONS_LOCK.read_text())
    assert parsed, "no pinned packages parsed from versions.lock.md"
    return parsed


def test_versions_lock_lists_all_expected_packages(pins):
    for expected in PROBES:
        assert expected in pins, (
            f"{expected} missing from versions.lock.md — every PROBES key "
            f"must be declared in the lock table"
        )


@pytest.mark.parametrize("pkg", list(PROBES.keys()))
def test_installed_version_matches_pin(pins, pkg):
    if pkg not in pins:
        pytest.fail(f"{pkg} not declared in versions.lock.md")

    probe = PROBES[pkg]
    if probe["kind"] == "cli":
        if shutil.which(probe["cmd"][0]) is None:
            pytest.skip(f"{probe['cmd'][0]} not on PATH in this env")
        installed = _probe_cli(probe["cmd"])
    elif probe["kind"] == "bundled":
        # Skip if the host package isn't installed in this env (e.g. ci.yml
        # doesn't ship task-master-ai; only nightly.yml does). Probe the host
        # via node's module resolver before attempting the bundled lookup.
        host = probe["host_pkg"]
        host_check = subprocess.run(
            ["node", "-e",
             f'try {{ require.resolve("{host}/package.json", {{ paths: ['
             '"/opt/homebrew/lib/node_modules",'
             '"/usr/local/lib/node_modules",'
             'require("os").homedir()+"/.nvm/versions/node"'
             f'] }}); }} catch (e) {{ process.exit(2); }}'],
            capture_output=True, text=True, timeout=15,
        )
        if host_check.returncode != 0 and shutil.which(host.replace("-ai", "")) is None:
            pytest.skip(f"{host} not installed in this env (CI without nightly toolchain)")
        installed = _probe_bundled(probe["host_pkg"], probe["sub_pkg"])
    else:
        pytest.fail(f"unknown probe kind for {pkg}")

    pinned = pins[pkg]
    assert _matches(pinned, installed), (
        f"{pkg}: installed {installed!r} does not match pin {pinned!r} "
        f"(update docs/versions.lock.md after verifying new version)"
    )
