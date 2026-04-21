# Kira-HQ v2.0 Implementation Plan

> I'm using the `writing-plans` skill to create this implementation plan.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Kira-HQ v2.0 — a local-first project manager for 10–15 AI-driven projects — covering Module 1 (markdown renderer production-hardening), Module 2 (FastAPI backend), Module 3 (Next.js dashboard), Module 4 (Hermes integration skills), plus all 18 cross-cutting concerns from PRD §6.

**Architecture:** Three layers. Projects own `.taskmaster/tasks.json` as source of truth. Kira-HQ reads via `task-master list --json` subprocess and renders markdown (Module 1) or serves REST (Module 2). Next.js frontend (Module 3) calls FastAPI on localhost:3100. Hermes (external orchestrator) invokes Kira-HQ skills from `~/.kira-hq/skills-shared/` (symlinks into `~/.hermes/skills/` and each project's `.claude/skills/`). Parallel track: Hermes cron AND Claude Code cron both run during Faza 2 evaluation.

**Tech Stack:**
- Python 3.12 + `uv` (renderer, CLI, scripts)
- FastAPI + `uvicorn` (backend) + `httpx` for test client
- Next.js 14 (App Router) + TypeScript + Tailwind (frontend)
- Playwright (E2E browser tests)
- `pytest` + `pytest-asyncio` (Python tests)
- `task-master-ai` CLI (source of task JSON)
- `rsync` + `launchctl`/cron (snapshots, scheduling)
- GitHub Actions (CI)

**File structure (top-level):**

```
~/Projects/kira-hq/
├── src/kira_hq/
│   ├── __init__.py
│   ├── renderer/           # Module 1
│   │   ├── __init__.py
│   │   ├── kanban.py
│   │   ├── global_kanban.py
│   │   ├── needs_attention.py
│   │   ├── adr_index.py
│   │   └── pipeline_log.py
│   ├── api/                # Module 2
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── routes/
│   │   │   ├── projects.py
│   │   │   ├── tasks.py
│   │   │   ├── views.py
│   │   │   └── metrics.py
│   │   ├── auth.py
│   │   └── taskmaster_client.py
│   ├── cli/                # kira-hq add-project etc.
│   │   ├── __init__.py
│   │   ├── add_project.py
│   │   └── archive_project.py
│   ├── config/
│   │   ├── projects_yaml.py
│   │   └── env.py
│   ├── tokens/
│   │   └── aggregate.py
│   ├── incidents/
│   │   └── writer.py
│   └── retry.py
├── frontend/               # Module 3 (Next.js)
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── projects/[name]/page.tsx
│   │   ├── needs-attention/page.tsx
│   │   └── blockers/page.tsx
│   ├── components/
│   │   ├── TaskCard.tsx
│   │   ├── KanbanColumn.tsx
│   │   └── HermesFrame.tsx
│   ├── lib/api.ts
│   ├── package.json
│   └── next.config.js
├── scripts/
│   ├── migrate_projects_yaml.py
│   ├── snapshot.sh
│   ├── restore_snapshot.sh
│   └── render_adr_index.py
├── tests/
│   ├── smoke/
│   ├── integration/
│   ├── e2e/                # Playwright
│   └── test_taskmaster_workaround.sh
├── docs/
│   ├── SECRETS.md
│   ├── PARALLEL_TRACK.md
│   ├── POSTMAN.json
│   └── ADR/
│       ├── 0001-use-fastapi-not-flask.md
│       └── 0002-orchestrator-decision.md   # filled after parallel track
├── versions.lock.md
├── README.md
└── pyproject.toml

~/.kira-hq/
├── projects.yaml              # v2 schema
├── global-kanban.md
├── global-pipeline.log.md
├── global-adrs.md
├── needs-attention.md
├── .env                       # chmod 600, gitignored
├── templates/ADR.md
├── snapshots/YYYY-MM-DD/
├── metrics/tokens-YYYY-MM-DD.json
├── reviews/YYYY-WW.md
├── incidents/<ts>-<project>.md
└── skills-shared/             # own git repo
    ├── .git/
    ├── README.md
    ├── kira-hq-render-kanban/SKILL.md
    ├── kira-hq-report/SKILL.md
    ├── kira-weekly-review/SKILL.md
    └── kira-add-project/SKILL.md
```

---

## Phase A — Module 1: Renderer production hardening (PRD §4.M1, §6.1, §6.3, §6.4, §6.7, §6.8, §6.10)

### Task 1: Pin SDK versions + smoke-test the taskmaster workaround (PRD §6.4)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/versions.lock.md`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/test_taskmaster_workaround.sh`

- [ ] **Step 1: Capture current versions**

Run: `task-master --version && npm ls -g @anthropic-ai/claude-agent-sdk`
Expected: prints two version strings.

- [ ] **Step 2: Create `versions.lock.md`**

```markdown
# Kira-HQ Pinned Versions (last-known-good)

| Tool                               | Version | Verified date | Source                                   |
|------------------------------------|---------|---------------|------------------------------------------|
| task-master-ai                     | <paste output from step 1>  | 2026-04-16 | `npm -g ls`                              |
| @anthropic-ai/claude-agent-sdk     | <paste output from step 1>  | 2026-04-16 | `npm -g ls`                              |
| Python                             | 3.12.x  | 2026-04-16    | `python3 --version`                      |
| Node                               | 22.x    | 2026-04-16    | `node --version`                         |

## Known-bad

- `claude-agent-sdk` when invoked in a nested Claude session throws `RangeError`.
  Workaround: wrapper in `~/.zshrc` that strips `CLAUDECODE=1` before invoking `task-master`.

## Upgrade policy

- Never bump without re-running `tests/test_taskmaster_workaround.sh` on the new version.
- If smoke fails after bump, revert and open ADR.
```

Replace `<paste output from step 1>` with actual captured versions.

- [ ] **Step 3: Write the workaround smoke test**

Create `/Users/mariuszkrawczyk/Projects/kira-hq/tests/test_taskmaster_workaround.sh`:

```bash
#!/usr/bin/env bash
# Smoke test: confirm the CLAUDECODE-stripping wrapper in ~/.zshrc is active
# and that running `task-master list` from inside a simulated nested Claude
# session exits 0 via the wrapper.
set -euo pipefail

FIXTURE_DIR="$(mktemp -d)"
trap 'rm -rf "$FIXTURE_DIR"' EXIT

cd "$FIXTURE_DIR"
task-master init --yes >/dev/null

# Case A: with wrapper (sourced zshrc) — must succeed
CLAUDECODE=1 zsh -i -c 'task-master list --json' >/dev/null
echo "PASS: wrapper allows task-master under CLAUDECODE=1"

# Case B: without wrapper (bare bash) — must fail, proving wrapper is required
if CLAUDECODE=1 bash -c 'task-master list --json' >/dev/null 2>&1; then
  echo "FAIL: task-master succeeded without wrapper — wrapper may be unnecessary or test is invalid"
  exit 1
fi
echo "PASS: bare run crashes as expected (wrapper is necessary)"
```

- [ ] **Step 4: Make executable and run**

Run:
```bash
chmod +x /Users/mariuszkrawczyk/Projects/kira-hq/tests/test_taskmaster_workaround.sh
/Users/mariuszkrawczyk/Projects/kira-hq/tests/test_taskmaster_workaround.sh
```
Expected output:
```
PASS: wrapper allows task-master under CLAUDECODE=1
PASS: bare run crashes as expected (wrapper is necessary)
```

- [ ] **Step 5: Commit**

```bash
cd /Users/mariuszkrawczyk/Projects/kira-hq
git add versions.lock.md tests/test_taskmaster_workaround.sh
git commit -m "feat(6.4): pin SDK versions + taskmaster workaround smoke test"
```

---

### Task 2: projects.yaml v2 loader with migration from v1 (PRD §6.6)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/config/projects_yaml.py`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/scripts/migrate_projects_yaml.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_projects_yaml.py`

- [ ] **Step 1: Write failing test for v2 loader**

```python
# tests/smoke/test_projects_yaml.py
from pathlib import Path
import textwrap
import pytest
from kira_hq.config.projects_yaml import load_projects, Project

def test_loads_v2_schema(tmp_path: Path):
    f = tmp_path / "projects.yaml"
    f.write_text(textwrap.dedent("""
        version: 2
        projects:
          - name: kira-hq
            path: ~/Projects/kira-hq
            status: active
            priority: high
            cron: "0 */2 * * *"
            added_at: 2026-04-16
            skills: [kira-hq-render-kanban]
            budget_tokens_monthly: 500000
            budget_tokens_per_run: 50000
            notes: "ref"
    """))
    projects = load_projects(f)
    assert len(projects) == 1
    p = projects[0]
    assert isinstance(p, Project)
    assert p.name == "kira-hq"
    assert p.status == "active"
    assert p.budget_tokens_monthly == 500_000
    assert p.skills == ["kira-hq-render-kanban"]

def test_rejects_unknown_status(tmp_path: Path):
    f = tmp_path / "projects.yaml"
    f.write_text("version: 2\nprojects:\n  - name: x\n    path: /tmp/x\n    status: bogus\n    priority: high\n    cron: '* * * * *'\n    added_at: 2026-04-16\n    skills: []\n    budget_tokens_monthly: 1\n    budget_tokens_per_run: 1\n")
    with pytest.raises(ValueError, match="status"):
        load_projects(f)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mariuszkrawczyk/Projects/kira-hq && uv run pytest tests/smoke/test_projects_yaml.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'kira_hq.config.projects_yaml'`.

- [ ] **Step 3: Implement loader**

Create `src/kira_hq/config/__init__.py` (empty) and `src/kira_hq/config/projects_yaml.py`:

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, List
import yaml
from datetime import date

Status = Literal["active", "stale", "archived"]
Priority = Literal["high", "medium", "low"]

@dataclass
class Project:
    name: str
    path: str
    status: Status
    priority: Priority
    cron: str
    added_at: date
    skills: List[str] = field(default_factory=list)
    budget_tokens_monthly: int = 0
    budget_tokens_per_run: int = 0
    notes: str = ""

_ALLOWED_STATUS = {"active", "stale", "archived"}
_ALLOWED_PRIORITY = {"high", "medium", "low"}

def load_projects(yaml_path: Path) -> List[Project]:
    data = yaml.safe_load(yaml_path.read_text())
    if data.get("version") != 2:
        raise ValueError(f"projects.yaml must be version 2, got {data.get('version')!r}. Run scripts/migrate_projects_yaml.py first.")
    out: List[Project] = []
    for entry in data.get("projects", []):
        if entry.get("status") not in _ALLOWED_STATUS:
            raise ValueError(f"invalid status: {entry.get('status')!r}")
        if entry.get("priority") not in _ALLOWED_PRIORITY:
            raise ValueError(f"invalid priority: {entry.get('priority')!r}")
        out.append(Project(
            name=entry["name"],
            path=entry["path"],
            status=entry["status"],
            priority=entry["priority"],
            cron=entry["cron"],
            added_at=entry["added_at"] if isinstance(entry["added_at"], date) else date.fromisoformat(entry["added_at"]),
            skills=list(entry.get("skills", [])),
            budget_tokens_monthly=int(entry.get("budget_tokens_monthly", 0)),
            budget_tokens_per_run=int(entry.get("budget_tokens_per_run", 0)),
            notes=entry.get("notes", ""),
        ))
    return out
```

- [ ] **Step 4: Re-run tests**

Run: `cd /Users/mariuszkrawczyk/Projects/kira-hq && uv run pytest tests/smoke/test_projects_yaml.py -v`
Expected: 2 passed.

- [ ] **Step 5: Write failing test for v1→v2 migration**

```python
# tests/smoke/test_migrate_projects_yaml.py
from pathlib import Path
import subprocess, sys, yaml, textwrap

def test_v1_to_v2(tmp_path: Path):
    src = tmp_path / "projects.yaml"
    src.write_text(textwrap.dedent("""
        projects:
          - name: kira-hq
            path: ~/Projects/kira-hq
    """))
    subprocess.run([sys.executable, "scripts/migrate_projects_yaml.py", str(src)], check=True, cwd="/Users/mariuszkrawczyk/Projects/kira-hq")
    got = yaml.safe_load(src.read_text())
    assert got["version"] == 2
    p = got["projects"][0]
    assert p["status"] == "active"
    assert p["priority"] == "medium"
    assert p["cron"] == "0 */2 * * *"
    assert p["skills"] == []
    assert p["budget_tokens_monthly"] == 500000
    assert p["budget_tokens_per_run"] == 50000
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/smoke/test_migrate_projects_yaml.py -v`
Expected: FAIL (script doesn't exist).

- [ ] **Step 7: Implement migration script**

Create `scripts/migrate_projects_yaml.py`:

```python
#!/usr/bin/env python3
"""Idempotent v1 -> v2 migration for projects.yaml."""
import sys, yaml
from datetime import date
from pathlib import Path

DEFAULTS = dict(
    status="active",
    priority="medium",
    cron="0 */2 * * *",
    skills=[],
    budget_tokens_monthly=500_000,
    budget_tokens_per_run=50_000,
    notes="",
)

def migrate(path: Path) -> None:
    data = yaml.safe_load(path.read_text()) or {}
    if data.get("version") == 2:
        print(f"{path}: already v2, no changes.")
        return
    for p in data.get("projects", []):
        for k, v in DEFAULTS.items():
            p.setdefault(k, v)
        p.setdefault("added_at", date.today().isoformat())
    data["version"] = 2
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    print(f"{path}: migrated to v2.")

if __name__ == "__main__":
    migrate(Path(sys.argv[1]))
```

- [ ] **Step 8: Re-run tests**

Run: `uv run pytest tests/smoke/test_migrate_projects_yaml.py tests/smoke/test_projects_yaml.py -v`
Expected: 3 passed.

- [ ] **Step 9: Commit**

```bash
git add src/kira_hq/config/ scripts/migrate_projects_yaml.py tests/smoke/test_projects_yaml.py tests/smoke/test_migrate_projects_yaml.py
git commit -m "feat(6.6): projects.yaml v2 loader + idempotent v1->v2 migration"
```

---

### Task 3: Pipeline log writer (PRD §6.1)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/renderer/pipeline_log.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_pipeline_log.py`

- [ ] **Step 1: Write failing test**

```python
# tests/smoke/test_pipeline_log.py
from pathlib import Path
from datetime import datetime, timezone
from kira_hq.renderer.pipeline_log import append_entry, PipelineEntry

def test_append_creates_header_if_missing(tmp_path: Path):
    log = tmp_path / "pipeline.log.md"
    e = PipelineEntry(
        timestamp=datetime(2026,4,17,3,0,12,tzinfo=timezone.utc),
        project="kira-hq", skill="kira-hq-render-kanban",
        tokens_in=0, tokens_out=0, status="ok", duration_s=1.2,
        notes="6 tasks rendered",
    )
    append_entry(log, e)
    text = log.read_text()
    assert "| timestamp" in text
    assert "| kira-hq " in text
    assert "6 tasks rendered" in text

def test_append_preserves_existing_rows(tmp_path: Path):
    log = tmp_path / "pipeline.log.md"
    e1 = PipelineEntry(datetime(2026,4,17,3,0,0,tzinfo=timezone.utc), "a","s1",0,0,"ok",1.0,"first")
    e2 = PipelineEntry(datetime(2026,4,17,3,1,0,tzinfo=timezone.utc), "b","s2",10,20,"fail",2.0,"second")
    append_entry(log, e1); append_entry(log, e2)
    text = log.read_text()
    assert text.count("| timestamp") == 1  # header once
    assert "first" in text and "second" in text
```

- [ ] **Step 2: Run test, confirm failure**

Run: `uv run pytest tests/smoke/test_pipeline_log.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# src/kira_hq/renderer/pipeline_log.py
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

Status = Literal["ok", "fail"]

HEADER = (
    "| timestamp           | project   | skill                  | tokens_in | tokens_out | status | duration_s | notes                |\n"
    "|---------------------|-----------|------------------------|-----------|------------|--------|------------|----------------------|\n"
)

@dataclass
class PipelineEntry:
    timestamp: datetime
    project: str
    skill: str
    tokens_in: int
    tokens_out: int
    status: Status
    duration_s: float
    notes: str = ""

def _row(e: PipelineEntry) -> str:
    ts = e.timestamp.strftime("%Y-%m-%dT%H:%M:%S")
    return f"| {ts} | {e.project:<9} | {e.skill:<22} | {e.tokens_in:>9} | {e.tokens_out:>10} | {e.status:<6} | {e.duration_s:>10.1f} | {e.notes:<20} |\n"

def append_entry(log_path: Path, entry: PipelineEntry) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if not log_path.exists() or log_path.stat().st_size == 0:
        log_path.write_text(HEADER)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(_row(entry))
```

- [ ] **Step 4: Verify passing**

Run: `uv run pytest tests/smoke/test_pipeline_log.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kira_hq/renderer/pipeline_log.py tests/smoke/test_pipeline_log.py
git commit -m "feat(6.1): append-only pipeline log writer with markdown-table schema"
```

---

### Task 4: Retry helper with 60s backoff + incident writer (PRD §6.3)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/retry.py`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/incidents/writer.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_retry.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_incident_writer.py`

- [ ] **Step 1: Write failing test for retry**

```python
# tests/smoke/test_retry.py
import time, pytest
from kira_hq.retry import retry_once

def test_succeeds_first_try():
    calls = []
    def fn():
        calls.append(1); return "ok"
    assert retry_once(fn, wait_s=0) == "ok"
    assert calls == [1]

def test_retries_then_succeeds():
    calls = []
    def fn():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return "ok2"
    assert retry_once(fn, wait_s=0) == "ok2"
    assert len(calls) == 2

def test_raises_after_second_failure():
    def fn(): raise RuntimeError("boom")
    with pytest.raises(RuntimeError, match="boom"):
        retry_once(fn, wait_s=0)
```

- [ ] **Step 2: Verify failure**

Run: `uv run pytest tests/smoke/test_retry.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement `retry.py`**

```python
# src/kira_hq/retry.py
import time
from typing import Callable, TypeVar
T = TypeVar("T")

def retry_once(fn: Callable[[], T], wait_s: float = 60.0) -> T:
    """Call fn; on Exception wait wait_s then call again; propagate on second failure."""
    try:
        return fn()
    except Exception:
        time.sleep(wait_s)
        return fn()
```

- [ ] **Step 4: Verify retry passes**

Run: `uv run pytest tests/smoke/test_retry.py -v`
Expected: 3 passed.

- [ ] **Step 5: Write failing test for incident writer**

```python
# tests/smoke/test_incident_writer.py
from pathlib import Path
from datetime import datetime, timezone
from kira_hq.incidents.writer import write_incident

def test_writes_incident_with_stderr_and_stdout_tail(tmp_path: Path):
    stdout = "\n".join(f"line{i}" for i in range(200))
    stderr = "Traceback ..."
    p = write_incident(
        incidents_dir=tmp_path,
        timestamp=datetime(2026,4,17,3,0,14,tzinfo=timezone.utc),
        project="monopilot", skill="monopilot-night-crew",
        stdout=stdout, stderr=stderr,
    )
    text = p.read_text()
    assert "monopilot" in text and "monopilot-night-crew" in text
    assert "Traceback" in text
    assert "line199" in text       # last line of stdout kept
    assert "line149" in text       # last 50 → 150..199
    assert "line100" not in text   # earlier lines dropped
```

- [ ] **Step 6: Verify failure**

Run: `uv run pytest tests/smoke/test_incident_writer.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 7: Implement incident writer**

```python
# src/kira_hq/incidents/__init__.py   (empty)
# src/kira_hq/incidents/writer.py
from pathlib import Path
from datetime import datetime

def write_incident(
    incidents_dir: Path,
    timestamp: datetime,
    project: str,
    skill: str,
    stdout: str,
    stderr: str,
) -> Path:
    incidents_dir.mkdir(parents=True, exist_ok=True)
    ts = timestamp.strftime("%Y-%m-%dT%H%M%S")
    path = incidents_dir / f"{ts}-{project}.md"
    tail = "\n".join(stdout.splitlines()[-50:])
    path.write_text(
        f"# Incident {ts}\n\n"
        f"- project: {project}\n- skill: {skill}\n- timestamp: {timestamp.isoformat()}\n\n"
        f"## stderr\n\n```\n{stderr}\n```\n\n"
        f"## stdout (last 50 lines)\n\n```\n{tail}\n```\n"
    )
    return path
```

- [ ] **Step 8: Verify passes**

Run: `uv run pytest tests/smoke/test_incident_writer.py -v`
Expected: 1 passed.

- [ ] **Step 9: Commit**

```bash
git add src/kira_hq/retry.py src/kira_hq/incidents/ tests/smoke/test_retry.py tests/smoke/test_incident_writer.py
git commit -m "feat(6.3): retry-once helper + incident file writer"
```

---

### Task 5: Telegram alert client (PRD §6.3, §6.4, §6.5)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/alerts/telegram.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_telegram.py`

- [ ] **Step 1: Write failing test using httpx MockTransport**

```python
# tests/smoke/test_telegram.py
import httpx, pytest
from kira_hq.alerts.telegram import TelegramClient

def test_send_posts_to_bot_api():
    calls = []
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"ok": True})
    transport = httpx.MockTransport(handler)
    client = TelegramClient(token="T", chat_ids=[111,222], transport=transport)
    client.send("hello")
    assert len(calls) == 2
    for r in calls:
        assert r.url.path == "/botT/sendMessage"
        assert "hello" in r.content.decode()

def test_send_raises_on_http_error():
    def handler(_): return httpx.Response(500, json={"ok": False})
    transport = httpx.MockTransport(handler)
    client = TelegramClient(token="T", chat_ids=[1], transport=transport)
    with pytest.raises(RuntimeError, match="Telegram"):
        client.send("x")
```

- [ ] **Step 2: Confirm failure**

Run: `uv run pytest tests/smoke/test_telegram.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# src/kira_hq/alerts/__init__.py   (empty)
# src/kira_hq/alerts/telegram.py
from dataclasses import dataclass
from typing import List, Optional
import httpx

@dataclass
class TelegramClient:
    token: str
    chat_ids: List[int]
    transport: Optional[httpx.BaseTransport] = None

    def send(self, text: str) -> None:
        with httpx.Client(base_url="https://api.telegram.org", transport=self.transport) as c:
            for chat in self.chat_ids:
                r = c.post(f"/bot{self.token}/sendMessage", json={"chat_id": chat, "text": text})
                if r.status_code != 200:
                    raise RuntimeError(f"Telegram send failed: {r.status_code} {r.text}")
```

- [ ] **Step 4: Verify passes**

Run: `uv run pytest tests/smoke/test_telegram.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kira_hq/alerts/ tests/smoke/test_telegram.py
git commit -m "feat(6.3): Telegram alert client with injectable httpx transport"
```

---

### Task 6: Orchestrator wrapper — combines retry + pipeline log + incident + stale-mark (PRD §6.3, §6.1)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/orchestrator.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/integration/test_orchestrator.py`

- [ ] **Step 1: Write failing integration test**

```python
# tests/integration/test_orchestrator.py
from pathlib import Path
from datetime import datetime, timezone
from kira_hq.orchestrator import run_skill

class FakeTelegram:
    def __init__(self): self.msgs = []
    def send(self, text): self.msgs.append(text)

def test_success_appends_ok_row_no_alert(tmp_path: Path):
    log = tmp_path / "pipeline.log.md"
    tg = FakeTelegram()
    def skill(): return (10, 20, "6 tasks rendered")
    res = run_skill(
        name="kira-hq-render-kanban", project="kira-hq",
        fn=skill, pipeline_log=log, incidents_dir=tmp_path/"inc",
        telegram=tg, now=lambda: datetime(2026,4,17,3,0,0,tzinfo=timezone.utc),
    )
    assert res.status == "ok"
    assert "ok" in log.read_text()
    assert tg.msgs == []

def test_two_failures_writes_incident_alerts_and_marks_stale(tmp_path: Path):
    log = tmp_path / "pipeline.log.md"
    tg = FakeTelegram()
    yaml = tmp_path / "projects.yaml"
    yaml.write_text("version: 2\nprojects:\n  - {name: kira-hq, path: /x, status: active, priority: high, cron: '* * * * *', added_at: 2026-04-16, skills: [], budget_tokens_monthly: 1, budget_tokens_per_run: 1}\n")
    def skill(): raise RuntimeError("boom")
    res = run_skill(
        name="kira-hq-render-kanban", project="kira-hq", fn=skill,
        pipeline_log=log, incidents_dir=tmp_path/"inc", telegram=tg,
        projects_yaml=yaml,
        now=lambda: datetime(2026,4,17,3,0,0,tzinfo=timezone.utc),
        retry_wait_s=0,
    )
    assert res.status == "fail"
    assert "fail" in log.read_text()
    assert any("boom" in p.read_text() for p in (tmp_path/"inc").iterdir())
    assert any("failed twice" in m for m in tg.msgs)
    assert "status: stale" in yaml.read_text()
```

- [ ] **Step 2: Confirm failure**

Run: `uv run pytest tests/integration/test_orchestrator.py -v`
Expected: FAIL `ModuleNotFoundError: kira_hq.orchestrator`.

- [ ] **Step 3: Implement `orchestrator.py`**

```python
# src/kira_hq/orchestrator.py
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Tuple
import time, yaml

from kira_hq.renderer.pipeline_log import append_entry, PipelineEntry
from kira_hq.incidents.writer import write_incident

SkillReturn = Tuple[int, int, str]  # tokens_in, tokens_out, notes

@dataclass
class RunResult:
    status: str
    duration_s: float
    incident_path: Optional[Path] = None

def _mark_stale(projects_yaml: Path, project: str) -> None:
    data = yaml.safe_load(projects_yaml.read_text())
    for p in data.get("projects", []):
        if p["name"] == project:
            p["status"] = "stale"
    projects_yaml.write_text(yaml.safe_dump(data, sort_keys=False))

def run_skill(
    *,
    name: str,
    project: str,
    fn: Callable[[], SkillReturn],
    pipeline_log: Path,
    incidents_dir: Path,
    telegram,
    projects_yaml: Optional[Path] = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    retry_wait_s: float = 60.0,
) -> RunResult:
    start = time.monotonic()
    try:
        try:
            tokens_in, tokens_out, notes = fn()
        except Exception:
            time.sleep(retry_wait_s)
            tokens_in, tokens_out, notes = fn()
        dur = time.monotonic() - start
        append_entry(pipeline_log, PipelineEntry(
            timestamp=now(), project=project, skill=name,
            tokens_in=tokens_in, tokens_out=tokens_out,
            status="ok", duration_s=dur, notes=notes,
        ))
        return RunResult(status="ok", duration_s=dur)
    except Exception as e:
        dur = time.monotonic() - start
        inc = write_incident(
            incidents_dir=incidents_dir, timestamp=now(),
            project=project, skill=name, stdout="", stderr=repr(e),
        )
        append_entry(pipeline_log, PipelineEntry(
            timestamp=now(), project=project, skill=name,
            tokens_in=0, tokens_out=0, status="fail",
            duration_s=dur, notes=f"incident={inc.name}",
        ))
        telegram.send(f"🔴 {project}/{name} failed twice. See incident {inc.name}.")
        if projects_yaml is not None:
            _mark_stale(projects_yaml, project)
        return RunResult(status="fail", duration_s=dur, incident_path=inc)
```

- [ ] **Step 4: Verify integration test passes**

Run: `uv run pytest tests/integration/test_orchestrator.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kira_hq/orchestrator.py tests/integration/test_orchestrator.py
git commit -m "feat(6.3): orchestrator wraps skill calls with retry+log+incident+stale"
```

---

### Task 7: needs-attention algorithm (PRD §6.10)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/renderer/needs_attention.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_needs_attention.py`

- [ ] **Step 1: Write failing test**

```python
# tests/smoke/test_needs_attention.py
from datetime import datetime, timedelta, timezone
from kira_hq.renderer.needs_attention import compute_needs_attention, Task, ProjectRuntime

NOW = datetime(2026,4,17,8,0,0,tzinfo=timezone.utc)

def t(id, status, priority, hours_ago, title="x", blocked_by=None):
    return Task(id=id, title=title, status=status, priority=priority,
                updated_at=NOW - timedelta(hours=hours_ago),
                blocked_by=blocked_by or [])

def test_blocked_gt_48h_triggers():
    tasks = [t("T-12","blocked","medium",67, title="Setup Stripe", blocked_by=["T-08"])]
    out = compute_needs_attention({"monopilot": ProjectRuntime(tasks=tasks, cron_failures_24h=0, tokens_30d=0, budget_monthly=1)}, now=NOW)
    assert "Blocked >48h (1)" in out
    assert "monopilot/T-12" in out
    assert "blocked by T-08" in out
    assert "67h" in out

def test_highprio_pending_gt_72h():
    tasks = [t("T-1","pending","high",80)]
    out = compute_needs_attention({"p": ProjectRuntime(tasks=tasks, cron_failures_24h=0, tokens_30d=0, budget_monthly=1)}, now=NOW)
    assert "High-prio stale >72h (1)" in out

def test_needs_human_status():
    tasks = [t("T-2","needs-human","medium",1)]
    out = compute_needs_attention({"p": ProjectRuntime(tasks=tasks, cron_failures_24h=0, tokens_30d=0, budget_monthly=1)}, now=NOW)
    assert "Needs-human" in out and "p/T-2" in out

def test_failed_crons_last_24h():
    out = compute_needs_attention({"p": ProjectRuntime(tasks=[], cron_failures_24h=1, tokens_30d=0, budget_monthly=1)}, now=NOW)
    assert "Failed crons (1)" in out

def test_budget_exceeded():
    out = compute_needs_attention({"p": ProjectRuntime(tasks=[], cron_failures_24h=0, tokens_30d=2_000_000, budget_monthly=1_000_000)}, now=NOW)
    assert "Budget exceeded" in out
```

- [ ] **Step 2: Run and verify failure**

Run: `uv run pytest tests/smoke/test_needs_attention.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# src/kira_hq/renderer/needs_attention.py
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List

@dataclass
class Task:
    id: str
    title: str
    status: str          # pending | in-progress | blocked | done | needs-human
    priority: str        # high | medium | low
    updated_at: datetime
    blocked_by: List[str] = field(default_factory=list)

@dataclass
class ProjectRuntime:
    tasks: List[Task]
    cron_failures_24h: int
    tokens_30d: int
    budget_monthly: int

def _hours(delta: timedelta) -> int:
    return int(delta.total_seconds() // 3600)

def compute_needs_attention(projects: Dict[str, ProjectRuntime], *, now: datetime) -> str:
    blocked, stale_high, needs_human, fails, budgets = [], [], [], [], []
    for name, rt in projects.items():
        for t in rt.tasks:
            age_h = _hours(now - t.updated_at)
            if t.status == "blocked" and age_h > 48:
                dep = ", ".join(t.blocked_by) or "—"
                blocked.append(f"- {name}/{t.id} \"{t.title}\" — blocked by {dep}, {age_h}h")
            if t.priority == "high" and t.status == "pending" and age_h > 72:
                stale_high.append(f"- {name}/{t.id} \"{t.title}\" — {age_h}h pending")
            if t.status == "needs-human":
                needs_human.append(f"- {name}/{t.id} \"{t.title}\"")
        if rt.cron_failures_24h > 0:
            fails.append(f"- {name} — {rt.cron_failures_24h} failure(s) in last 24h")
        if rt.budget_monthly > 0 and rt.tokens_30d > rt.budget_monthly:
            budgets.append(f"- {name} — {rt.tokens_30d} tokens / budget {rt.budget_monthly}")
    lines = [f"# Needs Attention — generated {now.isoformat()}", ""]
    lines += [f"## 🔴 Blocked >48h ({len(blocked)})", *blocked, ""]
    lines += [f"## 🟠 High-prio stale >72h ({len(stale_high)})", *stale_high, ""]
    lines += [f"## 🧑 Needs-human ({len(needs_human)})", *needs_human, ""]
    lines += [f"## 🚨 Failed crons ({len(fails)})", *fails, ""]
    lines += [f"## 💸 Budget exceeded ({len(budgets)})", *budgets, ""]
    return "\n".join(lines)
```

- [ ] **Step 4: Verify passes**

Run: `uv run pytest tests/smoke/test_needs_attention.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kira_hq/renderer/needs_attention.py tests/smoke/test_needs_attention.py
git commit -m "feat(6.10): needs-attention algorithm with 5 trigger rules"
```

---

### Task 8: ADR template + per-project index generator (PRD §6.8)

**Files:**
- Create: `/Users/mariuszkrawczyk/.kira-hq/templates/ADR.md` (already — just verify)
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/renderer/adr_index.py`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/scripts/render_adr_index.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_adr_index.py`

- [ ] **Step 1: Create ADR template**

Write `/Users/mariuszkrawczyk/.kira-hq/templates/ADR.md`:

```markdown
# ADR-NNNN: <kebab title>

- **Status:** proposed | accepted | superseded
- **Date:** YYYY-MM-DD

## Context

<What is the problem and the forces at play?>

## Decision

<What did we decide?>

## Consequences

<What becomes easier and harder?>
```

- [ ] **Step 2: Write failing test**

```python
# tests/smoke/test_adr_index.py
from pathlib import Path
from kira_hq.renderer.adr_index import render_project_index, render_global

def _adr(dir, num, title, status="accepted", date="2026-04-16"):
    p = dir / f"{num:04d}-{title}.md"
    p.write_text(f"# ADR-{num:04d}: {title}\n\n- **Status:** {status}\n- **Date:** {date}\n\n## Context\n\n## Decision\n")
    return p

def test_project_index_lists_all_and_orders_by_num(tmp_path: Path):
    _adr(tmp_path, 2, "orchestrator-decision")
    _adr(tmp_path, 1, "use-fastapi-not-flask")
    out = render_project_index(tmp_path)
    assert out.index("0001-") < out.index("0002-")
    assert "use-fastapi-not-flask" in out
    assert "orchestrator-decision" in out

def test_global_aggregates_across_projects(tmp_path: Path):
    pA = tmp_path / "A" / "docs" / "ADR"; pA.mkdir(parents=True)
    pB = tmp_path / "B" / "docs" / "ADR"; pB.mkdir(parents=True)
    _adr(pA, 1, "a1"); _adr(pB, 1, "b1")
    out = render_global({"A": pA, "B": pB})
    assert "## A" in out and "## B" in out
    assert "a1" in out and "b1" in out
```

- [ ] **Step 3: Verify failure**

Run: `uv run pytest tests/smoke/test_adr_index.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 4: Implement renderer**

```python
# src/kira_hq/renderer/adr_index.py
from pathlib import Path
from typing import Dict
import re

_STATUS_RE = re.compile(r"\*\*Status:\*\*\s*(\w+)")
_DATE_RE = re.compile(r"\*\*Date:\*\*\s*(\S+)")

def _entries(adr_dir: Path):
    items = []
    for f in sorted(adr_dir.glob("[0-9][0-9][0-9][0-9]-*.md")):
        txt = f.read_text()
        status = (_STATUS_RE.search(txt) or [None,"unknown"])[1] if _STATUS_RE.search(txt) else "unknown"
        date = (_DATE_RE.search(txt) or [None,"unknown"])[1] if _DATE_RE.search(txt) else "unknown"
        items.append((f.stem, status, date, f))
    return items

def render_project_index(adr_dir: Path) -> str:
    lines = ["# ADR Index", ""]
    for stem, status, date, f in _entries(adr_dir):
        lines.append(f"- [{stem}]({f.name}) — {status} — {date}")
    return "\n".join(lines) + "\n"

def render_global(project_adr_dirs: Dict[str, Path]) -> str:
    lines = ["# Global ADRs", ""]
    for name in sorted(project_adr_dirs):
        lines.append(f"## {name}")
        for stem, status, date, _ in _entries(project_adr_dirs[name]):
            lines.append(f"- {stem} — {status} — {date}")
        lines.append("")
    return "\n".join(lines)

def last_five(adr_dir: Path):
    return _entries(adr_dir)[-5:]
```

- [ ] **Step 5: Write CLI wrapper**

```python
# scripts/render_adr_index.py
#!/usr/bin/env python3
import sys
from pathlib import Path
from kira_hq.renderer.adr_index import render_project_index

if __name__ == "__main__":
    adr_dir = Path(sys.argv[1])
    (adr_dir / "INDEX.md").write_text(render_project_index(adr_dir))
    print(f"wrote {adr_dir/'INDEX.md'}")
```

- [ ] **Step 6: Verify tests pass**

Run: `uv run pytest tests/smoke/test_adr_index.py -v`
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add src/kira_hq/renderer/adr_index.py scripts/render_adr_index.py tests/smoke/test_adr_index.py
git commit -m "feat(6.8): ADR template + per-project and global index renderers"
```

---

### Task 9: Kanban renderer — include last 5 ADRs (PRD §4.M1, §6.8)

**Files:**
- Modify: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/renderer/kanban.py` (existing from Faza 1)
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/integration/test_kanban_with_adrs.py`

- [ ] **Step 1: Write failing integration test**

```python
# tests/integration/test_kanban_with_adrs.py
from pathlib import Path
import subprocess, json
from kira_hq.renderer.kanban import render_project_kanban

def _setup_fixture(root: Path):
    proj = root / "proj"; proj.mkdir()
    (proj / ".taskmaster").mkdir()
    tasks = {"tasks": [{"id":"1","title":"Do X","status":"pending","priority":"high","updated_at":"2026-04-17T00:00:00Z"}]}
    (proj / ".taskmaster" / "tasks.json").write_text(json.dumps(tasks))
    adr = proj / "docs" / "ADR"; adr.mkdir(parents=True)
    (adr / "0001-first.md").write_text("# ADR-0001: first\n- **Status:** accepted\n- **Date:** 2026-04-01\n")
    return proj

def test_kanban_includes_adr_section(tmp_path: Path):
    proj = _setup_fixture(tmp_path)
    md = render_project_kanban(proj, task_reader=lambda _: [{"id":"1","title":"Do X","status":"pending","priority":"high","updated_at":"2026-04-17T00:00:00Z"}])
    assert "## ADRs" in md
    assert "0001-first" in md
```

- [ ] **Step 2: Run to confirm failure**

Run: `uv run pytest tests/integration/test_kanban_with_adrs.py -v`
Expected: FAIL (either missing module or section `## ADRs` not present).

- [ ] **Step 3: Extend `kanban.py`**

Add to `src/kira_hq/renderer/kanban.py` (append / modify `render_project_kanban`):

```python
from pathlib import Path
from typing import Callable, List, Dict, Any
from kira_hq.renderer.adr_index import last_five

TaskReader = Callable[[Path], List[Dict[str, Any]]]

def _columns(tasks):
    cols = {"Needs-attention": [], "In-progress": [], "Pending": [], "Done": []}
    for t in tasks:
        s = t["status"]
        if s == "needs-human" or s == "blocked":
            cols["Needs-attention"].append(t)
        elif s == "in-progress":
            cols["In-progress"].append(t)
        elif s == "done":
            cols["Done"].append(t)
        else:
            cols["Pending"].append(t)
    return cols

def render_project_kanban(project_dir: Path, task_reader: TaskReader) -> str:
    tasks = task_reader(project_dir)
    cols = _columns(tasks)
    lines = [f"# Kanban — {project_dir.name}", ""]
    for col, items in cols.items():
        lines.append(f"## {col} ({len(items)})")
        for t in items:
            lines.append(f"- {t['id']} [{t['priority']}] {t['title']}")
        lines.append("")
    adr_dir = project_dir / "docs" / "ADR"
    lines.append("## ADRs")
    if adr_dir.exists():
        for stem, status, date, _ in last_five(adr_dir):
            lines.append(f"- {stem} — {status} — {date}")
    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Verify passes**

Run: `uv run pytest tests/integration/test_kanban_with_adrs.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kira_hq/renderer/kanban.py tests/integration/test_kanban_with_adrs.py
git commit -m "feat(4.M1,6.8): kanban renderer includes last-5 ADRs section"
```

---

### Task 10: E2E browser check for Module 1 (PRD §4.M1 DoD)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/e2e/test_module1_markdown_preview.py`

- [ ] **Step 1: Write Playwright test**

```python
# tests/e2e/test_module1_markdown_preview.py
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from kira_hq.renderer.kanban import render_project_kanban

def _fixture(tmp_path: Path, n: int):
    proj = tmp_path / "fx"; (proj / ".taskmaster").mkdir(parents=True)
    tasks = [{"id": f"T-{i}", "title": f"Task {i}", "status": "pending", "priority": "medium", "updated_at":"2026-04-17T00:00:00Z"} for i in range(n)]
    (proj / ".taskmaster" / "tasks.json").write_text(json.dumps({"tasks": tasks}))
    return proj, tasks

def test_preview_shows_same_count_as_tasks_json(tmp_path: Path):
    proj, tasks = _fixture(tmp_path, n=10)
    md = render_project_kanban(proj, task_reader=lambda _: tasks)
    html_path = tmp_path / "preview.html"
    # Minimal MD → HTML via markdown-it CDN:
    html_path.write_text(f"""<html><body><div id="src" style="display:none">{md}</div>
<script type="module">
  import markdownit from 'https://cdn.skypack.dev/markdown-it@13.0.1';
  const md = markdownit();
  document.body.insertAdjacentHTML('beforeend', md.render(document.getElementById('src').textContent));
</script></body></html>""")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file://{html_path}")
        page.wait_for_timeout(500)
        text = page.content()
        # 10 tasks → 10 "T-i" list entries visible in the rendered DOM
        for i in range(10):
            assert f"T-{i}" in text
        browser.close()
```

- [ ] **Step 2: Install Playwright browser once**

Run: `uv run playwright install chromium`
Expected: browser download succeeds.

- [ ] **Step 3: Run E2E test**

Run: `uv run pytest tests/e2e/test_module1_markdown_preview.py -v`
Expected: 1 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_module1_markdown_preview.py
git commit -m "test(4.M1): E2E markdown preview confirms task-count parity"
```

---

### Task 11: Module 1 README (PRD §4.M1 DoD, §6.17)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/renderer/README.md`

- [ ] **Step 1: Write README**

Create with this exact content:

```markdown
# Module 1 — Markdown Renderer

## Inputs
- `~/.kira-hq/projects.yaml` (v2 schema — see PRD §6.6)
- For each project: `<path>/.taskmaster/tasks.json` (read via `task-master list --json`)
- For each project: `<path>/docs/ADR/*.md` (optional)

## Outputs
- `<path>/kanban_board.md` per project
- `~/.kira-hq/global-kanban.md` (aggregate)
- `~/.kira-hq/needs-attention.md` (see PRD §6.10)
- `~/.kira-hq/global-adrs.md`
- Append to `<path>/pipeline.log.md` + `~/.kira-hq/global-pipeline.log.md`

## Error modes
- Missing `.taskmaster/` → project skipped, warning logged
- `task-master list` non-zero → retry once after 60s (see PRD §6.3); on second failure, incident + Telegram alert + stale-mark
- `projects.yaml` version ≠ 2 → hard error, run `scripts/migrate_projects_yaml.py`

## Running
```
uv run python -m kira_hq.renderer
```

## Tests
- Smoke: `uv run pytest tests/smoke/`
- Integration: `uv run pytest tests/integration/`
- E2E: `uv run pytest tests/e2e/test_module1_markdown_preview.py`
```

- [ ] **Step 2: Commit**

```bash
git add src/kira_hq/renderer/README.md
git commit -m "docs(4.M1): Module 1 README with inputs/outputs/error modes"
```

---

### Task 12: Backup snapshot script + rolling 7-day window (PRD §6.7)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/scripts/snapshot.sh`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/scripts/restore_snapshot.sh`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/integration/test_snapshot.sh`

- [ ] **Step 1: Write `snapshot.sh`**

```bash
#!/usr/bin/env bash
# Daily cron 03:00 — hardlink snapshot of every project's .taskmaster/
set -euo pipefail

ROOT="${KIRA_HQ_PROJECTS_ROOT:-$HOME/Projects}"
SNAP="${KIRA_HQ_SNAPSHOTS:-$HOME/.kira-hq/snapshots}"
TODAY="$(date +%F)"
mkdir -p "$SNAP"
YESTERDAY="$(ls -1 "$SNAP" | sort | tail -n 1 || true)"
DEST="$SNAP/$TODAY"
mkdir -p "$DEST"

for proj in "$ROOT"/*/; do
  name="$(basename "$proj")"
  [[ -d "$proj/.taskmaster" ]] || continue
  if [[ -n "${YESTERDAY:-}" && "$YESTERDAY" != "$TODAY" && -d "$SNAP/$YESTERDAY/$name" ]]; then
    rsync -a --link-dest="$SNAP/$YESTERDAY/$name/" "$proj/.taskmaster/" "$DEST/$name/"
  else
    rsync -a "$proj/.taskmaster/" "$DEST/$name/"
  fi
done

# Rolling 7-day window
cd "$SNAP"
ls -1 | sort | head -n -7 | while read -r old; do
  rm -rf "./$old"
done
echo "snapshot ok: $DEST"
```

- [ ] **Step 2: Write `restore_snapshot.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
PROJECT="${1:?usage: restore_snapshot.sh <project> <YYYY-MM-DD>}"
DATE="${2:?usage: restore_snapshot.sh <project> <YYYY-MM-DD>}"
SRC="$HOME/.kira-hq/snapshots/$DATE/$PROJECT"
DST="$HOME/Projects/$PROJECT/.taskmaster"
[[ -d "$SRC" ]] || { echo "no snapshot: $SRC"; exit 1; }

read -r -p "Overwrite $DST with $SRC? [y/N] " ans
[[ "$ans" == "y" || "$ans" == "Y" ]] || { echo "aborted"; exit 0; }
rsync -a --delete "$SRC/" "$DST/"
echo "restored"
```

- [ ] **Step 3: Write integration test**

```bash
#!/usr/bin/env bash
# tests/integration/test_snapshot.sh
set -euo pipefail
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/projects/p1/.taskmaster" "$TMP/projects/p2/.taskmaster"
echo '{"tasks":[]}' > "$TMP/projects/p1/.taskmaster/tasks.json"
echo '{"tasks":[]}' > "$TMP/projects/p2/.taskmaster/tasks.json"

KIRA_HQ_PROJECTS_ROOT="$TMP/projects" KIRA_HQ_SNAPSHOTS="$TMP/snaps" \
  bash /Users/mariuszkrawczyk/Projects/kira-hq/scripts/snapshot.sh

TODAY="$(date +%F)"
[[ -f "$TMP/snaps/$TODAY/p1/tasks.json" ]] || { echo "missing p1"; exit 1; }
[[ -f "$TMP/snaps/$TODAY/p2/tasks.json" ]] || { echo "missing p2"; exit 1; }
echo PASS
```

- [ ] **Step 4: Make executable and run**

```bash
chmod +x /Users/mariuszkrawczyk/Projects/kira-hq/scripts/snapshot.sh \
         /Users/mariuszkrawczyk/Projects/kira-hq/scripts/restore_snapshot.sh \
         /Users/mariuszkrawczyk/Projects/kira-hq/tests/integration/test_snapshot.sh
bash /Users/mariuszkrawczyk/Projects/kira-hq/tests/integration/test_snapshot.sh
```
Expected: `PASS`.

- [ ] **Step 5: Install daily cron via launchctl**

Create `~/Library/LaunchAgents/com.kirahq.snapshot.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.kirahq.snapshot</string>
  <key>ProgramArguments</key>
    <array>
      <string>/bin/bash</string>
      <string>/Users/mariuszkrawczyk/Projects/kira-hq/scripts/snapshot.sh</string>
    </array>
  <key>StartCalendarInterval</key>
    <dict><key>Hour</key><integer>3</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardOutPath</key><string>/tmp/kirahq-snapshot.log</string>
  <key>StandardErrorPath</key><string>/tmp/kirahq-snapshot.err</string>
</dict></plist>
```

Load:
```bash
launchctl load ~/Library/LaunchAgents/com.kirahq.snapshot.plist
```

- [ ] **Step 6: Commit**

```bash
git add scripts/snapshot.sh scripts/restore_snapshot.sh tests/integration/test_snapshot.sh
git commit -m "feat(6.7): daily hardlink snapshot + 7-day rolling window + restore"
```

---

## Phase B — Module 2: FastAPI Backend (PRD §4.M2)

### Task 13: Pyproject dependencies + FastAPI skeleton (PRD §4.M2)

**Files:**
- Modify: `/Users/mariuszkrawczyk/Projects/kira-hq/pyproject.toml`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/api/__init__.py`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/api/main.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_api_boot.py`

- [ ] **Step 1: Add dependencies**

Append to `[project.dependencies]`:
```toml
"fastapi>=0.115",
"uvicorn[standard]>=0.32",
"httpx>=0.27",
"pyyaml>=6",
"pytest>=8",
"pytest-asyncio>=0.23",
"playwright>=1.45",
```

Run `uv sync`.

- [ ] **Step 2: Write failing smoke test**

```python
# tests/smoke/test_api_boot.py
from fastapi.testclient import TestClient
from kira_hq.api.main import app

def test_health():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 3: Run to confirm failure**

Run: `uv run pytest tests/smoke/test_api_boot.py -v`
Expected: FAIL `ModuleNotFoundError: kira_hq.api`.

- [ ] **Step 4: Implement skeleton**

```python
# src/kira_hq/api/main.py
from fastapi import FastAPI

app = FastAPI(title="Kira-HQ", version="2.0")

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 5: Verify passes**

Run: `uv run pytest tests/smoke/test_api_boot.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/kira_hq/api/__init__.py src/kira_hq/api/main.py tests/smoke/test_api_boot.py
git commit -m "feat(4.M2): FastAPI skeleton with /health endpoint"
```

---

### Task 14: `taskmaster_client.py` — subprocess wrapper (PRD §4.M2, §6.4)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/api/taskmaster_client.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_taskmaster_client.py`

- [ ] **Step 1: Write failing test using fake subprocess**

```python
# tests/smoke/test_taskmaster_client.py
import json
from kira_hq.api.taskmaster_client import list_tasks, add_task

def test_list_tasks_parses_json(monkeypatch):
    payload = {"tasks": [{"id":"T-1","title":"x","status":"pending","priority":"high","updated_at":"2026-04-17T00:00:00Z"}]}
    class R: returncode=0; stdout=json.dumps(payload); stderr=""
    monkeypatch.setattr("subprocess.run", lambda *a, **k: R)
    tasks = list_tasks(project_path="/tmp/p")
    assert tasks[0]["id"] == "T-1"

def test_add_task_invokes_cli(monkeypatch):
    calls = {}
    class R: returncode=0; stdout='{"id":"T-9"}'; stderr=""
    def fake(cmd, **kw):
        calls["cmd"] = cmd; return R
    monkeypatch.setattr("subprocess.run", fake)
    out = add_task(project_path="/tmp/p", title="t", description="d", priority="high", parent_id=None)
    assert "task-master" in calls["cmd"][0] or "task-master" in calls["cmd"][1]
    assert "add-task" in calls["cmd"]
    assert out["id"] == "T-9"
```

- [ ] **Step 2: Confirm failure**

Run: `uv run pytest tests/smoke/test_taskmaster_client.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# src/kira_hq/api/taskmaster_client.py
import json, subprocess, shlex
from typing import List, Dict, Any, Optional

def list_tasks(project_path: str) -> List[Dict[str, Any]]:
    r = subprocess.run(
        ["task-master", "list", "--json"],
        cwd=project_path, capture_output=True, text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"task-master list failed: {r.stderr}")
    return json.loads(r.stdout).get("tasks", [])

def add_task(*, project_path: str, title: str, description: str,
             priority: str, parent_id: Optional[str]) -> Dict[str, Any]:
    cmd = ["task-master", "add-task",
           f"--title={title}", f"--description={description}",
           f"--priority={priority}", "--json"]
    if parent_id:
        cmd.append(f"--parent={parent_id}")
    r = subprocess.run(cmd, cwd=project_path, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"task-master add-task failed: {r.stderr}")
    return json.loads(r.stdout)
```

- [ ] **Step 4: Verify passes**

Run: `uv run pytest tests/smoke/test_taskmaster_client.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kira_hq/api/taskmaster_client.py tests/smoke/test_taskmaster_client.py
git commit -m "feat(4.M2): taskmaster_client wraps `task-master list/add-task --json`"
```

---

### Task 15: `GET /projects` + `GET /projects/{name}/tasks` (PRD §4.M2)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/api/routes/projects.py`
- Modify: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/api/main.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_projects_routes.py`

- [ ] **Step 1: Write failing test**

```python
# tests/smoke/test_projects_routes.py
import json
from pathlib import Path
from fastapi.testclient import TestClient
from kira_hq.api.main import app, set_config

def test_list_projects(tmp_path: Path, monkeypatch):
    y = tmp_path / "projects.yaml"
    y.write_text("version: 2\nprojects:\n  - {name: kira-hq, path: /tmp/p, status: active, priority: high, cron: '* * * * *', added_at: 2026-04-16, skills: [], budget_tokens_monthly: 1, budget_tokens_per_run: 1}\n")
    monkeypatch.setattr("kira_hq.api.routes.projects._list_tasks", lambda path: [{"id":"T-1","status":"pending","priority":"high","title":"x","updated_at":"2026-04-17T00:00:00Z"}])
    set_config(projects_yaml=y)
    client = TestClient(app)
    r = client.get("/projects")
    assert r.status_code == 200
    body = r.json()
    assert body[0]["name"] == "kira-hq"
    assert body[0]["summary"]["total"] == 1
    assert body[0]["summary"]["pending"] == 1

def test_project_tasks_filter(tmp_path: Path, monkeypatch):
    y = tmp_path / "projects.yaml"
    y.write_text("version: 2\nprojects:\n  - {name: kira-hq, path: /tmp/p, status: active, priority: high, cron: '* * * * *', added_at: 2026-04-16, skills: [], budget_tokens_monthly: 1, budget_tokens_per_run: 1}\n")
    monkeypatch.setattr("kira_hq.api.routes.projects._list_tasks", lambda path: [
        {"id":"T-1","status":"pending","priority":"high","title":"x","updated_at":"2026-04-17T00:00:00Z"},
        {"id":"T-2","status":"done","priority":"low","title":"y","updated_at":"2026-04-17T00:00:00Z"},
    ])
    set_config(projects_yaml=y)
    client = TestClient(app)
    r = client.get("/projects/kira-hq/tasks?status=pending")
    assert r.status_code == 200
    assert len(r.json()) == 1 and r.json()[0]["id"] == "T-1"
```

- [ ] **Step 2: Confirm failure**

Run: `uv run pytest tests/smoke/test_projects_routes.py -v`
Expected: FAIL (routes and `set_config` do not exist).

- [ ] **Step 3: Implement routes**

```python
# src/kira_hq/api/routes/__init__.py  (empty)
# src/kira_hq/api/routes/projects.py
from fastapi import APIRouter, HTTPException, Query
from pathlib import Path
from typing import Optional, List, Dict, Any
from kira_hq.config.projects_yaml import load_projects
from kira_hq.api.taskmaster_client import list_tasks as _list_tasks

router = APIRouter()
_CONFIG = {"projects_yaml": Path.home() / ".kira-hq" / "projects.yaml"}

def set_projects_yaml(p: Path) -> None:
    _CONFIG["projects_yaml"] = p

def _summary(tasks):
    s = {"total": len(tasks), "pending": 0, "in-progress": 0, "blocked": 0, "done": 0, "needs-human": 0}
    for t in tasks:
        s[t["status"]] = s.get(t["status"], 0) + 1
    return s

@router.get("/projects")
def list_projects() -> List[Dict[str, Any]]:
    projects = load_projects(_CONFIG["projects_yaml"])
    out = []
    for p in projects:
        try:
            tasks = _list_tasks(p.path)
        except Exception:
            tasks = []
        out.append({"name": p.name, "status": p.status, "priority": p.priority, "summary": _summary(tasks)})
    return out

@router.get("/projects/{name}/tasks")
def project_tasks(name: str,
                  status: Optional[str] = Query(None),
                  priority: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    for p in load_projects(_CONFIG["projects_yaml"]):
        if p.name == name:
            tasks = _list_tasks(p.path)
            if status:   tasks = [t for t in tasks if t["status"] == status]
            if priority: tasks = [t for t in tasks if t["priority"] == priority]
            return tasks
    raise HTTPException(404, f"project {name!r} not found")
```

- [ ] **Step 4: Register router + `set_config`**

Modify `src/kira_hq/api/main.py`:

```python
from fastapi import FastAPI
from pathlib import Path
from kira_hq.api.routes import projects as projects_route

app = FastAPI(title="Kira-HQ", version="2.0")
app.include_router(projects_route.router)

def set_config(*, projects_yaml: Path) -> None:
    projects_route.set_projects_yaml(projects_yaml)

@app.get("/health")
def health(): return {"status": "ok"}
```

- [ ] **Step 5: Verify tests pass**

Run: `uv run pytest tests/smoke/test_projects_routes.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kira_hq/api/routes/ src/kira_hq/api/main.py tests/smoke/test_projects_routes.py
git commit -m "feat(4.M2): GET /projects and GET /projects/{name}/tasks with filters"
```

---

### Task 16: `POST /projects/{name}/tasks` (add task/fix) (PRD §4.M2)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/api/routes/tasks.py`
- Modify: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/api/main.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_add_task.py`

- [ ] **Step 1: Write failing test**

```python
# tests/smoke/test_add_task.py
from pathlib import Path
from fastapi.testclient import TestClient
from kira_hq.api.main import app, set_config

def test_post_task(tmp_path: Path, monkeypatch):
    y = tmp_path / "projects.yaml"
    y.write_text("version: 2\nprojects:\n  - {name: kira-hq, path: /tmp/p, status: active, priority: high, cron: '* * * * *', added_at: 2026-04-16, skills: [], budget_tokens_monthly: 1, budget_tokens_per_run: 1}\n")
    set_config(projects_yaml=y)
    captured = {}
    def fake_add(**kw):
        captured.update(kw); return {"id":"T-42","title":kw["title"]}
    monkeypatch.setattr("kira_hq.api.routes.tasks._add_task", fake_add)
    client = TestClient(app)
    r = client.post("/projects/kira-hq/tasks", json={"title":"Do Y","description":"details","priority":"medium"})
    assert r.status_code == 201
    assert r.json()["id"] == "T-42"
    assert captured["title"] == "Do Y"
    assert captured["parent_id"] is None

def test_post_fix_with_parent(tmp_path: Path, monkeypatch):
    y = tmp_path / "projects.yaml"
    y.write_text("version: 2\nprojects:\n  - {name: kira-hq, path: /tmp/p, status: active, priority: high, cron: '* * * * *', added_at: 2026-04-16, skills: [], budget_tokens_monthly: 1, budget_tokens_per_run: 1}\n")
    set_config(projects_yaml=y)
    monkeypatch.setattr("kira_hq.api.routes.tasks._add_task", lambda **kw: {"id":"T-43","parent_id":kw["parent_id"]})
    r = TestClient(app).post("/projects/kira-hq/tasks", json={"title":"fix","description":"d","priority":"high","parent_id":"T-7"})
    assert r.status_code == 201 and r.json()["parent_id"] == "T-7"
```

- [ ] **Step 2: Confirm failure**

Run: `uv run pytest tests/smoke/test_add_task.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement route**

```python
# src/kira_hq/api/routes/tasks.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from kira_hq.config.projects_yaml import load_projects
from kira_hq.api.taskmaster_client import add_task as _add_task
from kira_hq.api.routes.projects import _CONFIG

router = APIRouter()

class TaskIn(BaseModel):
    title: str
    description: str
    priority: str
    parent_id: Optional[str] = None

@router.post("/projects/{name}/tasks", status_code=201)
def post_task(name: str, body: TaskIn):
    for p in load_projects(_CONFIG["projects_yaml"]):
        if p.name == name:
            return _add_task(project_path=p.path, title=body.title,
                             description=body.description, priority=body.priority,
                             parent_id=body.parent_id)
    raise HTTPException(404, f"project {name!r} not found")
```

- [ ] **Step 4: Register in `main.py`**

Add:
```python
from kira_hq.api.routes import tasks as tasks_route
app.include_router(tasks_route.router)
```

- [ ] **Step 5: Verify**

Run: `uv run pytest tests/smoke/test_add_task.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kira_hq/api/routes/tasks.py src/kira_hq/api/main.py tests/smoke/test_add_task.py
git commit -m "feat(4.M2): POST /projects/{name}/tasks for add task/fix"
```

---

### Task 17: `/views/needs-attention` + `/views/blockers` (PRD §4.M2, §6.10)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/api/routes/views.py`
- Modify: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/api/main.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_views.py`

- [ ] **Step 1: Failing test**

```python
# tests/smoke/test_views.py
from pathlib import Path
from fastapi.testclient import TestClient
from kira_hq.api.main import app, set_config

def test_blockers_only_blocked(tmp_path: Path, monkeypatch):
    y = tmp_path / "projects.yaml"
    y.write_text("version: 2\nprojects:\n  - {name: p, path: /tmp/p, status: active, priority: high, cron: '* * * * *', added_at: 2026-04-16, skills: [], budget_tokens_monthly: 1, budget_tokens_per_run: 1}\n")
    monkeypatch.setattr("kira_hq.api.routes.views._list_tasks", lambda path: [
        {"id":"T-1","status":"blocked","priority":"high","title":"x","updated_at":"2026-04-17T00:00:00Z","blocked_by":["T-0"]},
        {"id":"T-2","status":"pending","priority":"low","title":"y","updated_at":"2026-04-17T00:00:00Z"},
    ])
    set_config(projects_yaml=y)
    r = TestClient(app).get("/views/blockers")
    assert r.status_code == 200
    assert len(r.json()) == 1 and r.json()[0]["id"] == "T-1"

def test_needs_attention_contains_markdown(tmp_path: Path, monkeypatch):
    y = tmp_path / "projects.yaml"
    y.write_text("version: 2\nprojects:\n  - {name: p, path: /tmp/p, status: active, priority: high, cron: '* * * * *', added_at: 2026-04-16, skills: [], budget_tokens_monthly: 100, budget_tokens_per_run: 10}\n")
    monkeypatch.setattr("kira_hq.api.routes.views._list_tasks", lambda path: [])
    monkeypatch.setattr("kira_hq.api.routes.views._cron_fails_24h", lambda name: 0)
    monkeypatch.setattr("kira_hq.api.routes.views._tokens_30d", lambda name: 0)
    set_config(projects_yaml=y)
    r = TestClient(app).get("/views/needs-attention")
    assert r.status_code == 200
    assert "# Needs Attention" in r.text
```

- [ ] **Step 2: Confirm failure**

Run: `uv run pytest tests/smoke/test_views.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/kira_hq/api/routes/views.py
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from datetime import datetime, timezone
from typing import List, Dict, Any
from kira_hq.config.projects_yaml import load_projects
from kira_hq.api.taskmaster_client import list_tasks as _list_tasks
from kira_hq.api.routes.projects import _CONFIG
from kira_hq.renderer.needs_attention import compute_needs_attention, ProjectRuntime, Task

router = APIRouter(prefix="/views")

def _cron_fails_24h(project: str) -> int: return 0          # overridden by pipeline-log scan later
def _tokens_30d(project: str) -> int: return 0              # overridden by tokens aggregate later

@router.get("/blockers")
def blockers() -> List[Dict[str, Any]]:
    out = []
    for p in load_projects(_CONFIG["projects_yaml"]):
        for t in _list_tasks(p.path):
            if t["status"] == "blocked":
                out.append({"project": p.name, **t})
    return out

@router.get("/needs-attention", response_class=PlainTextResponse)
def needs_attention() -> str:
    runtimes: Dict[str, ProjectRuntime] = {}
    for p in load_projects(_CONFIG["projects_yaml"]):
        tasks = []
        for t in _list_tasks(p.path):
            tasks.append(Task(
                id=t["id"], title=t["title"], status=t["status"], priority=t["priority"],
                updated_at=datetime.fromisoformat(t["updated_at"].replace("Z","+00:00")),
                blocked_by=t.get("blocked_by", []),
            ))
        runtimes[p.name] = ProjectRuntime(
            tasks=tasks,
            cron_failures_24h=_cron_fails_24h(p.name),
            tokens_30d=_tokens_30d(p.name),
            budget_monthly=p.budget_tokens_monthly,
        )
    return compute_needs_attention(runtimes, now=datetime.now(timezone.utc))
```

- [ ] **Step 4: Register router**

Add in `src/kira_hq/api/main.py`:
```python
from kira_hq.api.routes import views as views_route
app.include_router(views_route.router)
```

- [ ] **Step 5: Verify**

Run: `uv run pytest tests/smoke/test_views.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kira_hq/api/routes/views.py src/kira_hq/api/main.py tests/smoke/test_views.py
git commit -m "feat(4.M2,6.10): /views/blockers and /views/needs-attention"
```

---

### Task 18: Token aggregation + `/metrics/tokens` + `/metrics/pipeline` (PRD §4.M2, §6.1, §6.2)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/tokens/aggregate.py`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/api/routes/metrics.py`
- Modify: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/api/main.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_tokens.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_metrics_routes.py`

- [ ] **Step 1: Write failing test for aggregate**

```python
# tests/smoke/test_tokens.py
from pathlib import Path
from kira_hq.tokens.aggregate import aggregate_from_log, daily_rollup

PIPELINE = """| timestamp           | project   | skill                  | tokens_in | tokens_out | status | duration_s | notes |
|---|---|---|---|---|---|---|---|
| 2026-04-17T03:00:12 | kira-hq   | kira-hq-render-kanban  | 100       | 200        | ok     | 1.2        | a     |
| 2026-04-17T03:01:05 | monopilot | monopilot-night-crew   | 12450     | 3201       | ok     | 47.3       | b     |
| 2026-04-17T04:00:08 | kira-hq   | kira-weekly-review     | 8200      | 1100       | fail   | 12.0       | c     |
"""

def test_aggregate_per_project_per_day(tmp_path: Path):
    log = tmp_path / "pipeline.log.md"; log.write_text(PIPELINE)
    totals = aggregate_from_log(log, since=None)
    assert totals["kira-hq"] == {"tokens_in": 8300, "tokens_out": 1300, "runs": 2}
    assert totals["monopilot"]["tokens_in"] == 12450

def test_daily_rollup_writes_json(tmp_path: Path):
    log = tmp_path / "pipeline.log.md"; log.write_text(PIPELINE)
    out_dir = tmp_path / "metrics"
    paths = daily_rollup(log, out_dir)
    assert any(p.name == "tokens-2026-04-17.json" for p in paths)
```

- [ ] **Step 2: Confirm failure**

Run: `uv run pytest tests/smoke/test_tokens.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/kira_hq/tokens/__init__.py  (empty)
# src/kira_hq/tokens/aggregate.py
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional
import json, re

ROW = re.compile(r"^\|\s*(?P<ts>\S+)\s*\|\s*(?P<project>\S+)\s*\|\s*(?P<skill>\S+)\s*\|\s*(?P<ti>\d+)\s*\|\s*(?P<to>\d+)\s*\|\s*(?P<status>\w+)\s*\|")

def _iter_rows(log: Path):
    for line in log.read_text().splitlines():
        m = ROW.match(line.strip())
        if not m: continue
        yield m.groupdict()

def aggregate_from_log(log: Path, since: Optional[datetime]) -> Dict[str, Dict[str, int]]:
    totals: Dict[str, Dict[str, int]] = {}
    for r in _iter_rows(log):
        ts = datetime.fromisoformat(r["ts"]).replace(tzinfo=timezone.utc)
        if since and ts < since: continue
        d = totals.setdefault(r["project"], {"tokens_in":0,"tokens_out":0,"runs":0})
        d["tokens_in"] += int(r["ti"]); d["tokens_out"] += int(r["to"]); d["runs"] += 1
    return totals

def daily_rollup(log: Path, out_dir: Path) -> List[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    per_day: Dict[str, Dict[str, Dict[str,int]]] = {}
    for r in _iter_rows(log):
        day = r["ts"][:10]
        per_day.setdefault(day, {}).setdefault(r["project"], {"tokens_in":0,"tokens_out":0,"runs":0})
        per_day[day][r["project"]]["tokens_in"] += int(r["ti"])
        per_day[day][r["project"]]["tokens_out"] += int(r["to"])
        per_day[day][r["project"]]["runs"] += 1
    paths: List[Path] = []
    for day, data in per_day.items():
        p = out_dir / f"tokens-{day}.json"
        p.write_text(json.dumps(data, indent=2))
        paths.append(p)
    return paths
```

- [ ] **Step 4: Verify tokens tests pass**

Run: `uv run pytest tests/smoke/test_tokens.py -v`
Expected: 2 passed.

- [ ] **Step 5: Write route test**

```python
# tests/smoke/test_metrics_routes.py
from pathlib import Path
from fastapi.testclient import TestClient
from kira_hq.api.main import app, set_config

def test_metrics_tokens(tmp_path: Path):
    log = tmp_path / "pipeline.log.md"
    log.write_text("| ts | p | s | ti | to | st | d | n |\n|-|-|-|-|-|-|-|-|\n"
                   "| 2026-04-17T03:00:12 | kira-hq | x | 100 | 200 | ok | 1 | a |\n")
    set_config(projects_yaml=tmp_path/"projects.yaml", pipeline_log=log)
    (tmp_path/"projects.yaml").write_text("version: 2\nprojects: []\n")
    r = TestClient(app).get("/metrics/tokens")
    assert r.status_code == 200
    assert r.json()["kira-hq"]["tokens_in"] == 100

def test_metrics_pipeline_since(tmp_path: Path):
    log = tmp_path / "pipeline.log.md"
    log.write_text("| ts | p | s | ti | to | st | d | n |\n|-|-|-|-|-|-|-|-|\n"
                   "| 2026-04-10T03:00:12 | kira-hq | x | 100 | 200 | ok | 1 | a |\n"
                   "| 2026-04-17T03:00:12 | kira-hq | x | 50  | 70  | ok | 1 | b |\n")
    set_config(projects_yaml=tmp_path/"projects.yaml", pipeline_log=log)
    (tmp_path/"projects.yaml").write_text("version: 2\nprojects: []\n")
    r = TestClient(app).get("/metrics/pipeline?since=2026-04-15T00:00:00")
    assert r.status_code == 200
    assert r.json()["kira-hq"]["tokens_in"] == 50
```

- [ ] **Step 6: Confirm failure**

Run: `uv run pytest tests/smoke/test_metrics_routes.py -v`
Expected: FAIL.

- [ ] **Step 7: Implement metrics route**

```python
# src/kira_hq/api/routes/metrics.py
from fastapi import APIRouter, Query
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from kira_hq.tokens.aggregate import aggregate_from_log

router = APIRouter(prefix="/metrics")
_STATE = {"pipeline_log": Path.home() / ".kira-hq" / "global-pipeline.log.md"}

def set_pipeline_log(p: Path) -> None:
    _STATE["pipeline_log"] = p

@router.get("/tokens")
def tokens():
    return aggregate_from_log(_STATE["pipeline_log"], since=None)

@router.get("/pipeline")
def pipeline(since: Optional[str] = Query(None)):
    s = datetime.fromisoformat(since).replace(tzinfo=timezone.utc) if since else None
    return aggregate_from_log(_STATE["pipeline_log"], since=s)
```

- [ ] **Step 8: Extend `set_config`**

Modify `src/kira_hq/api/main.py`:

```python
from kira_hq.api.routes import metrics as metrics_route
app.include_router(metrics_route.router)

def set_config(*, projects_yaml, pipeline_log=None):
    projects_route.set_projects_yaml(projects_yaml)
    if pipeline_log is not None:
        metrics_route.set_pipeline_log(pipeline_log)
```

- [ ] **Step 9: Verify**

Run: `uv run pytest tests/smoke/test_metrics_routes.py -v`
Expected: 2 passed.

- [ ] **Step 10: Commit**

```bash
git add src/kira_hq/tokens/ src/kira_hq/api/routes/metrics.py src/kira_hq/api/main.py tests/smoke/test_tokens.py tests/smoke/test_metrics_routes.py
git commit -m "feat(4.M2,6.1,6.2): /metrics/tokens + /metrics/pipeline with daily rollup"
```

---

### Task 19: HTTP Basic auth behind env toggle (PRD §4.M2, §6.5, §6.12)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/api/auth.py`
- Modify: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/api/main.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_auth.py`

- [ ] **Step 1: Failing test**

```python
# tests/smoke/test_auth.py
import os, base64
from fastapi.testclient import TestClient
from kira_hq.api.main import app, set_config

def test_no_auth_by_default(tmp_path):
    (tmp_path/"projects.yaml").write_text("version: 2\nprojects: []\n")
    set_config(projects_yaml=tmp_path/"projects.yaml")
    os.environ.pop("KIRA_HQ_REQUIRE_AUTH", None)
    assert TestClient(app).get("/projects").status_code == 200

def test_requires_auth_when_enabled(monkeypatch, tmp_path):
    (tmp_path/"projects.yaml").write_text("version: 2\nprojects: []\n")
    set_config(projects_yaml=tmp_path/"projects.yaml")
    monkeypatch.setenv("KIRA_HQ_REQUIRE_AUTH","1")
    monkeypatch.setenv("KIRA_HQ_USER","u"); monkeypatch.setenv("KIRA_HQ_PASS","p")
    c = TestClient(app)
    assert c.get("/projects").status_code == 401
    tok = base64.b64encode(b"u:p").decode()
    assert c.get("/projects", headers={"Authorization": f"Basic {tok}"}).status_code == 200
```

- [ ] **Step 2: Confirm failure**

Run: `uv run pytest tests/smoke/test_auth.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement auth dependency**

```python
# src/kira_hq/api/auth.py
import os, secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

_basic = HTTPBasic(auto_error=False)

def maybe_auth(creds: HTTPBasicCredentials | None = Depends(_basic)):
    if os.environ.get("KIRA_HQ_REQUIRE_AUTH") != "1":
        return True
    want_u = os.environ.get("KIRA_HQ_USER","")
    want_p = os.environ.get("KIRA_HQ_PASS","")
    if creds is None or not (
        secrets.compare_digest(creds.username, want_u) and
        secrets.compare_digest(creds.password, want_p)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="auth required",
                            headers={"WWW-Authenticate": "Basic"})
    return True
```

- [ ] **Step 4: Apply globally**

Modify `src/kira_hq/api/main.py`:

```python
from fastapi import Depends
from kira_hq.api.auth import maybe_auth

app = FastAPI(title="Kira-HQ", version="2.0", dependencies=[Depends(maybe_auth)])
# (rest unchanged)
```

- [ ] **Step 5: Verify**

Run: `uv run pytest tests/smoke/test_auth.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kira_hq/api/auth.py src/kira_hq/api/main.py tests/smoke/test_auth.py
git commit -m "feat(4.M2,6.12): HTTP Basic auth gated by KIRA_HQ_REQUIRE_AUTH=1"
```

---

### Task 20: Module 2 integration test + Postman collection (PRD §4.M2 DoD)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/integration/test_api_e2e.py`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/docs/POSTMAN.json`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/api/README.md`

- [ ] **Step 1: Write integration test with uvicorn subprocess**

```python
# tests/integration/test_api_e2e.py
import subprocess, time, httpx, signal, os, sys, json
from pathlib import Path

def test_curl_equivalent_roundtrip(tmp_path: Path):
    y = tmp_path / "projects.yaml"; y.write_text("version: 2\nprojects: []\n")
    env = {**os.environ, "KIRA_HQ_PROJECTS_YAML": str(y)}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "kira_hq.api.main:app",
         "--host","127.0.0.1","--port","3100"],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        for _ in range(30):
            try:
                r = httpx.get("http://127.0.0.1:3100/health"); break
            except httpx.HTTPError: time.sleep(0.3)
        else:
            raise RuntimeError("server never came up")
        assert httpx.get("http://127.0.0.1:3100/health").json() == {"status":"ok"}
        assert httpx.get("http://127.0.0.1:3100/projects").status_code == 200
    finally:
        proc.send_signal(signal.SIGINT); proc.wait(timeout=5)
```

Also modify `src/kira_hq/api/main.py` to read `KIRA_HQ_PROJECTS_YAML` at import:

```python
import os
from pathlib import Path
_default_yaml = Path(os.environ.get("KIRA_HQ_PROJECTS_YAML", Path.home()/".kira-hq"/"projects.yaml"))
projects_route.set_projects_yaml(_default_yaml)
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/integration/test_api_e2e.py -v`
Expected: 1 passed.

- [ ] **Step 3: Write Postman collection**

Create `docs/POSTMAN.json`:

```json
{
  "info": {"name":"Kira-HQ v2.0","schema":"https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
  "item": [
    {"name":"Health","request":{"method":"GET","url":"http://127.0.0.1:3100/health"}},
    {"name":"List projects","request":{"method":"GET","url":"http://127.0.0.1:3100/projects"}},
    {"name":"Project tasks","request":{"method":"GET","url":"http://127.0.0.1:3100/projects/kira-hq/tasks?status=pending"}},
    {"name":"Blockers","request":{"method":"GET","url":"http://127.0.0.1:3100/views/blockers"}},
    {"name":"Needs attention","request":{"method":"GET","url":"http://127.0.0.1:3100/views/needs-attention"}},
    {"name":"Tokens","request":{"method":"GET","url":"http://127.0.0.1:3100/metrics/tokens"}},
    {"name":"Pipeline","request":{"method":"GET","url":"http://127.0.0.1:3100/metrics/pipeline?since=2026-04-10T00:00:00"}},
    {"name":"Add task","request":{"method":"POST","url":"http://127.0.0.1:3100/projects/kira-hq/tasks",
      "header":[{"key":"Content-Type","value":"application/json"}],
      "body":{"mode":"raw","raw":"{\"title\":\"x\",\"description\":\"d\",\"priority\":\"medium\"}"}}}
  ]
}
```

- [ ] **Step 4: Write API README**

Create `src/kira_hq/api/README.md`:

```markdown
# Module 2 — FastAPI Backend

## Run
```
uv run uvicorn kira_hq.api.main:app --host 127.0.0.1 --port 3100
```

## Endpoints
- `GET /health` → `{"status":"ok"}`
- `GET /projects` — from projects.yaml v2 + per-project task summary
- `GET /projects/{name}/tasks?status=&priority=`
- `POST /projects/{name}/tasks` body: `{title, description, priority, parent_id?}`
- `GET /views/blockers` — tasks with `status: blocked` across all projects
- `GET /views/needs-attention` — markdown output of needs-attention algorithm (§6.10)
- `GET /metrics/tokens` — aggregate tokens per project from pipeline.log
- `GET /metrics/pipeline?since=ISO` — filtered aggregate

## Auth
- Off by default (localhost only).
- Set `KIRA_HQ_REQUIRE_AUTH=1` + `KIRA_HQ_USER` + `KIRA_HQ_PASS` to require Basic.

## Error modes
- `projects.yaml` version ≠ 2 → 500 with message pointing at `scripts/migrate_projects_yaml.py`
- task-master CLI missing → 500
- Project not in yaml → 404

## Postman
See `docs/POSTMAN.json`.
```

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_api_e2e.py docs/POSTMAN.json src/kira_hq/api/README.md src/kira_hq/api/main.py
git commit -m "feat(4.M2): integration test + Postman collection + README"
```

---

## Phase C — Module 3: Next.js Frontend (PRD §4.M3)

### Task 21: Scaffold Next.js app + API client (PRD §4.M3)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/frontend/package.json`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/frontend/next.config.js`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/frontend/tsconfig.json`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/frontend/app/layout.tsx`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/frontend/app/page.tsx`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/frontend/lib/api.ts`

- [ ] **Step 1: Scaffold**

Run:
```bash
mkdir -p /Users/mariuszkrawczyk/Projects/kira-hq/frontend
cd /Users/mariuszkrawczyk/Projects/kira-hq/frontend
npx --yes create-next-app@14 . --typescript --app --tailwind --eslint --src-dir=false --import-alias='@/*' --no-git --use-npm
```
Expected: scaffolding finishes; `npm run dev` would boot.

- [ ] **Step 2: Write `lib/api.ts`**

```ts
// frontend/lib/api.ts
const BASE = process.env.NEXT_PUBLIC_KIRA_HQ_API ?? "http://127.0.0.1:3100";

export type TaskSummary = { total: number; pending: number; "in-progress": number; blocked: number; done: number; "needs-human": number };
export type Project = { name: string; status: string; priority: string; summary: TaskSummary };
export type Task = { id: string; title: string; status: string; priority: string; updated_at: string; blocked_by?: string[] };

async function j<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json() as Promise<T>;
}

export const api = {
  projects: () => j<Project[]>("/projects"),
  tasks:    (name: string) => j<Task[]>(`/projects/${encodeURIComponent(name)}/tasks`),
  blockers: () => j<(Task & { project: string })[]>("/views/blockers"),
  needsAttention: async (): Promise<string> => {
    const r = await fetch(`${BASE}/views/needs-attention`, { cache: "no-store" });
    if (!r.ok) throw new Error(`needs-attention → ${r.status}`);
    return r.text();
  },
};
```

- [ ] **Step 3: Replace `app/page.tsx` with project list**

```tsx
// frontend/app/page.tsx
import { api, Project } from "@/lib/api";

export default async function Home() {
  const projects: Project[] = await api.projects();
  return (
    <main className="p-6">
      <h1 className="text-2xl font-bold mb-4">Kira-HQ</h1>
      <ul className="space-y-2">
        {projects.map(p => (
          <li key={p.name} className="border rounded p-3">
            <a href={`/projects/${p.name}`} className="font-semibold">{p.name}</a>
            <span className="ml-2 text-sm text-gray-500">{p.status} / {p.priority}</span>
            <div className="text-sm">
              {p.summary.total} tasks · pending {p.summary.pending} · in-progress {p.summary["in-progress"]} · blocked {p.summary.blocked} · done {p.summary.done}
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
```

- [ ] **Step 4: Commit**

```bash
cd /Users/mariuszkrawczyk/Projects/kira-hq
git add frontend/
git commit -m "feat(4.M3): Next.js scaffold + api client + project list page"
```

---

### Task 22: Project detail page + TaskCard component (PRD §4.M3)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/frontend/app/projects/[name]/page.tsx`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/frontend/components/TaskCard.tsx`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/frontend/components/KanbanColumn.tsx`

- [ ] **Step 1: Create `TaskCard.tsx`**

```tsx
// frontend/components/TaskCard.tsx
"use client";
import { useState } from "react";
import type { Task } from "@/lib/api";

export function TaskCard({ task }: { task: Task }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border rounded p-2 bg-white cursor-pointer"
         data-testid="task-card"
         data-task-id={task.id}
         onClick={() => setOpen(!open)}>
      <div className="font-medium">{task.id} · {task.title}</div>
      <div className="text-xs text-gray-500">{task.priority} · {task.status}</div>
      {open && (
        <div className="mt-2 text-sm" data-testid="task-detail">
          <div>Updated: {task.updated_at}</div>
          {task.blocked_by?.length ? <div>Blocked by: {task.blocked_by.join(", ")}</div> : null}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create `KanbanColumn.tsx`**

```tsx
// frontend/components/KanbanColumn.tsx
import type { Task } from "@/lib/api";
import { TaskCard } from "./TaskCard";

export function KanbanColumn({ title, tasks }: { title: string; tasks: Task[] }) {
  return (
    <section className="bg-gray-50 rounded p-3 min-w-[220px]">
      <h2 className="font-semibold mb-2">{title} ({tasks.length})</h2>
      <div className="space-y-2">{tasks.map(t => <TaskCard key={t.id} task={t} />)}</div>
    </section>
  );
}
```

- [ ] **Step 3: Create project page**

```tsx
// frontend/app/projects/[name]/page.tsx
import { api } from "@/lib/api";
import { KanbanColumn } from "@/components/KanbanColumn";

const COLS: [string, string[]][] = [
  ["Needs-attention", ["blocked","needs-human"]],
  ["In-progress", ["in-progress"]],
  ["Pending", ["pending"]],
  ["Done", ["done"]],
];

export default async function ProjectPage({ params }: { params: { name: string } }) {
  const tasks = await api.tasks(params.name);
  return (
    <main className="p-6">
      <h1 className="text-2xl font-bold mb-4">{params.name}</h1>
      <div className="grid grid-flow-col auto-cols-max gap-4">
        {COLS.map(([title, statuses]) => (
          <KanbanColumn key={title} title={title} tasks={tasks.filter(t => statuses.includes(t.status))} />
        ))}
      </div>
    </main>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/app/projects frontend/components
git commit -m "feat(4.M3): project detail kanban page + TaskCard + KanbanColumn"
```

---

### Task 23: Needs-attention page + Blockers page + Hermes iframe (PRD §4.M3, §6.10, §6.14)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/frontend/app/needs-attention/page.tsx`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/frontend/app/blockers/page.tsx`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/frontend/components/HermesFrame.tsx`
- Modify: `/Users/mariuszkrawczyk/Projects/kira-hq/frontend/app/layout.tsx`

- [ ] **Step 1: Needs-attention page (renders markdown as pre text)**

```tsx
// frontend/app/needs-attention/page.tsx
import { api } from "@/lib/api";
export default async function Page() {
  const md = await api.needsAttention();
  return <main className="p-6"><pre className="whitespace-pre-wrap text-sm">{md}</pre></main>;
}
```

- [ ] **Step 2: Blockers page**

```tsx
// frontend/app/blockers/page.tsx
import { api } from "@/lib/api";
export default async function Page() {
  const blockers = await api.blockers();
  return (
    <main className="p-6">
      <h1 className="text-2xl font-bold mb-4">Blockers ({blockers.length})</h1>
      <ul className="space-y-1">
        {blockers.map(b => (
          <li key={`${b.project}-${b.id}`} className="border rounded p-2">
            <span className="font-mono">{b.project}/{b.id}</span> — {b.title}
            {b.blocked_by?.length ? <span className="text-xs ml-2">blocked by {b.blocked_by.join(",")}</span> : null}
          </li>
        ))}
      </ul>
    </main>
  );
}
```

- [ ] **Step 3: Hermes iframe**

```tsx
// frontend/components/HermesFrame.tsx
export function HermesFrame() {
  const url = process.env.NEXT_PUBLIC_HERMES_URL ?? "about:blank";
  return <iframe src={url} className="w-full h-96 border rounded" title="Hermes dashboard" />;
}
```

- [ ] **Step 4: Nav in layout**

```tsx
// frontend/app/layout.tsx
import "./globals.css";
export const metadata = { title: "Kira-HQ" };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en"><body>
      <nav className="bg-gray-900 text-white p-3 flex gap-4">
        <a href="/">Projects</a>
        <a href="/needs-attention">Needs attention</a>
        <a href="/blockers">Blockers</a>
      </nav>
      {children}
    </body></html>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/app frontend/components/HermesFrame.tsx
git commit -m "feat(4.M3,6.10,6.14): needs-attention + blockers pages + Hermes iframe + nav"
```

---

### Task 24: Playwright E2E — 10-tasks parity (PRD §4.M3 DoD, §6.15)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/e2e/test_module3_dashboard.py`

- [ ] **Step 1: Write fixture + test**

```python
# tests/e2e/test_module3_dashboard.py
import json, os, signal, subprocess, sys, time
from pathlib import Path
import httpx, pytest
from playwright.sync_api import sync_playwright

@pytest.fixture
def servers(tmp_path: Path):
    proj = tmp_path / "fx"; (proj / ".taskmaster").mkdir(parents=True)
    tasks = [{"id": f"T-{i}", "title": f"Task {i}", "status": "pending",
              "priority": "medium", "updated_at":"2026-04-17T00:00:00Z"} for i in range(10)]
    (proj / ".taskmaster" / "tasks.json").write_text(json.dumps({"tasks": tasks}))
    y = tmp_path / "projects.yaml"
    y.write_text(f"version: 2\nprojects:\n  - {{name: fx, path: {proj}, status: active, priority: medium, cron: '* * * * *', added_at: 2026-04-16, skills: [], budget_tokens_monthly: 1, budget_tokens_per_run: 1}}\n")
    env = {**os.environ, "KIRA_HQ_PROJECTS_YAML": str(y)}
    api = subprocess.Popen([sys.executable,"-m","uvicorn","kira_hq.api.main:app","--host","127.0.0.1","--port","3100"], env=env)
    fe = subprocess.Popen(["npm","run","dev","--","--port","3001"],
        cwd="/Users/mariuszkrawczyk/Projects/kira-hq/frontend",
        env={**os.environ,"NEXT_PUBLIC_KIRA_HQ_API":"http://127.0.0.1:3100"})
    for _ in range(60):
        try:
            httpx.get("http://127.0.0.1:3100/health").raise_for_status()
            httpx.get("http://127.0.0.1:3001").raise_for_status(); break
        except Exception: time.sleep(1)
    yield proj, tasks
    api.send_signal(signal.SIGINT); fe.send_signal(signal.SIGINT)
    api.wait(timeout=5); fe.wait(timeout=10)

def test_ten_tasks_visible_click_detail_then_eleven(servers):
    proj, tasks = servers
    with sync_playwright() as p:
        page = p.chromium.launch().new_page()
        page.goto("http://127.0.0.1:3001/projects/fx")
        page.wait_for_selector('[data-testid=task-card]')
        cards = page.locator('[data-testid=task-card]')
        assert cards.count() == 10
        cards.first.click()
        page.wait_for_selector('[data-testid=task-detail]')
        assert "T-0" in page.content()
        # mutate fixture → add T-10
        tasks.append({"id":"T-10","title":"Task 10","status":"pending","priority":"medium","updated_at":"2026-04-17T00:00:00Z"})
        (proj/".taskmaster"/"tasks.json").write_text(json.dumps({"tasks": tasks}))
        page.reload()
        page.wait_for_selector('[data-testid=task-card]')
        assert page.locator('[data-testid=task-card]').count() == 11
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/e2e/test_module3_dashboard.py -v`
Expected: 1 passed (servers boot, Playwright finds 10 cards → detail → 11 after reload).

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_module3_dashboard.py
git commit -m "test(4.M3): Playwright E2E — 10 tasks visible, click detail, 11 after mutation"
```

---

### Task 25: Module 3 README + dev scripts (PRD §4.M3 DoD, §6.13, §6.17)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/frontend/README.md`

- [ ] **Step 1: Write README**

```markdown
# Module 3 — Next.js Dashboard

## Dev (Phase 3a: localhost-first)
```
cd frontend
npm install
NEXT_PUBLIC_KIRA_HQ_API=http://127.0.0.1:3100 npm run dev -- --port 3001
```

Open http://127.0.0.1:3001

## Pages
- `/` — project list (GET /projects)
- `/projects/<name>` — kanban (GET /projects/<name>/tasks)
- `/needs-attention` — GET /views/needs-attention (markdown)
- `/blockers` — GET /views/blockers

## Phase 3b: Vercel (only after 3a stable ≥1 week — per PRD §6.13)
- Set `NEXT_PUBLIC_KIRA_HQ_API` env var on Vercel (e.g. Tailscale URL)
- Set `NEXT_PUBLIC_HERMES_URL` for the embedded Hermes iframe
- Require Basic auth on API side (`KIRA_HQ_REQUIRE_AUTH=1`)

## Error modes
- API unreachable → page shows fetch error (server component throws)
- Empty projects.yaml → `/` renders empty list (no error)

## Tests
- Playwright E2E: `uv run pytest tests/e2e/test_module3_dashboard.py`
```

- [ ] **Step 2: Commit**

```bash
git add frontend/README.md
git commit -m "docs(4.M3): frontend README with dev/deploy/error modes"
```

---

## Phase D — Module 4: Hermes Integration + Shared Skills Library (PRD §4.M4, §6.11, §6.14, §6.18)

### Task 26: Init shared-skills git repo (PRD §6.11)

**Files:**
- Create: `/Users/mariuszkrawczyk/.kira-hq/skills-shared/README.md`
- Create: `/Users/mariuszkrawczyk/.kira-hq/skills-shared/.gitignore`

- [ ] **Step 1: Init repo**

```bash
cd /Users/mariuszkrawczyk/.kira-hq/skills-shared 2>/dev/null || mkdir -p /Users/mariuszkrawczyk/.kira-hq/skills-shared
cd /Users/mariuszkrawczyk/.kira-hq/skills-shared
git init -b main
```

- [ ] **Step 2: Write README**

```markdown
# Kira-HQ shared skills

Single source of truth for Kira-HQ skills. Projects + Hermes symlink into this directory.

## Skills in this repo
- `kira-hq-render-kanban` — renders kanban_board.md per project
- `kira-hq-report` — post-cycle summary (changes, blockers, alerts)
- `kira-weekly-review` — Saturday 09:00 aggregate
- `kira-add-project` — onboard a new project

## Distribution
- Per project: `~/Projects/<name>/.claude/skills/<skill>` → symlink into this repo
- Hermes: `~/.hermes/skills/<skill>` → symlink into this repo

## Versioning
Git tags `vMAJOR.MINOR`. `projects.yaml` v2 does NOT pin tags yet (see PRD §7: out of scope).
```

- [ ] **Step 3: Commit**

```bash
git add README.md .gitignore
git commit -m "chore: init kira-hq shared-skills repo"
cd /Users/mariuszkrawczyk/Projects/kira-hq
```

---

### Task 27: `kira-hq-report` skill (PRD §4.M4)

**Files:**
- Create: `/Users/mariuszkrawczyk/.kira-hq/skills-shared/kira-hq-report/SKILL.md`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/skills/report.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_report.py`

- [ ] **Step 1: Write failing test**

```python
# tests/smoke/test_report.py
from pathlib import Path
from datetime import datetime, timezone, timedelta
from kira_hq.skills.report import generate_report

def test_report_includes_changes_blockers_alerts(tmp_path: Path):
    log = tmp_path / "pipeline.log.md"
    log.write_text("| ts | p | s | ti | to | st | d | n |\n|-|-|-|-|-|-|-|-|\n"
                   "| 2026-04-17T03:00:00 | p1 | x | 10 | 20 | ok   | 1 | a |\n"
                   "| 2026-04-17T04:00:00 | p2 | y | 5  | 8  | fail | 1 | b |\n")
    since = datetime(2026,4,17,2,0,0,tzinfo=timezone.utc)
    out = generate_report(log, since=since)
    assert "## Changes since" in out
    assert "p1" in out and "p2" in out
    assert "Failures" in out
```

- [ ] **Step 2: Confirm failure**

Run: `uv run pytest tests/smoke/test_report.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/kira_hq/skills/__init__.py  (empty)
# src/kira_hq/skills/report.py
from pathlib import Path
from datetime import datetime, timezone
from kira_hq.tokens.aggregate import _iter_rows

def generate_report(pipeline_log: Path, since: datetime) -> str:
    changes, fails = [], []
    for r in _iter_rows(pipeline_log):
        ts = datetime.fromisoformat(r["ts"]).replace(tzinfo=timezone.utc)
        if ts < since: continue
        line = f"- {r['ts']} {r['project']}/{r['skill']} ti={r['ti']} to={r['to']} status={r['status']}"
        changes.append(line)
        if r["status"] == "fail":
            fails.append(line)
    md = [f"## Changes since {since.isoformat()} ({len(changes)} runs)"]
    md += changes
    md += [f"", f"## Failures ({len(fails)})"]
    md += fails or ["- none"]
    return "\n".join(md)
```

- [ ] **Step 4: Write SKILL.md**

```markdown
---
name: kira-hq-report
description: Use after each cron cycle to summarize what changed. Reads ~/.kira-hq/global-pipeline.log.md since last run.
---

# kira-hq-report

Runs: `uv run python -m kira_hq.skills.report --since <ISO>`.

Writes: markdown summary to stdout + Telegram (via Hermes).
```

- [ ] **Step 5: Verify**

Run: `uv run pytest tests/smoke/test_report.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kira_hq/skills/report.py tests/smoke/test_report.py
git commit -m "feat(4.M4): kira-hq-report skill summarises pipeline.log since given ts"
cd /Users/mariuszkrawczyk/.kira-hq/skills-shared
git add kira-hq-report/
git commit -m "feat: kira-hq-report SKILL.md"
cd /Users/mariuszkrawczyk/Projects/kira-hq
```

---

### Task 28: `kira-weekly-review` skill (PRD §4.M4, §6.18)

**Files:**
- Create: `/Users/mariuszkrawczyk/.kira-hq/skills-shared/kira-weekly-review/SKILL.md`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/skills/weekly_review.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/integration/test_weekly_review.py`

- [ ] **Step 1: Failing integration test**

```python
# tests/integration/test_weekly_review.py
from pathlib import Path
from datetime import datetime, timezone
from kira_hq.skills.weekly_review import run_weekly_review

def test_weekly_review_writes_file(tmp_path: Path):
    log = tmp_path / "pipeline.log.md"
    log.write_text("| ts | p | s | ti | to | st | d | n |\n|-|-|-|-|-|-|-|-|\n"
                   "| 2026-04-14T03:00:00 | p1 | kira-hq-render-kanban | 100 | 200 | ok   | 1 | a |\n"
                   "| 2026-04-15T03:00:00 | p2 | other-skill           | 500 | 400 | fail | 1 | b |\n")
    snapshots_dir = tmp_path / "snaps"
    for d in ["2026-04-08","2026-04-09","2026-04-10","2026-04-11","2026-04-12","2026-04-13","2026-04-14"]:
        (snapshots_dir / d).mkdir(parents=True)
    reviews = tmp_path / "reviews"
    out = run_weekly_review(
        pipeline_log=log, snapshots_dir=snapshots_dir, reviews_dir=reviews,
        now=datetime(2026,4,14,9,0,0,tzinfo=timezone.utc),
        projects_yaml=None,
    )
    assert out.exists()
    text = out.read_text()
    assert "Top-3 token consumers" in text
    assert "Snapshot health" in text
    assert "7/7" in text
    assert "p2" in text and "fail" in text
```

- [ ] **Step 2: Confirm failure**

Run: `uv run pytest tests/integration/test_weekly_review.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/kira_hq/skills/weekly_review.py
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional
from kira_hq.tokens.aggregate import aggregate_from_log, _iter_rows

def run_weekly_review(*, pipeline_log: Path, snapshots_dir: Path, reviews_dir: Path,
                      now: datetime, projects_yaml: Optional[Path]) -> Path:
    reviews_dir.mkdir(parents=True, exist_ok=True)
    iso_year, iso_week, _ = now.isocalendar()
    out_path = reviews_dir / f"{iso_year}-W{iso_week:02d}.md"

    week_ago = now - timedelta(days=7)
    totals = aggregate_from_log(pipeline_log, since=week_ago)
    top3 = sorted(totals.items(), key=lambda kv: kv[1]["tokens_in"]+kv[1]["tokens_out"], reverse=True)[:3]

    # cron success rate
    success, fail = {}, {}
    for r in _iter_rows(pipeline_log):
        ts = datetime.fromisoformat(r["ts"]).replace(tzinfo=timezone.utc)
        if ts < week_ago: continue
        (success if r["status"] == "ok" else fail).setdefault(r["project"], 0)
        (success if r["status"] == "ok" else fail)[r["project"]] += 1

    # snapshot health
    days_present = 0
    for i in range(7):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        if (snapshots_dir / d).exists(): days_present += 1
    snap_line = f"{days_present}/7 days with snapshot"

    lines = [f"# Weekly review {iso_year}-W{iso_week:02d}", ""]
    lines += ["## Top-3 token consumers"]
    for name, agg in top3:
        lines.append(f"- {name}: in={agg['tokens_in']}, out={agg['tokens_out']}, runs={agg['runs']}")
    lines += ["", "## Cron success"]
    for name in sorted(set(list(success)+list(fail))):
        s = success.get(name,0); f = fail.get(name,0)
        lines.append(f"- {name}: {s} ok / {f} fail")
    lines += ["", "## Snapshot health", f"- {snap_line}"]
    lines += ["", "## Parallel track (Path A Hermes vs Path B Claude Code)",
              "- See docs/PARALLEL_TRACK.md for weekly row."]
    out_path.write_text("\n".join(lines))
    return out_path
```

- [ ] **Step 4: Write SKILL.md**

```markdown
---
name: kira-weekly-review
description: Use Saturday 09:00 (or on demand via Telegram /review) to produce weekly aggregate report.
---

# kira-weekly-review

Invocation: `uv run python -m kira_hq.skills.weekly_review`.

Outputs: `~/.kira-hq/reviews/YYYY-Www.md` + Telegram summary.

Contents:
- Tasks completed per project (future: reads .taskmaster history)
- Tokens top-3 + week-over-week delta (future)
- Cron success rate
- Snapshot health (7/7 days)
- Parallel-track comparison row (Path A Hermes vs Path B Claude Code)
```

- [ ] **Step 5: Verify**

Run: `uv run pytest tests/integration/test_weekly_review.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kira_hq/skills/weekly_review.py tests/integration/test_weekly_review.py
git commit -m "feat(4.M4,6.18): kira-weekly-review with snapshots+tokens+cron health"
cd /Users/mariuszkrawczyk/.kira-hq/skills-shared
git add kira-weekly-review/
git commit -m "feat: kira-weekly-review SKILL.md"
cd /Users/mariuszkrawczyk/Projects/kira-hq
```

---

### Task 29: `kira-add-project` CLI + skill (PRD §4.M4, §6.9)

**Files:**
- Create: `/Users/mariuszkrawczyk/.kira-hq/skills-shared/kira-add-project/SKILL.md`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/cli/__init__.py`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/cli/add_project.py`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/cli/archive_project.py`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/cli/main.py`
- Modify: `/Users/mariuszkrawczyk/Projects/kira-hq/pyproject.toml` (add console script)
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/integration/test_add_project.py`

- [ ] **Step 1: Failing test**

```python
# tests/integration/test_add_project.py
from pathlib import Path
import subprocess, sys, yaml

def _fake_project(root: Path, name: str) -> Path:
    proj = root / name; proj.mkdir()
    (proj / ".git").mkdir()
    (proj / ".taskmaster").mkdir()
    (proj / ".taskmaster" / "tasks.json").write_text('{"tasks":[]}')
    (proj / "prd").mkdir(); (proj / "prd" / "master-prd.md").write_text("# PRD")
    return proj

def test_add_project_updates_yaml_and_creates_env(tmp_path: Path):
    y = tmp_path / "projects.yaml"
    y.write_text("version: 2\nprojects: []\n")
    shared = tmp_path / "skills-shared"
    shared.mkdir(); (shared / "kira-hq-render-kanban").mkdir()
    proj = _fake_project(tmp_path, "alpha")

    r = subprocess.run(
        [sys.executable, "-m", "kira_hq.cli.main", "add-project", str(proj),
         "--name=alpha", "--priority=high", "--cron=0 */2 * * *",
         "--budget-monthly=500000", "--budget-per-run=50000",
         "--skill=kira-hq-render-kanban", "--yes"],
        env={
            "KIRA_HQ_PROJECTS_YAML": str(y),
            "KIRA_HQ_SKILLS_SHARED": str(shared),
            "PATH": "/usr/bin:/bin",
        },
        capture_output=True, text=True, cwd="/Users/mariuszkrawczyk/Projects/kira-hq",
    )
    assert r.returncode == 0, r.stderr
    data = yaml.safe_load(y.read_text())
    assert data["projects"][0]["name"] == "alpha"
    assert data["projects"][0]["status"] == "active"
    assert (proj / ".env").exists()
    assert (proj / ".claude" / "skills" / "kira-hq-render-kanban").is_symlink()

def test_archive_project_flips_status(tmp_path: Path):
    y = tmp_path / "projects.yaml"
    y.write_text("version: 2\nprojects:\n  - {name: alpha, path: /x, status: active, priority: high, cron: '* * * * *', added_at: 2026-04-16, skills: [], budget_tokens_monthly: 1, budget_tokens_per_run: 1}\n")
    r = subprocess.run([sys.executable,"-m","kira_hq.cli.main","archive-project","alpha"],
                       env={"KIRA_HQ_PROJECTS_YAML": str(y), "PATH":"/usr/bin:/bin"},
                       capture_output=True, text=True, cwd="/Users/mariuszkrawczyk/Projects/kira-hq")
    assert r.returncode == 0, r.stderr
    assert yaml.safe_load(y.read_text())["projects"][0]["status"] == "archived"
```

- [ ] **Step 2: Confirm failure**

Run: `uv run pytest tests/integration/test_add_project.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement CLI**

```python
# src/kira_hq/cli/add_project.py
import argparse, os, subprocess, sys, yaml
from pathlib import Path
from datetime import date

def main(argv):
    ap = argparse.ArgumentParser(prog="kira-hq add-project")
    ap.add_argument("path")
    ap.add_argument("--name", required=True)
    ap.add_argument("--priority", required=True, choices=["high","medium","low"])
    ap.add_argument("--cron", required=True)
    ap.add_argument("--budget-monthly", type=int, required=True)
    ap.add_argument("--budget-per-run", type=int, required=True)
    ap.add_argument("--skill", action="append", default=[])
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args(argv)

    proj = Path(args.path).expanduser().resolve()
    if not (proj / ".git").exists():
        print("not a git repo", file=sys.stderr); return 2
    if not (proj / ".taskmaster").exists():
        if not args.yes:
            print("no .taskmaster; pass --yes to auto-init", file=sys.stderr); return 2
        subprocess.run(["task-master","init","--yes"], cwd=proj, check=True)

    yaml_path = Path(os.environ.get("KIRA_HQ_PROJECTS_YAML", Path.home()/".kira-hq"/"projects.yaml"))
    data = yaml.safe_load(yaml_path.read_text()) or {"version":2,"projects":[]}
    if data.get("version") != 2:
        print("projects.yaml must be v2 — run scripts/migrate_projects_yaml.py", file=sys.stderr); return 2
    if any(p["name"] == args.name for p in data["projects"]):
        print(f"name {args.name!r} already exists", file=sys.stderr); return 2

    data["projects"].append({
        "name": args.name, "path": str(proj), "status": "active",
        "priority": args.priority, "cron": args.cron,
        "added_at": date.today().isoformat(),
        "skills": args.skill,
        "budget_tokens_monthly": args.budget_monthly,
        "budget_tokens_per_run": args.budget_per_run,
        "notes": "",
    })
    yaml_path.write_text(yaml.safe_dump(data, sort_keys=False))

    env = proj / ".env"
    if not env.exists():
        env.write_text("# per-project secrets (see ~/.kira-hq/.env for global)\n")
        env.chmod(0o600)

    shared = Path(os.environ.get("KIRA_HQ_SKILLS_SHARED", Path.home()/".kira-hq"/"skills-shared"))
    skills_dir = proj / ".claude" / "skills"; skills_dir.mkdir(parents=True, exist_ok=True)
    for s in args.skill:
        target = skills_dir / s
        if target.exists() or target.is_symlink(): target.unlink()
        target.symlink_to(shared / s)

    print(f"added {args.name}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

```python
# src/kira_hq/cli/archive_project.py
import argparse, os, sys, yaml
from pathlib import Path

def main(argv):
    ap = argparse.ArgumentParser(prog="kira-hq archive-project")
    ap.add_argument("name")
    a = ap.parse_args(argv)
    y = Path(os.environ.get("KIRA_HQ_PROJECTS_YAML", Path.home()/".kira-hq"/"projects.yaml"))
    data = yaml.safe_load(y.read_text())
    for p in data["projects"]:
        if p["name"] == a.name:
            p["status"] = "archived"
            y.write_text(yaml.safe_dump(data, sort_keys=False))
            print(f"archived {a.name}"); return 0
    print(f"no project named {a.name!r}", file=sys.stderr); return 2

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

```python
# src/kira_hq/cli/main.py
import sys
from kira_hq.cli import add_project, archive_project

USAGE = "kira-hq {add-project|archive-project} [args]"

def main():
    if len(sys.argv) < 2:
        print(USAGE, file=sys.stderr); sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "add-project":       sys.exit(add_project.main(sys.argv[2:]))
    if cmd == "archive-project":   sys.exit(archive_project.main(sys.argv[2:]))
    print(USAGE, file=sys.stderr); sys.exit(2)

if __name__ == "__main__":
    main()
```

Add console script to `pyproject.toml`:
```toml
[project.scripts]
kira-hq = "kira_hq.cli.main:main"
```

- [ ] **Step 4: Write SKILL.md**

```markdown
---
name: kira-add-project
description: Use to onboard a new project into Kira-HQ. Validates git+taskmaster+PRD, updates projects.yaml v2, creates .env, symlinks chosen skills, runs first kanban render.
---

# kira-add-project

Delegates to CLI: `kira-hq add-project <path> --name=... --priority=... --cron=... --budget-monthly=... --budget-per-run=... --skill=... --yes`.

See PRD §6.9 for the 9-step behavior.
```

- [ ] **Step 5: Verify tests pass**

Run: `uv run pytest tests/integration/test_add_project.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/kira_hq/cli/ pyproject.toml tests/integration/test_add_project.py
git commit -m "feat(4.M4,6.9): kira-hq add-project / archive-project CLI"
cd /Users/mariuszkrawczyk/.kira-hq/skills-shared
git add kira-add-project/
git commit -m "feat: kira-add-project SKILL.md"
cd /Users/mariuszkrawczyk/Projects/kira-hq
```

---

### Task 30: Telegram command handler stubs + round-trip test (PRD §4.M4)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/src/kira_hq/telegram_handlers.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/integration/test_telegram_commands.py`

- [ ] **Step 1: Failing test**

```python
# tests/integration/test_telegram_commands.py
from pathlib import Path
import yaml
from kira_hq.telegram_handlers import handle_command

def _ctx(tmp_path: Path) -> dict:
    y = tmp_path / "projects.yaml"
    y.write_text("version: 2\nprojects:\n  - {name: kira-hq, path: /tmp/p, status: active, priority: high, cron: '* * * * *', added_at: 2026-04-16, skills: [], budget_tokens_monthly: 1, budget_tokens_per_run: 1}\n")
    log = tmp_path / "pipeline.log.md"; log.write_text("| ts |\n|-|\n")
    return {"projects_yaml": y, "pipeline_log": log,
            "list_tasks": lambda path: [{"id":"T-1","status":"blocked","priority":"high","title":"x","updated_at":"2026-04-17T00:00:00Z","blocked_by":[]}],
            "add_task": lambda **kw: {"id":"T-99","title":kw["title"]},
            "run_weekly_review": lambda: "weekly-ok"}

def test_status(tmp_path):
    out = handle_command("/status", _ctx(tmp_path))
    assert "kira-hq" in out and "active" in out

def test_blockers(tmp_path):
    out = handle_command("/blockers", _ctx(tmp_path))
    assert "T-1" in out

def test_add(tmp_path):
    out = handle_command("/add kira-hq Write docs", _ctx(tmp_path))
    assert "T-99" in out and "Write docs" in out

def test_fix(tmp_path):
    out = handle_command("/fix kira-hq T-1 retry with jitter", _ctx(tmp_path))
    assert "T-99" in out

def test_review(tmp_path):
    out = handle_command("/review", _ctx(tmp_path))
    assert "weekly-ok" in out

def test_unstale(tmp_path):
    ctx = _ctx(tmp_path)
    data = yaml.safe_load(Path(ctx["projects_yaml"]).read_text())
    data["projects"][0]["status"] = "stale"
    Path(ctx["projects_yaml"]).write_text(yaml.safe_dump(data, sort_keys=False))
    out = handle_command("/unstale kira-hq", ctx)
    assert "active" in out
    assert yaml.safe_load(Path(ctx["projects_yaml"]).read_text())["projects"][0]["status"] == "active"

def test_unknown_returns_help(tmp_path):
    out = handle_command("/wat", _ctx(tmp_path))
    assert "commands" in out.lower()
```

- [ ] **Step 2: Confirm failure**

Run: `uv run pytest tests/integration/test_telegram_commands.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/kira_hq/telegram_handlers.py
import shlex, yaml
from pathlib import Path
from kira_hq.config.projects_yaml import load_projects

HELP = "commands: /status /blockers /add <proj> <title> /fix <proj> <task-id> <note> /review /unstale <proj>"

def handle_command(text: str, ctx: dict) -> str:
    try:
        parts = shlex.split(text)
    except ValueError:
        parts = text.split()
    if not parts: return HELP
    cmd = parts[0]

    if cmd == "/status":
        projects = load_projects(ctx["projects_yaml"])
        return "\n".join(f"{p.name}: {p.status}/{p.priority}" for p in projects)

    if cmd == "/blockers":
        projects = load_projects(ctx["projects_yaml"])
        out = []
        for p in projects:
            for t in ctx["list_tasks"](p.path):
                if t["status"] == "blocked":
                    out.append(f"{p.name}/{t['id']}: {t['title']}")
        return "\n".join(out) or "no blockers"

    if cmd == "/add" and len(parts) >= 3:
        proj, title = parts[1], " ".join(parts[2:])
        path = _path_for(ctx, proj)
        if not path: return f"unknown project {proj}"
        r = ctx["add_task"](project_path=path, title=title, description=title, priority="medium", parent_id=None)
        return f"added {r['id']}: {r['title']}"

    if cmd == "/fix" and len(parts) >= 4:
        proj, parent_id, note = parts[1], parts[2], " ".join(parts[3:])
        path = _path_for(ctx, proj)
        if not path: return f"unknown project {proj}"
        r = ctx["add_task"](project_path=path, title=f"fix: {note}", description=note,
                            priority="high", parent_id=parent_id)
        return f"added {r['id']} under {parent_id}"

    if cmd == "/review":
        return ctx["run_weekly_review"]()

    if cmd == "/unstale" and len(parts) == 2:
        y = Path(ctx["projects_yaml"])
        data = yaml.safe_load(y.read_text())
        for p in data["projects"]:
            if p["name"] == parts[1]:
                p["status"] = "active"
                y.write_text(yaml.safe_dump(data, sort_keys=False))
                return f"{parts[1]} active"
        return f"unknown project {parts[1]}"

    return HELP

def _path_for(ctx, name):
    for p in load_projects(ctx["projects_yaml"]):
        if p.name == name: return p.path
    return None
```

- [ ] **Step 4: Verify**

Run: `uv run pytest tests/integration/test_telegram_commands.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/kira_hq/telegram_handlers.py tests/integration/test_telegram_commands.py
git commit -m "feat(4.M4,6.3): Telegram command handlers /status/blockers/add/fix/review/unstale"
```

---

### Task 31: Parallel-track harness + docs (PRD §6.14)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/docs/PARALLEL_TRACK.md`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/scripts/parallel_track_row.py`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_parallel_track.py`

- [ ] **Step 1: Write failing test**

```python
# tests/smoke/test_parallel_track.py
from pathlib import Path
from kira_hq.skills.parallel_track import weekly_row, ParallelMetrics

def test_weekly_row_formats_markdown():
    row = weekly_row(
        iso_week="2026-W16",
        a=ParallelMetrics(tasks=10, tokens=12000, human_interventions=1, alerts=2, latency_s=4.2),
        b=ParallelMetrics(tasks=9,  tokens=15000, human_interventions=3, alerts=4, latency_s=3.9),
    )
    assert "2026-W16" in row
    assert "| 10 |" in row and "| 9 |" in row
    assert "12000" in row and "15000" in row
```

- [ ] **Step 2: Confirm failure**

Run: `uv run pytest tests/smoke/test_parallel_track.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

```python
# src/kira_hq/skills/parallel_track.py
from dataclasses import dataclass

@dataclass
class ParallelMetrics:
    tasks: int
    tokens: int
    human_interventions: int
    alerts: int
    latency_s: float

HEADER = (
    "| week     | path | tasks | tokens | human_interventions | alerts | latency_s |\n"
    "|----------|------|-------|--------|----------------------|--------|-----------|\n"
)

def weekly_row(iso_week: str, a: ParallelMetrics, b: ParallelMetrics) -> str:
    return (
        f"| {iso_week} | A    | {a.tasks} | {a.tokens} | {a.human_interventions} | {a.alerts} | {a.latency_s:.1f} |\n"
        f"| {iso_week} | B    | {b.tasks} | {b.tokens} | {b.human_interventions} | {b.alerts} | {b.latency_s:.1f} |\n"
    )
```

- [ ] **Step 4: Write PARALLEL_TRACK.md seed**

```markdown
# Parallel track evaluation

Comparing Path A (Hermes cron → skills) vs Path B (Claude Code manual + launchctl) for 2–3 weeks starting 2026-04-16. Final decision recorded in `docs/ADR/0002-orchestrator-decision.md`.

## Weekly comparison

| week     | path | tasks | tokens | human_interventions | alerts | latency_s |
|----------|------|-------|--------|----------------------|--------|-----------|

Append weekly via `kira-weekly-review` which calls `kira_hq.skills.parallel_track.weekly_row`.
```

- [ ] **Step 5: Write CLI wrapper**

```python
# scripts/parallel_track_row.py
#!/usr/bin/env python3
import sys
from kira_hq.skills.parallel_track import ParallelMetrics, weekly_row
# usage: parallel_track_row.py <week> <A.tasks> <A.tokens> <A.hi> <A.alerts> <A.lat> <B.tasks> <B.tokens> <B.hi> <B.alerts> <B.lat>
w = sys.argv[1]
a = ParallelMetrics(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), float(sys.argv[6]))
b = ParallelMetrics(int(sys.argv[7]), int(sys.argv[8]), int(sys.argv[9]), int(sys.argv[10]), float(sys.argv[11]))
print(weekly_row(w, a, b))
```

- [ ] **Step 6: Verify**

Run: `uv run pytest tests/smoke/test_parallel_track.py -v`
Expected: 1 passed.

- [ ] **Step 7: Commit**

```bash
git add src/kira_hq/skills/parallel_track.py docs/PARALLEL_TRACK.md scripts/parallel_track_row.py tests/smoke/test_parallel_track.py
git commit -m "feat(6.14): parallel-track harness — weekly_row + PARALLEL_TRACK.md"
```

---

## Phase E — Cross-cutting hardening (PRD §6.5, §6.15, §6.17)

### Task 32: SECRETS.md + .env scaffolding (PRD §6.5)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/docs/SECRETS.md`
- Modify: `/Users/mariuszkrawczyk/.kira-hq/.env` (create if absent)
- Modify: `/Users/mariuszkrawczyk/Projects/kira-hq/.gitignore`
- Test: `/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_env_schema.sh`

- [ ] **Step 1: Write `docs/SECRETS.md`**

```markdown
# Secrets

## Global: `~/.kira-hq/.env` (chmod 600, gitignored)

```sh
# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHATS=

# Fallback LLMs
OPENROUTER_API_KEY=
MINIMAX_API_KEY=

# GitHub
GITHUB_TOKEN=

# FastAPI
KIRA_HQ_USER=
KIRA_HQ_PASS=
KIRA_HQ_REQUIRE_AUTH=0
```

## Per-project: `~/Projects/<name>/.env`
Loaded AFTER global → overrides. Chmod 600, gitignored.

## Rotation schedule (manual)
| Key                    | Provider          | Last rotated | Next due |
|------------------------|-------------------|--------------|----------|
| TELEGRAM_BOT_TOKEN     | @BotFather        | 2026-04-16   | 2026-10  |
| OPENROUTER_API_KEY     | openrouter.ai     | 2026-04-16   | 2026-10  |
| MINIMAX_API_KEY        | minimax.chat      | 2026-04-16   | 2026-10  |
| GITHUB_TOKEN           | github.com/settings/tokens | 2026-04-16 | 2026-10 |
| KIRA_HQ_PASS           | `openssl rand -base64 24` | 2026-04-16 | 2026-10 |

## Rotation steps per provider
- **Telegram:** /revoke in @BotFather → new token → paste.
- **OpenRouter:** openrouter.ai → Keys → revoke → create → paste.
- **Minimax:** minimax.chat/platform → Keys → revoke → create → paste.
- **GitHub:** github.com/settings/tokens → delete → Generate new (classic, scope: repo) → paste.
- **KIRA_HQ_PASS:** `openssl rand -base64 24` → paste.

Automated rotation is OUT OF SCOPE (PRD §7).
```

- [ ] **Step 2: Create .env scaffold (only if absent)**

```bash
[[ -f /Users/mariuszkrawczyk/.kira-hq/.env ]] || {
  mkdir -p /Users/mariuszkrawczyk/.kira-hq
  cat > /Users/mariuszkrawczyk/.kira-hq/.env <<'EOF'
TELEGRAM_BOT_TOKEN=
TELEGRAM_ALLOWED_CHATS=
OPENROUTER_API_KEY=
MINIMAX_API_KEY=
GITHUB_TOKEN=
KIRA_HQ_USER=
KIRA_HQ_PASS=
KIRA_HQ_REQUIRE_AUTH=0
EOF
  chmod 600 /Users/mariuszkrawczyk/.kira-hq/.env
}
```

- [ ] **Step 3: Update `.gitignore`**

Add lines:
```
/.env
/frontend/.env.local
~/.kira-hq/.env
**/.env
```

- [ ] **Step 4: Write smoke test**

```bash
#!/usr/bin/env bash
# tests/smoke/test_env_schema.sh — verifies .env has the required keys (value optional)
set -euo pipefail
F="$HOME/.kira-hq/.env"
[[ -f "$F" ]] || { echo "missing $F"; exit 1; }
for k in TELEGRAM_BOT_TOKEN TELEGRAM_ALLOWED_CHATS OPENROUTER_API_KEY MINIMAX_API_KEY GITHUB_TOKEN KIRA_HQ_USER KIRA_HQ_PASS; do
  grep -q "^$k=" "$F" || { echo "missing key: $k"; exit 1; }
done
echo PASS
```

- [ ] **Step 5: Run**

```bash
chmod +x /Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_env_schema.sh
/Users/mariuszkrawczyk/Projects/kira-hq/tests/smoke/test_env_schema.sh
```
Expected: `PASS`.

- [ ] **Step 6: Commit**

```bash
git add docs/SECRETS.md .gitignore tests/smoke/test_env_schema.sh
git commit -m "feat(6.5): SECRETS.md + .env schema smoke test + gitignore"
```

---

### Task 33: GitHub Actions CI — pytest + Playwright + shell tests (PRD §6.15)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/.github/workflows/ci.yml`

- [ ] **Step 1: Write workflow**

```yaml
# .github/workflows/ci.yml
name: CI
on:
  push: { branches: [main] }
  pull_request:
  schedule: [{cron: '0 4 * * *'}]   # nightly
jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run pytest tests/smoke tests/integration -v
      - run: bash tests/smoke/test_env_schema.sh
        env:
          HOME: ${{ runner.temp }}
        if: false   # needs .env fixture; skipped in CI (run locally)
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '22' }
      - run: npm ci
        working-directory: frontend
      - run: npm run build
        working-directory: frontend
  e2e:
    runs-on: ubuntu-latest
    needs: [python, frontend]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - uses: actions/setup-node@v4
        with: { node-version: '22' }
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run playwright install --with-deps chromium
      - run: npm ci
        working-directory: frontend
      - run: uv run pytest tests/e2e -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(6.15): GitHub Actions — python, frontend build, Playwright E2E, nightly"
```

---

### Task 34: Module DoD checklist + self-verify script (PRD §6.17)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/scripts/verify_module_dod.sh`

- [ ] **Step 1: Write script**

```bash
#!/usr/bin/env bash
# scripts/verify_module_dod.sh <module-number>
# Prints PASS/FAIL per DoD item from PRD §6.17.
set -u
MOD="${1:?usage: verify_module_dod.sh 1|2|3|4}"
cd "$(dirname "$0")/.."

fail=0
check() { if eval "$2" >/dev/null 2>&1; then echo "PASS: $1"; else echo "FAIL: $1"; fail=1; fi; }

case "$MOD" in
  1)
    check "smoke tests"       "uv run pytest tests/smoke/test_pipeline_log.py tests/smoke/test_needs_attention.py tests/smoke/test_adr_index.py"
    check "integration tests" "uv run pytest tests/integration/test_kanban_with_adrs.py tests/integration/test_orchestrator.py tests/integration/test_snapshot.sh || bash tests/integration/test_snapshot.sh"
    check "e2e test"          "uv run pytest tests/e2e/test_module1_markdown_preview.py"
    check "README exists"     "[ -f src/kira_hq/renderer/README.md ]"
    check "pipeline.log.md"   "[ -f $HOME/.kira-hq/global-pipeline.log.md ]"
    ;;
  2)
    check "smoke tests"       "uv run pytest tests/smoke/test_api_boot.py tests/smoke/test_projects_routes.py tests/smoke/test_add_task.py tests/smoke/test_views.py tests/smoke/test_tokens.py tests/smoke/test_metrics_routes.py tests/smoke/test_auth.py"
    check "integration tests" "uv run pytest tests/integration/test_api_e2e.py"
    check "README exists"     "[ -f src/kira_hq/api/README.md ]"
    check "Postman exists"    "[ -f docs/POSTMAN.json ]"
    ;;
  3)
    check "frontend build"    "cd frontend && npm run build"
    check "e2e test"          "uv run pytest tests/e2e/test_module3_dashboard.py"
    check "README exists"     "[ -f frontend/README.md ]"
    ;;
  4)
    check "smoke tests"       "uv run pytest tests/smoke/test_report.py tests/smoke/test_parallel_track.py"
    check "integration tests" "uv run pytest tests/integration/test_weekly_review.py tests/integration/test_add_project.py tests/integration/test_telegram_commands.py"
    check "shared-skills repo" "[ -d $HOME/.kira-hq/skills-shared/.git ]"
    ;;
  *) echo "unknown module $MOD"; exit 2;;
esac
exit $fail
```

- [ ] **Step 2: Make executable and run for every module**

```bash
chmod +x /Users/mariuszkrawczyk/Projects/kira-hq/scripts/verify_module_dod.sh
for m in 1 2 3 4; do
  /Users/mariuszkrawczyk/Projects/kira-hq/scripts/verify_module_dod.sh "$m" || true
done
```
Expected: each module ends with PASS lines for all DoD items.

- [ ] **Step 3: Commit**

```bash
git add scripts/verify_module_dod.sh
git commit -m "feat(6.17): verify_module_dod.sh — automated DoD checklist per module"
```

---

### Task 35: Top-level README + ADR-0001 (PRD §6.8, §6.17)

**Files:**
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/README.md`
- Create: `/Users/mariuszkrawczyk/Projects/kira-hq/docs/ADR/0001-use-fastapi-not-flask.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# Kira-HQ

Local command center for 10–15 AI-driven projects. See `prd/master-prd.md`.

## Layout
- `src/kira_hq/renderer/` — Module 1 markdown renderer
- `src/kira_hq/api/` — Module 2 FastAPI
- `frontend/` — Module 3 Next.js
- `src/kira_hq/skills/` + `~/.kira-hq/skills-shared/` — Module 4 skills
- `scripts/` — snapshots, migrations, DoD verifier
- `tests/smoke|integration|e2e/` — three-tier test strategy (§6.15)

## Quickstart
```
uv sync
uv run uvicorn kira_hq.api.main:app --host 127.0.0.1 --port 3100 &
cd frontend && NEXT_PUBLIC_KIRA_HQ_API=http://127.0.0.1:3100 npm run dev -- --port 3001
```

## Phases
- ✅ Faza 0, Faza 1 (see `memory/kira_hq_faza_*`)
- ⬅️ Faza 2: Module 1 hardening + cross-cutting + Hermes scaffold + parallel track
- Faza 3: Modules 2+3 localhost
- Faza 4: Hermes full migration + orchestrator decision
- Faza 5: Vercel + second project
```

- [ ] **Step 2: Write ADR-0001**

```markdown
# ADR-0001: Use FastAPI, not Flask

- **Status:** accepted
- **Date:** 2026-04-16

## Context
Module 2 needs a REST API reading taskmaster JSON. Options: Flask, FastAPI, Starlette.

## Decision
FastAPI. Reasons:
- Pydantic v2 request validation out of the box (Task 16 uses `TaskIn`)
- ASGI enables future streaming (SSE for live kanban updates)
- TestClient built on httpx — same client used throughout tests

## Consequences
- + Typed models, automatic OpenAPI docs at `/docs`
- + Native async for future integrations
- − Extra dependency (uvicorn, starlette) — acceptable
```

- [ ] **Step 3: Commit**

```bash
mkdir -p /Users/mariuszkrawczyk/Projects/kira-hq/docs/ADR
git add README.md docs/ADR/0001-use-fastapi-not-flask.md
git commit -m "docs(6.8,6.17): top-level README + ADR-0001"
```

---

### Task 36: Self-review pass (PRD §7, §8, §9, §6.16 missing)

**Files:**
- Modify: plan.md (this document) — add coverage-self-review.md separately

- [ ] **Step 1: Run the coverage self-review**

See `coverage-self-review.md` — explicit PRD-section → Task mapping. Gaps flagged there.

- [ ] **Step 2: Note: PRD §6.16 does NOT exist**

PRD §6 jumps from 6.15 to 6.17. This is a gap in the PRD itself (see `coverage-self-review.md` for the finding). No plan task needed.

- [ ] **Step 3: Out-of-scope explicit acknowledgment**

From PRD §7:
- Multi-machine sync — OUT OF SCOPE (no task)
- Multi-tenant — OUT OF SCOPE (no task)
- Perf benchmarks — OUT OF SCOPE (no task)
- Public UI — OUT OF SCOPE (no task)
- Automated secrets rotation — OUT OF SCOPE — Task 32 documents manual rotation only
- Skill-tag pinning — OUT OF SCOPE — Task 26 README acknowledges this

- [ ] **Step 4: Open questions from PRD §8 — capture in ADRs (proposed)**

Create placeholders so they're not forgotten:

```bash
cat > /Users/mariuszkrawczyk/Projects/kira-hq/docs/ADR/0003-hermes-install.md <<'EOF'
# ADR-0003: Hermes install path (TBD — tracking open question)

- **Status:** proposed
- **Date:** 2026-04-16

## Context
PRD §8.1 lists two options for Hermes install: official installer vs `git clone`. Must resolve before Faza 3.

## Decision
(pending — tracked as open question)

## Consequences
Kept as proposed until Faza 3 kickoff. Weekly review (§6.18) prompts revisit.
EOF

cat > /Users/mariuszkrawczyk/Projects/kira-hq/docs/ADR/0004-vercel-auth.md <<'EOF'
# ADR-0004: Vercel auth strategy (TBD)

- **Status:** proposed
- **Date:** 2026-04-16

## Context
PRD §8.2 asks whether HTTP Basic is OK when Module 3 deploys to Vercel, or OAuth is required. Current code supports Basic only (Task 19).

## Decision
(pending — decide at Faza 5 kickoff)
EOF

cat > /Users/mariuszkrawczyk/Projects/kira-hq/docs/ADR/0005-monopilot-prd-decomposer.md <<'EOF'
# ADR-0005: MonoPilot PRD decomposition path (TBD)

- **Status:** proposed
- **Date:** 2026-04-16

## Context
PRD §8.3: when MonoPilot PRD is ready, who decomposes it? Likely winner from PRD-decomposition benchmark. This plan itself is benchmark approach B.

## Decision
(pending — driven by benchmark outcome)
EOF
```

- [ ] **Step 5: Commit**

```bash
git add docs/ADR/0003-hermes-install.md docs/ADR/0004-vercel-auth.md docs/ADR/0005-monopilot-prd-decomposer.md
git commit -m "docs(§8): track PRD open questions as proposed ADRs 0003-0005"
```

---

## Self-Review

See companion file `coverage-self-review.md` for the full PRD-section → Task mapping table and gap analysis.

### Placeholder scan (done inline)
- No "TBD" in implementation steps — where present (ADR 0003–0005) it reflects PRD §8 open questions by design.
- No "appropriate validation", "handle edge cases" without code.
- Every Python/TS/bash code step contains full code.
- No "similar to Task N" — repeated patterns (pytest structure, commit blocks) written out each time.

### Type consistency check (done inline)
- `Project` dataclass fields consistent across Tasks 2, 15, 17, 29.
- `PipelineEntry` field names match between Tasks 3, 6, 18.
- API route prefixes: `/views/*` (Task 17), `/metrics/*` (Task 18), `/projects` & `/projects/{name}/tasks` (Tasks 15–16). No collisions.
- `set_config(projects_yaml=..., pipeline_log=...)` signature extended additively in Task 18 (keyword-only, backward compatible).
- `_CONFIG` dict shared between `routes/projects.py` (Task 15) and `routes/tasks.py` (Task 16) and `routes/views.py` (Task 17) — imports match.
- Playwright `data-testid=task-card` / `data-testid=task-detail` used in Task 22 and asserted in Task 24 — names match.
- Pipeline log row regex `ROW` in `tokens/aggregate.py` matches header+row format produced by `append_entry` in Task 3 — verified.

---

## Execution Handoff

Plan complete and saved to `/Users/mariuszkrawczyk/Projects/kira-hq/benchmark/B-writing-plans/plan.md`.

Two execution options:
1. **Subagent-Driven (recommended)** — dispatch fresh subagent per task, review between.
2. **Inline Execution** — batch run with checkpoints.

Recommended: Subagent-Driven, starting at Task 1 (pin SDKs + workaround smoke) and proceeding sequentially. Tasks 1–12 complete Faza 2 Module 1 hardening; 13–20 complete Faza 3 Module 2; 21–25 complete Faza 3 Module 3; 26–31 complete Faza 4 Module 4; 32–36 finalize cross-cutting.
