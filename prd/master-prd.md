# Kira-HQ — Product Requirements Document

**Version:** 2.0
**Last updated:** 2026-04-16
**Owner:** Mariusz (solo)

---

## 1. Vision

Kira-HQ is a **command center for managing 10–15 AI-driven projects in parallel**, running 24/7 on a local Mac M4. Each project owns its pipeline (Taskmaster + skills + cron). Kira-HQ aggregates state into one dashboard, surfaces what needs human attention cross-project, and exposes both data and views to a higher-level orchestrator (Hermes).

Kira-HQ is **not** an executor. It is the *project manager*. **Hermes is the orchestrator/executor**. Both run in parallel during Faza 2 to validate which produces better outcomes; final ownership decided by data.

## 2. Users

- **Primary:** Mariusz, solo owner-operator
- **Usage pattern:** 24/7 local server on Mac M4; user reviews dashboard mornings + responds to Telegram alerts during day
- **Scale assumption:** 10–15 projects max (no horizontal scaling concerns)

## 3. Architecture (high level)

```
┌─────────────────────────────────────────────────────────────┐
│  HERMES (orchestrator, executor)                            │
│  - cron scheduler                                           │
│  - agent invocation (Claude OAuth, OpenRouter fallback)    │
│  - Telegram gateway (in/out)                                │
│  - autolearn / memory                                       │
└────────────┬────────────────────────────────────────────────┘
             │ invokes skills, reads/writes API
             ▼
┌─────────────────────────────────────────────────────────────┐
│  KIRA-HQ (project manager, data + views)                    │
│  - Module 1: Markdown renderer (kanban_board.md per proj)   │
│  - Module 2: FastAPI backend (state API)                    │
│  - Module 3: Next.js frontend (dashboard)                   │
│  - Module 4: Hermes integration (skills + commands)         │
│  - Cross-cutting: logs, secrets, backups, ADRs, etc.        │
└────────────┬────────────────────────────────────────────────┘
             │ reads tasks.json, projects.yaml
             ▼
┌─────────────────────────────────────────────────────────────┐
│  PROJECTS (~/Projects/<name>/)                              │
│  - .taskmaster/tasks.json (source of truth per project)     │
│  - .claude/skills/ → symlinks to ~/.kira-hq/skills-shared/  │
│  - prd/master-prd.md + prd/modules/                         │
└─────────────────────────────────────────────────────────────┘
```

**Parallel track decision (2026-04-16):** Faza 2 builds Hermes + Claude Code execution paths simultaneously. Each Friday for 2–3 weeks, weekly review compares: tasks completed, tokens spent, human interventions required. Data-driven decision on primary executor.

---

## 4. Modules

### Module 1: Markdown Renderer

**What:** Python script reads `~/.kira-hq/projects.yaml`, calls `task-master list --json` per project, generates `kanban_board.md` per project + global `~/.kira-hq/global-kanban.md` + `needs-attention.md`.

**Status:** Faza 1 done (smoke + e2e passed, 6 tasks rendered).

**Definition of Done:**
- Smoke test passes (single project, fake tasks.json)
- Integration test passes (multi-project, real tasks.json)
- E2E browser test: open `kanban_board.md` in Markdown preview, verify task count matches `task-master list` count (10 tasks in JSON → 10 entries rendered)
- `README.md` documents inputs, outputs, error modes
- Pipeline log entry created on every run

### Module 2: FastAPI Backend

**What:** REST API over project state. Reads tasks.json via `task-master list --json` subprocess.

**Endpoints (v1):**
- `GET /projects` — list all from projects.yaml + status summary
- `GET /projects/{name}/tasks` — task list, filter by status/priority
- `GET /views/needs-attention` — algorithm output (see §6.10)
- `GET /views/blockers` — only `status: blocked` tasks across projects
- `POST /projects/{name}/tasks` — add task or fix; payload: `{title, description, priority, parent_id?}`
- `GET /metrics/tokens` — token usage aggregates (daily/weekly per project)

**Hosting:** `uvicorn --host 127.0.0.1 --port 3100` (port 3100 verified free 2026-04-16; OpenClaw fully removed).

**Auth:** Localhost-only = no auth needed locally. When exposed (Tailscale/Vercel later), HTTP Basic Auth via FastAPI `HTTPBasic()` dependency, credentials in `~/.kira-hq/.env` (`KIRA_HQ_USER`, `KIRA_HQ_PASS`). Rationale: simplest possible auth that works.

**Definition of Done:** smoke (each endpoint returns 200 on fixture) + integration (real projects.yaml) + E2E browser (curl + Postman collection in `docs/`) + README.

### Module 3: Next.js Frontend

**What:** Dashboard UI. Pages: project list, project detail (kanban view), cross-project needs-attention view, blockers view, add task/fix form, embedded iframe for Hermes dashboard.

**Hosting strategy:**
1. **Phase 3a:** `localhost:3001` (Next.js dev server, calls FastAPI at `localhost:3100`)
2. **Phase 3b:** Vercel deploy (only after 3a stable for ≥1 week). Auth = same HTTP Basic via env vars.

**Definition of Done:** smoke (pages render with mock data) + integration (real API) + E2E browser (Playwright: load tasks.json with 10 tasks, navigate to project page, assert 10 task cards visible, click one, assert detail panel matches JSON) + docs.

### Module 4: Hermes Integration

**What:** Skills callable by Hermes + Telegram command handlers + parallel-track scaffold.

**Skills (in `~/.hermes/skills/` via symlink to `~/.kira-hq/skills-shared/`):**
- `kira-hq-render-kanban` — runs renderer (already exists, Faza 1)
- `kira-hq-report` — generates summary for cron post-cycle (changes since last run, blockers, alerts)
- `kira-weekly-review` — weekly aggregate (Saturday 9:00 cron): tokens used, tasks completed, blockers count, parallel-track comparison
- `kira-add-project` — `kira-hq add-project <path>` CLI/skill: validates repo, dops to projects.yaml v2

**Telegram commands (via Hermes gateway):**
- `/status` — global summary
- `/blockers` — list active blockers
- `/add <project> <title>` — add task
- `/fix <project> <task-id> <note>` — add fix sub-task
- `/review` — trigger kira-weekly-review on demand

**Definition of Done:** each skill smoke + each Telegram command tested round-trip + parallel-track skill harness present + README.

---

## 5. Phases (high-level)

- **Faza 0** ✅ (2026-04-16) — Homebrew, Python 3.12, Node 22, uv, task-master, MCP servers, ~/.kira-hq/
- **Faza 1** ✅ (2026-04-16) — Kira-HQ skeleton + Module 1 markdown renderer + 6 taskmaster tasks
- **Faza 2** ⬅️ NEXT — Module 1 production-ready + cross-cutting (§6) + Hermes integration scaffold + parallel track
- **Faza 3** — Modules 2 (FastAPI) + 3 (Next.js localhost)
- **Faza 4** — Hermes v0.10 install + migration. **Uses Native Anthropic Provider (Addendum §5)** — auto-discovery from Claude Code OAuth credentials, NOT the manual OAuth flow from KIRA_HQ_IMPLEMENTATION_PLAN.md §8.3 (outdated for v0.10). Prompt caching native. Smart Approvals: `strict` → `smart` after 1 week. Plus parallel-track decision.
- **Faza 5** — Vercel deploy Module 3 + add real second project (e.g. MonoPilot when PRD ready)

---

## 6. Cross-cutting concerns (NEW — must be addressed in Faza 2)

These apply across all modules. Each is a deliverable, not a vague principle.

### 6.1 Pipeline log schema

**File:** `~/Projects/<project>/pipeline.log.md` (per project) + `~/.kira-hq/global-pipeline.log.md` (aggregate, append-only)

**Format (markdown table, one row per skill invocation):**

```markdown
| timestamp           | project   | skill                  | provider | expand_used | tokens_in | tokens_out | status | duration_s | notes              |
|---------------------|-----------|------------------------|----------|-------------|-----------|------------|--------|------------|--------------------|
| 2026-04-17T03:00:12 | kira-hq   | kira-hq-render-kanban  | sonnet   | false       | 0         | 0          | ok     | 1.2        | 6 tasks rendered   |
| 2026-04-17T03:01:05 | monopilot | monopilot-night-crew   | sonnet   | false       | 12450     | 3201       | ok     | 47.3       | task #5 → reviewed |
| 2026-04-17T04:00:08 | kira-hq   | kira-weekly-review     | kimi-2.6 | true        | 8200      | 1100       | ok     | 28.0       | expanded to 5 sub  |
```

Renderer appends; Kira-HQ Module 2 exposes via `GET /metrics/pipeline?since=...`.

### 6.2 Token tracking (NOT cost)

Per user decision: track `tokens_in` and `tokens_out`, NOT $ cost. OAuth Claude Max is unmetered for the user, but tokens still indicate where compute is going.

**Aggregation:**
- Daily roll-up in `~/.kira-hq/metrics/tokens-YYYY-MM-DD.json`
- Weekly report (kira-weekly-review skill) shows top-3 token-consuming projects
- Optional alert via Telegram if a single skill run exceeds `budget_tokens_per_run` from projects.yaml v2

### 6.3 Cron failure handling

**Policy:**
1. Skill fails (non-zero exit OR exception) → retry once after 60s
2. Second failure → log to pipeline.log with `status: fail` + write to `~/.kira-hq/incidents/<timestamp>-<project>.md` with full context (stderr, last 50 lines stdout)
3. Send Telegram alert: `🔴 <project>/<skill> failed twice. See incident <id>.`
4. Mark project `status: stale` in projects.yaml until human ack via `/unstale <project>` Telegram command
5. Stale projects skipped by subsequent cron runs (prevents alert storms)

### 6.4 SDK pinning + smoke test for taskmaster workaround

**Problem:** `claude-agent-sdk` RangeError in nested Claude sessions (workaround in `~/.zshrc` env-stripping wrapper, see Faza 1 memory).

**Mitigation:**
- Pin `task-master-ai` and `@anthropic-ai/claude-agent-sdk` versions in a `versions.lock.md` doc with last-known-good
- Smoke test `tests/test_taskmaster_workaround.sh`:
  - Runs `task-master list` from a child shell with `CLAUDECODE=1` simulated → expects exit 0
  - Runs same without wrapper → expects crash (proves wrapper is necessary, prevents accidental removal)
- Run on every cron cycle of Kira-HQ (cheap, <1s) + on demand
- If smoke fails → Telegram alert + halt all cron until ack

### 6.5 Secrets schema

**File:** `~/.kira-hq/.env` (chmod 600, gitignored everywhere)

**Schema:**
```sh
# === Telegram (Hermes gateway) ===
TELEGRAM_BOT_TOKEN=...
TELEGRAM_ALLOWED_CHATS=123456789,987654321  # comma-separated chat IDs

# === Fallback LLM (when Claude OAuth rate-limits) ===
OPENROUTER_API_KEY=sk-or-v1-...
MINIMAX_API_KEY=...

# === GitHub (for kira-hq Pages auto-commit + future PR automation) ===
GITHUB_TOKEN=ghp_...

# === Kira-HQ FastAPI auth (when exposed beyond localhost) ===
KIRA_HQ_USER=mariusz
KIRA_HQ_PASS=...  # generate with: openssl rand -base64 24

# === Optional: per-project budget overrides ===
# Use ~/Projects/<name>/.env for project-specific secrets/limits
```

**Per-project override:** `~/Projects/<name>/.env` (also gitignored). Loaded second, takes precedence over `~/.kira-hq/.env` for project-scoped runs.

**No rotation automation in v2.** Documented in `docs/SECRETS.md`: rotation steps per provider, last-rotated dates table.

### 6.6 projects.yaml v2 schema

```yaml
version: 2
projects:
  - name: kira-hq
    path: ~/Projects/kira-hq
    status: active             # active | stale | archived
    priority: high             # high | medium | low
    cron: "0 */2 * * *"        # standard cron syntax
    added_at: 2026-04-16
    skills:                    # which shared skills this project uses
      - kira-hq-render-kanban
      - kira-weekly-review
    budget_tokens_monthly: 500000
    budget_tokens_per_run: 50000
    notes: "Self-managing; serves as reference project."

  - name: monopilot
    path: ~/Projects/monopilot
    status: active
    priority: high
    cron: "0 */1 * * *"
    added_at: 2026-04-XX
    skills:
      - monopilot-night-crew
      - kira-hq-render-kanban
    budget_tokens_monthly: 2000000
    budget_tokens_per_run: 100000
```

**Migration:** v1 → v2 handled by `scripts/migrate_projects_yaml.py` (idempotent: detects v1 by missing `version` field, fills defaults).

### 6.7 Backup policy

**Source of truth:** `.taskmaster/tasks.json` per project.

**Strategy:**
- **kira-hq:** already auto-commits to GitHub Pages every 10 min — counts as continuous backup
- **All projects (incl. kira-hq):** daily 03:00 cron (`scripts/snapshot.sh`):
  - `rsync -a --link-dest=<yesterday> ~/Projects/*/.taskmaster/ ~/.kira-hq/snapshots/$(date +%F)/`
  - Hardlinks deduplicate unchanged files → ~MB total per week
  - Rolling 7-day window: delete `~/.kira-hq/snapshots/<oldest>` if >7 directories
- **Disaster recovery:** `scripts/restore_snapshot.sh <project> <date>` → restores `.taskmaster/` from snapshot to project dir (with safety prompt)

**Verification:** weekly review skill checks: did snapshot run successfully each day? Alert if 2+ missed.

### 6.8 ADR convention

**Location:** `~/Projects/<project>/docs/ADR/`

**Naming:** `NNNN-kebab-title.md` (zero-padded, e.g. `0001-use-fastapi-not-flask.md`)

**Template:** `~/.kira-hq/templates/ADR.md` — sections: Context, Decision, Consequences, Date, Status (proposed/accepted/superseded).

**Index:** `scripts/render_adr_index.py` generates `docs/ADR/INDEX.md` per project + `~/.kira-hq/global-adrs.md`. Renderer (Module 1) includes ADR section in `kanban_board.md` (last 5 ADRs).

### 6.9 `kira-hq add-project` command

**Invocation:** `kira-hq add-project <path>` (CLI wrapper) or skill `kira-add-project` (Hermes/Claude).

**Behavior:**
1. Validate path exists + is git repo + has `.taskmaster/` (or offer to `task-master init`)
2. Validate `prd/master-prd.md` exists (or warn)
3. Check name unique in `projects.yaml`
4. Prompt for: priority, cron schedule, budget_tokens_monthly, skills to enable
5. Append to `projects.yaml v2` with `added_at: <today>`
6. Create `~/Projects/<name>/.env` skeleton (chmod 600)
7. Symlink chosen skills into `<path>/.claude/skills/`
8. Run `kira-hq-render-kanban` once to generate first kanban
9. Print summary

**Inverse:** `kira-hq archive-project <name>` — sets `status: archived`, stops cron, keeps in projects.yaml for history (does NOT delete files).

### 6.10 needs-attention algorithm

**Trigger conditions** (any of):
1. Task `status: blocked` for >48h (compute from task `updated_at`)
2. Task `priority: high` AND `status: pending` for >72h
3. Task `status: needs-human` (set by skill when retries exhausted)
4. Project has any failed cron run in last 24h (from pipeline.log)
5. Token budget exceeded: project's last 30d tokens > `budget_tokens_monthly`

**Output (`~/.kira-hq/needs-attention.md`):**
```markdown
# Needs Attention — generated 2026-04-17T08:00:00

## 🔴 Blocked >48h (3)
- monopilot/T-12 "Setup Stripe webhook" — blocked by T-08, 67h
- ...

## 🟠 High-prio stale >72h (2)
- ...

## 🚨 Failed crons (1)
- monopilot/monopilot-night-crew at 2026-04-17T03:00 — see incident 2026-04-17T030014
```

### 6.11 Shared skills library

**Location:** `~/.kira-hq/skills-shared/` — own git repo (init in Faza 2, push to private GitHub).

**Structure:**
```
~/.kira-hq/skills-shared/
├── .git/
├── README.md
├── kira-hq-render-kanban/SKILL.md
├── kira-hq-report/SKILL.md
├── kira-weekly-review/SKILL.md
├── kira-add-project/SKILL.md
└── monopilot-night-crew/SKILL.md   # added when monopilot onboards
```

**Distribution:**
- Per project: `~/Projects/<name>/.claude/skills/<skill>` → symlink to `~/.kira-hq/skills-shared/<skill>`
- Hermes: `~/.hermes/skills/<skill>` → same symlink target
- Versioning: git tag `v<major>.<minor>` on the shared repo; projects.yaml v2 may pin a tag (future, not v2.0)

**Rationale:** single source of truth, edits propagate everywhere instantly, git history per skill, future upgrade path via tag pinning. Aligns with existing plan §8.5.

### 6.12 FastAPI auth (already covered §4 Module 2)

Decision: localhost-only first, HTTP Basic when exposed. No JWT, no OAuth, no session cookies until use case demands.

### 6.13 Next.js localhost-first (already covered §4 Module 3)

Decision: `localhost:3001` for ≥1 week before any Vercel deploy.

### 6.14 Hermes orchestrator role + parallel track

**Architectural truth:** Hermes is the orchestrator (cron, agent execution, Telegram). Kira-HQ is the project manager (data, views, decision support). Both already exist in plan §8 (Faza 4 covers Hermes install).

**Re-sequencing for parallel track:**
- Faza 2 runs Module 1 (Kira-HQ data layer) **and** scaffolds Hermes skills simultaneously
- For 2–3 weeks both paths run side-by-side:
  - **Path A (Hermes):** cron in `~/.hermes/scheduler` invokes skills, posts to Telegram
  - **Path B (Claude Code):** user manually triggers `claude /run kira-hq-render-kanban`, also a cron via `launchctl` (no Hermes)
- Weekly review skill compares: tasks completed each path, tokens, human interventions, alert noise, latency
- After 2–3 weeks: data-driven decision on which path becomes primary; the other either (a) deprecated, or (b) kept as backup

**Docs:** `docs/PARALLEL_TRACK.md` records weekly comparison data; `docs/ADR/0003-orchestrator-decision.md` captures final choice with rationale.

### 6.15 Test strategy

Three tiers, every module gets all three:

1. **Smoke tests** (`tests/smoke/`): single function, fake inputs, assert no crash + basic shape. Runs <1s.
2. **Integration tests** (`tests/integration/`): real projects.yaml, real `.taskmaster/`, asserts data flow end-to-end.
3. **E2E browser tests** (`tests/e2e/`): Playwright. Example test for Module 3:
   ```
   - Setup: create fixture project with 10 tasks in tasks.json
   - Open localhost:3001/projects/fixture
   - Assert: 10 task cards visible
   - Click first card
   - Assert: detail panel shows title matching tasks.json[0].title
   - Modify tasks.json (add 11th task)
   - Refresh page
   - Assert: 11 task cards visible
   ```

**CI:** GitHub Actions on every push to `main` + nightly.

### 6.16 Execution policy: provider-aware task expansion

**Problem:** Tasks are sized for Sonnet/Opus class models (~7 atomic steps per task, full plan.md as reference). Weaker models (Kimi 2.6, Haiku, OpenRouter fallbacks) have lower effective context and higher hallucination rates on multi-step work.

**Policy:** Before executing a task, the executor checks the active provider and decides granularity:

| Provider class                     | Granularity     | Action                                           |
|------------------------------------|-----------------|--------------------------------------------------|
| Opus / Sonnet 4.6+                 | parent task     | Execute full task (~7 steps) in one session     |
| Haiku 4.5+                         | parent task     | Execute full task with reminder to consult plan.md |
| Kimi 2.6 / Sonnet 4.5 / weaker     | subtasks        | First `task-master expand --id=N --num=auto`, then execute subtasks one by one |
| OpenRouter fallback (any)          | subtasks        | Always expand (defensive — fallback signals stress) |

**Execution layer routing (Pattern B — per Addendum §15.3):**

In addition to provider class, the wrapper decides **execution layer**:

| Task needs                                                 | Layer             | Why                                       |
|------------------------------------------------------------|-------------------|-------------------------------------------|
| Multi-file edit, Playwright MCP, Codex plugin, Explore sub | Claude Code       | Native tooling + Max subscription         |
| Long-form reasoning (Opus Tier 3 review, PRD decomposition) | Claude Code       | Max OAuth, deep context                   |
| Single LLM call, batch processing, cheap models (GLM/MiniMax) | Hermes subagent   | No Claude Code overhead, explicit model choice |
| Local model (Qwen3-Coder Tier 1 review)                    | Hermes subagent   | Via llama-server localhost:8127           |
| Telegram delivery, cron-triggered                          | Hermes subagent   | Hermes owns the gateway + scheduler       |

**Rule:** default to Hermes subagent for tasks with 1 LLM call. Escalate to Claude Code when task requires tool orchestration.

**Implementation:**

1. **Skill `kira-hq-execute`** (in shared skills library) — wrapper around task execution:
   ```
   1. Read task ID from cron context or CLI arg
   2. Detect active provider (env var KIRA_HQ_PROVIDER, defaults from Hermes config)
   3. Lookup provider class in policy table (above)
   4. If "subtasks" class: run `task-master expand --id=<N>` (idempotent — skips if already expanded)
   5. Get tasks to execute: parent (if "parent task") OR all subtasks of N (if "subtasks")
   6. For each: dispatch to Claude with skill, plan.md path, task details
   7. Update status after each
   ```

2. **Auto-expand from plan.md:** the `prd-decompose-hybrid` skill embeds 165 atomic steps in plan.md. When `task-master expand` is called, the wrapper reads plan.md for the corresponding parent task and emits one subtask per step (so subtasks contain the actual code from the plan, not LLM-regenerated content). This eliminates the typical `task-master expand` weakness of subtasks drifting from parent intent.

3. **Hermes integration:** Hermes cron jobs invoke `kira-hq-execute` instead of raw Claude calls. Hermes provides provider info via env. Hermes's autolearn observes which provider class succeeds for which task type → policy refines over time.

**Failure mode handling:**
- If parent-task execution fails twice (per §6.3 retry policy) → automatically demote to subtask granularity for retry #3 before alerting human
- Logged in pipeline.log: `expand_used: true|false` column added to schema (§6.1)

**Why this matters:** Without this policy, weak providers either (a) fail silently producing partial work, or (b) over-consume tokens re-establishing context every step. With this policy, granularity matches provider capacity → reliable execution across the model spectrum.

### 6.17 Definition of Done per module

A module is **done** when ALL of the following are true:

1. ✅ All planned features implemented (per module §4)
2. ✅ Smoke tests pass
3. ✅ Integration tests pass
4. ✅ E2E browser test pass (front-end check: data in tasks.json matches what's visible in UI; e.g. 10 tasks in JSON → 10 visible in browser → click works → detail matches)
5. ✅ `README.md` documents inputs/outputs/error modes
6. ✅ Pipeline log entries flow correctly during normal use

**No partial-done.** A module is either done or in-progress. No "done with TODOs."

### 6.18 Weekly review ritual

**Skill:** `kira-weekly-review` (in shared library)

**Trigger:** Hermes cron Saturday 09:00 (also manual via Telegram `/review`)

**Output:** `~/.kira-hq/reviews/YYYY-WW.md` + Telegram message

**Contents:**
- Tasks: completed this week per project, blockers count, needs-human count
- Tokens: total per project, top-3 consumers, week-over-week delta
- Cron: success rate per project, failed runs list
- Parallel track (during Faza 2 evaluation period): Path A vs Path B comparison table
- Snapshot health: was daily snapshot run all 7 days?
- Stale projects: list + suggested action
- Hermes autolearn delta: what new patterns Hermes added to its memory this week (if Hermes provides API for this)

**Why important:** Hermes has autolearn → user wants the full feedback loop running through Hermes so its memory grows from real Kira-HQ operations, not just synthetic prompts.

---

### 6.19 Token economics — output discipline

**Origin:** Addendum §17. Output tokens cost 3–5× input tokens on every top-tier model. Naive `rewrite-whole-file` patterns produce ~20× more output tokens than `edit_file` patches. Prompt caching cuts repeated input by ~75–90%. Combined savings: **up to 20×** per task.

**Mandatory rules for every writer/reviewer skill:**

#### For writer skills (creates/modifies code)

1. **Use `edit_file` tool** for modifications. Do NOT regenerate file content when patching.
2. **When to create vs edit:**
   | Case                                   | Action                   |
   |----------------------------------------|--------------------------|
   | New file per requirement               | `create_file`            |
   | Add field/method/import to existing    | `edit_file` (patches)    |
   | Refactor touching >80% of file         | `create_file` (rewrite)  |
   | Refactor touching <80%                 | `edit_file` patches      |
   | Style/formatting only                  | Run formatter; no LLM    |
3. **Output budget:** target <500 output tokens per task. Flag at >2000 → task likely too large, split it.
4. **Red flags (stop immediately):** typing a line that already exists, copying imports unchanged, regenerating function body that doesn't change, writing "// unchanged" comments.

#### For reviewer skills

1. **Input context:** `git diff` only (changed lines + 10-line context per hunk) + related file signatures (imports + function sigs, NO bodies).
2. **Forbidden input:** full unchanged files, entire test suites, build logs (unless debugging build failure), package manifests (unless dep changed).
3. **Output format (strict):**
   ```
   ---
   status: pass | fix
   attempts: <N>
   issues_critical: <count>
   issues_major: <count>
   issues_minor: <count>
   ---

   ## Critical
   - file.ts:42 — <1-line>. Fix: <1-line>.
   ```
4. **Max 500 output tokens.** No code citations — use `file:line` references only.

#### Prompt caching (automatic — Hermes v0.7+ + Claude Code)

Enabled natively. What's cached:
- System prompt (frozen at session start)
- CLAUDE.md / `.hermes.md`
- Loaded skills
- Memory files

**Rule:** keep CLAUDE.md stable. Frequent edits rupture cache hit rate. Monitor `cache_hit_rate` target ≥70%.

#### Tiered review policy (reduces Opus usage)

| Tier | Trigger                                   | Model/Layer                                  |
|------|-------------------------------------------|----------------------------------------------|
| 1    | Diff ≤100 lines, no business logic        | Qwen3-Coder local (Hermes subagent)          |
| 2    | Diff ≤500 lines, standard changes         | Sonnet 4.6 cached (Claude Code)              |
| 3    | Architecture / cross-module changes       | Opus 4.6 (Claude Code)                       |

Workflow generates diff + classifies tier before dispatching reviewer. Never send full files to reviewer.

#### Metrics to monitor (weekly review skill §6.18 includes these)

- Output tokens per skill, trend malejący
- Cache hit rate ≥70%
- Cost/tokens per task per project, month-over-month delta

**DoD for writer/reviewer skills:** section "Output discipline" present + smoke test verifies `edit_file` used (not `write_file`) for a known modification scenario.

## 7. Out of scope (v2.0)

- Multi-machine sync (single Mac M4 only)
- Multi-tenant / multi-user (solo)
- Performance benchmarks (10–15 projects max, no scale concerns)
- Public-facing UI (private use)
- Automated secrets rotation
- Skill-tag pinning per project (future, not v2.0)

---

## 8. Open questions (must resolve before Faza 3)

1. Hermes install path: official installer vs git clone? (plan §8.1 lists both)
2. Vercel deploy: which auth strategy when public? (HTTP Basic OK or need OAuth?)
3. MonoPilot PRD: when ready, who decomposes — Kira-HQ skill or manual? (probably the winning approach from PRD-decomposition benchmark, see Faza 2)

---

## 9. Module → Cross-cutting matrix

Quick reference: which §6 items apply to which module.

| Module           | 6.1 log | 6.2 tokens | 6.3 retry | 6.4 SDK | 6.5 secrets | 6.6 yaml | 6.7 backup | 6.8 ADR | 6.9 add | 6.10 needs | 6.11 skills | 6.14 herm | 6.15 test | 6.16 expand | 6.17 DoD | 6.18 review | 6.19 tok |
|------------------|---------|------------|-----------|---------|-------------|----------|------------|---------|---------|------------|-------------|-----------|-----------|-------------|----------|-------------|----------|
| 1 Renderer       | ✅      | ✅         | ✅        | ✅      | —           | ✅       | ✅         | ✅      | ✅      | ✅         | ✅          | ✅        | ✅        | ✅          | ✅       | ✅          | —        |
| 2 FastAPI        | ✅      | ✅         | —         | ✅      | ✅          | ✅       | —          | ✅      | —       | ✅         | —           | ✅        | ✅        | ✅          | ✅       | ✅          | ✅       |
| 3 Next.js        | —       | —          | —         | —       | ✅          | —        | —          | ✅      | —       | ✅         | —           | —         | ✅        | —           | ✅       | ✅          | ✅       |
| 4 Hermes integ.  | ✅      | ✅         | ✅        | ✅      | ✅          | ✅       | —          | ✅      | ✅      | ✅         | ✅          | ✅        | ✅        | ✅          | ✅       | ✅          | ✅       |

---

**End of PRD v2.0**
