# Kira-HQ v2.0 — Implementation Plan (Hybrid Decomposition)

**Source PRD:** `/Users/mariuszkrawczyk/Projects/kira-hq/prd/master-prd.md` (v2.0, 2026-04-16)
**Generated:** 2026-04-16 (Approach C — prd-decompose-hybrid benchmark)
**Total tasks:** 24
**Phases covered:** Faza 2 → Faza 5 (Faza 0/1 already done per §5)

---

## Coverage worksheet (built BEFORE task writing)

| PRD ref              | Content (≤80 chars)                                             | task_id    |
|----------------------|-----------------------------------------------------------------|------------|
| §1 Vision            | Command center for 10–15 AI projects; not executor              | T-23       |
| §2 Users             | Solo Mariusz; 24/7 Mac M4; 10–15 projects max                   | T-23       |
| §3 Architecture      | Hermes vs Kira-HQ roles; parallel track decision                | T-22       |
| §4 M1 Renderer       | projects.yaml → per-project kanban + global + needs-attention   | T-8        |
| §4 M1 DoD            | Smoke + integration + E2E browser + README + pipeline log       | T-8, T-23  |
| §4 M2 Endpoints      | GET /projects, /tasks, /views/*, POST tasks, /metrics/tokens    | T-16       |
| §4 M2 Hosting        | uvicorn 127.0.0.1:3100 (port verified free)                     | T-16       |
| §4 M2 Auth           | Localhost-no-auth; HTTPBasic when exposed                        | T-17       |
| §4 M2 DoD            | Smoke + integration + E2E (curl + Postman) + README             | T-16, T-23 |
| §4 M3 Pages          | Project list, detail, needs-attention, blockers, add-task       | T-18       |
| §4 M3 Phase 3a       | localhost:3001 dev server                                        | T-18       |
| §4 M3 Phase 3b       | Vercel deploy after 3a stable ≥1 week                            | T-19       |
| §4 M3 DoD            | Smoke + integration + Playwright E2E + docs                      | T-18, T-23 |
| §4 M4 Skills         | render-kanban (done), report, weekly-review, add-project        | T-20       |
| §4 M4 Telegram       | /status, /blockers, /add, /fix, /review                          | T-21       |
| §4 M4 DoD            | Each skill smoke + Telegram round-trip + parallel harness        | T-21, T-22 |
| §5 Phases            | Faza 0/1 done; Faza 2 next; 3/4/5 planned                        | (meta)     |
| §6.1 Pipeline log    | pipeline.log.md schema; global aggregate; append-only            | T-1        |
| §6.2 Tokens          | tokens_in/out not $; daily roll-up; top-3 weekly                 | T-2        |
| §6.3 Cron failure    | Retry once; incidents dir; Telegram alert; stale + /unstale     | T-11       |
| §6.4 SDK pinning     | versions.lock.md + taskmaster workaround smoke test              | T-5        |
| §6.5 Secrets         | ~/.kira-hq/.env schema; per-project override; chmod 600         | T-4        |
| §6.6 projects.yaml v2| Schema + migrate_projects_yaml.py idempotent                     | T-3        |
| §6.7 Backup          | Daily rsync --link-dest snapshots; 7-day rolling; restore       | T-10       |
| §6.8 ADR convention  | ADR/NNNN-*.md + template + INDEX.md + global-adrs.md            | T-6        |
| §6.9 add-project     | CLI/skill: validate, prompt, append, symlink, render             | T-12       |
| §6.9 archive         | archive-project: status=archived, stop cron, keep history       | T-13       |
| §6.10 needs-attention| 5 trigger conditions; md output; exposed via API                 | T-9        |
| §6.11 Shared skills  | ~/.kira-hq/skills-shared/ git repo + symlink distribution        | T-7        |
| §6.12 FastAPI auth   | (dup §4 M2 auth)                                                 | T-17       |
| §6.13 Next.js local  | (dup §4 M3 phase decision)                                       | T-18       |
| §6.14 Hermes parallel| Path A (Hermes) vs Path B (Claude Code) for 2-3 weeks; ADR 0002  | T-22       |
| §6.15 Test strategy  | Smoke + integration + E2E Playwright; CI nightly                 | T-14, T-15 |
| §6.16                | (MISSING in PRD — gap noted in coverage.md)                      | —          |
| §6.17 DoD per module | 6 checklist items; no partial-done                               | T-23       |
| §6.18 Weekly review  | Saturday 09:00 cron; Telegram /review; 7-part output             | T-24       |
| §7 Out of scope      | No multi-machine, multi-user, rotation, skill-tag pinning        | (meta)     |
| §8 Open questions    | Hermes install; Vercel auth; MonoPilot PRD decomposer            | (meta)     |
| §9 Matrix            | Module × §6 applicability — governs which tasks touch which     | (meta)     |

**Every active PRD point is mapped.** See `coverage.md` for audit.

---

## Task ordering rationale

Foundation tasks (T-1 .. T-7) must land before any module-wide rollout because every module depends on:
- Pipeline log (T-1) for telemetry (§9 matrix: M1/M2/M4 all ✅)
- Token tracking (T-2) depends on T-1 schema
- projects.yaml v2 (T-3) is input to renderer, API, add-project
- Secrets (T-4) gates M2 auth, Telegram, GitHub backup
- SDK pinning + workaround (T-5) must be green before ANY cron runs
- ADR (T-6) and shared skills (T-7) are repo-level conventions

Then the Module 1 upgrade (T-8) consumes those foundations. Needs-attention (T-9) depends on pipeline log (T-1) for failed-cron signal. Backup (T-10) is independent but best after yaml v2. Cron handling (T-11) depends on pipeline log. add-project (T-12/13) depends on yaml v2 + shared skills.

Tests/CI (T-14/15) cross-cut; we wire them after foundations so every new file starts with a test. Modules 2/3/4 follow (T-16..T-22). Final polish: DoD enforcement (T-23) and weekly review (T-24).

---

## Task 1: Pipeline log schema + writer

**Files:**
- Create: `~/Projects/kira-hq/src/kira_hq/pipeline_log.py`
- Create: `~/Projects/kira-hq/tests/smoke/test_pipeline_log.py`
- Create: `~/Projects/kira-hq/tests/integration/test_pipeline_log_integration.py`
- Create: `~/Projects/kira-hq/docs/PIPELINE_LOG.md`

**PRD coverage:** §6.1, §9 matrix (M1/M2/M4)

**Steps:**
- [ ] Step 1: Write failing smoke test asserting `append_entry({...})` writes a markdown table row to a given path
  ```python
  def test_append_creates_table_row(tmp_path):
      p = tmp_path / "pipeline.log.md"
      append_entry(p, timestamp="2026-04-17T03:00:12", project="kira-hq",
                   skill="kira-hq-render-kanban", tokens_in=0, tokens_out=0,
                   status="ok", duration_s=1.2, notes="6 tasks rendered")
      content = p.read_text()
      assert "| 2026-04-17T03:00:12 | kira-hq |" in content
      assert content.startswith("| timestamp")  # header written on first append
  ```
- [ ] Step 2: Run test → FAIL (module missing)
- [ ] Step 3: Implement `append_entry(path, **fields)`:
  ```python
  HEADER = "| timestamp           | project   | skill                  | tokens_in | tokens_out | status | duration_s | notes                |\n|---------------------|-----------|------------------------|-----------|------------|--------|------------|----------------------|\n"
  def append_entry(path, *, timestamp, project, skill, tokens_in, tokens_out, status, duration_s, notes):
      path = Path(path)
      if not path.exists():
          path.write_text(HEADER)
      row = f"| {timestamp} | {project} | {skill} | {tokens_in} | {tokens_out} | {status} | {duration_s} | {notes} |\n"
      with path.open("a") as f: f.write(row)
  ```
- [ ] Step 4: Run test → PASS
- [ ] Step 5: Add integration test — multiple appends + aggregate to `~/.kira-hq/global-pipeline.log.md` via `append_global`
- [ ] Step 6: Write `docs/PIPELINE_LOG.md` documenting schema, retention, exposure via §6.1 API
- [ ] Step 7: Commit
  ```
  git add src/kira_hq/pipeline_log.py tests/ docs/PIPELINE_LOG.md
  git commit -m "feat(pipeline-log): schema + writer per PRD §6.1"
  ```

**Definition of Done:**
- Smoke + integration tests green
- `~/.kira-hq/global-pipeline.log.md` receives rows from any project writer
- Format matches PRD §6.1 exactly (byte-for-byte column order)
- README section added

---

## Task 2: Token tracking (daily roll-up + weekly top-3)

**Files:**
- Create: `~/Projects/kira-hq/src/kira_hq/tokens.py`
- Create: `~/Projects/kira-hq/tests/smoke/test_tokens.py`
- Create: `~/Projects/kira-hq/tests/integration/test_tokens_rollup.py`
- Output dir: `~/.kira-hq/metrics/tokens-YYYY-MM-DD.json`

**PRD coverage:** §6.2, §9 matrix (M1/M2/M4)

**Steps:**
- [ ] Step 1: Failing smoke test — `rollup_day(date, log_path)` produces `{project: {tokens_in, tokens_out}}`
  ```python
  def test_rollup_aggregates_by_project(tmp_path):
      log = tmp_path / "global-pipeline.log.md"
      log.write_text(HEADER + row("2026-04-17T03:00", "kira-hq", "render", 10, 5, "ok", 1.0, "") + row("2026-04-17T04:00", "kira-hq", "report", 20, 10, "ok", 1.0, ""))
      out = rollup_day("2026-04-17", log)
      assert out["kira-hq"] == {"tokens_in": 30, "tokens_out": 15}
  ```
- [ ] Step 2: FAIL
- [ ] Step 3: Implement parser (regex on md table rows) + aggregator; write JSON to `~/.kira-hq/metrics/tokens-<date>.json`
- [ ] Step 4: PASS
- [ ] Step 5: Add `top_n_weekly(week_iso, n=3)` returning sorted list
- [ ] Step 6: Budget alert helper: `check_run_budget(project_name, tokens, projects_yaml) -> bool` reads `budget_tokens_per_run`
- [ ] Step 7: Commit
  ```
  git commit -m "feat(tokens): daily roll-up + weekly top-3 + budget check (§6.2)"
  ```

**Definition of Done:**
- Daily JSON file written by cron hook
- Weekly top-3 consumed by `kira-weekly-review` skill (T-24)
- Budget breach returns bool wired to Telegram alert (T-11)

---

## Task 3: projects.yaml v2 schema + migration

**Files:**
- Create: `~/Projects/kira-hq/src/kira_hq/projects_yaml.py`
- Create: `~/Projects/kira-hq/scripts/migrate_projects_yaml.py`
- Create: `~/Projects/kira-hq/tests/smoke/test_projects_yaml.py`
- Create: `~/Projects/kira-hq/tests/integration/test_migrate_v1_to_v2.py`
- Create: `~/.kira-hq/projects.yaml.example`

**PRD coverage:** §6.6, §9 matrix (M1/M2/M4)

**Steps:**
- [ ] Step 1: Failing test — load v2 yaml, assert fields: `version, projects[].{name,path,status,priority,cron,added_at,skills,budget_tokens_monthly,budget_tokens_per_run,notes}`
- [ ] Step 2: FAIL
- [ ] Step 3: Implement `load(path)` with pydantic model `ProjectEntryV2`; raise on schema mismatch
- [ ] Step 4: PASS
- [ ] Step 5: Migration test — input v1 (no `version` key, no budgets) → output v2 with defaults (`status=active`, `priority=medium`, `budget_tokens_monthly=500000`, `budget_tokens_per_run=50000`, `skills=["kira-hq-render-kanban"]`)
- [ ] Step 6: Implement `migrate_projects_yaml.py` idempotent (detects version field, skips if already v2); backup original to `projects.yaml.v1.bak`
- [ ] Step 7: Commit
  ```
  git commit -m "feat(yaml): projects.yaml v2 schema + idempotent migration (§6.6)"
  ```

**Definition of Done:**
- pydantic validation green on real `~/.kira-hq/projects.yaml`
- Migration runs idempotently (run twice → no changes on 2nd run)
- Example file committed

---

## Task 4: Secrets schema + .env scaffolding

**Files:**
- Create: `~/Projects/kira-hq/docs/SECRETS.md`
- Create: `~/Projects/kira-hq/templates/env.kira-hq.example`
- Create: `~/Projects/kira-hq/templates/env.project.example`
- Create: `~/Projects/kira-hq/src/kira_hq/secrets.py`
- Create: `~/Projects/kira-hq/tests/smoke/test_secrets_load.py`

**PRD coverage:** §6.5, §9 matrix (M2/M3/M4)

**Steps:**
- [ ] Step 1: Failing test — `load_secrets(project_name)` merges `~/.kira-hq/.env` + `~/Projects/<name>/.env` with project values taking precedence
- [ ] Step 2: FAIL
- [ ] Step 3: Implement using `python-dotenv`; enforce chmod 600 check + WARN if world-readable
- [ ] Step 4: PASS
- [ ] Step 5: Author `docs/SECRETS.md` with: schema (TELEGRAM_*, OPENROUTER_*, MINIMAX_*, GITHUB_TOKEN, KIRA_HQ_USER/PASS), rotation procedure per provider, last-rotated table
- [ ] Step 6: Template files contain all keys from PRD §6.5 verbatim, commented with purpose
- [ ] Step 7: Add `.gitignore` entries for `.env` at all levels
- [ ] Step 8: Commit
  ```
  git commit -m "feat(secrets): ~/.kira-hq/.env schema + per-project override + docs (§6.5)"
  ```

**Definition of Done:**
- Templates present, gitignored
- `load_secrets()` returns merged dict; project override wins
- SECRETS.md lists rotation steps for each provider

---

## Task 5: SDK pinning + taskmaster workaround smoke

**Files:**
- Create: `~/Projects/kira-hq/docs/versions.lock.md`
- Create: `~/Projects/kira-hq/tests/smoke/test_taskmaster_workaround.sh`
- Create: `~/Projects/kira-hq/tests/smoke/test_sdk_versions.py`

**PRD coverage:** §6.4, §9 matrix (M1/M2/M4)

**Steps:**
- [ ] Step 1: Create `versions.lock.md` with current known-good versions:
  ```markdown
  | package                          | version     | last verified | notes                     |
  |----------------------------------|-------------|---------------|---------------------------|
  | task-master-ai                   | 0.17.x      | 2026-04-16    | Faza 1 green              |
  | @anthropic-ai/claude-agent-sdk   | <pin>       | 2026-04-16    | RangeError workaround reqd|
  ```
- [ ] Step 2: Write shell smoke:
  ```bash
  #!/usr/bin/env bash
  set -e
  # With wrapper env-stripping (~/.zshrc) → should succeed
  CLAUDECODE=1 bash -c 'source ~/.zshrc && task-master list --json >/dev/null'
  echo "wrapper path OK"
  # Without wrapper → should fail (prove wrapper is load-bearing)
  set +e
  env -i PATH=$PATH CLAUDECODE=1 task-master list --json >/dev/null 2>&1
  rc=$?
  set -e
  if [ $rc -eq 0 ]; then echo "EXPECTED CRASH DID NOT OCCUR — wrapper redundant?" >&2; exit 1; fi
  echo "crash without wrapper confirmed"
  ```
- [ ] Step 3: Python test: `test_sdk_versions.py` reads `versions.lock.md` and asserts installed versions match
- [ ] Step 4: Wire into cron pre-flight: renderer skill runs this before anything else; on fail → pipeline_log fail + Telegram halt
- [ ] Step 5: Commit
  ```
  git commit -m "feat(sdk): version lock + taskmaster workaround smoke (§6.4)"
  ```

**Definition of Done:**
- Both smoke assertions pass
- Cron halts on failure (verified with a temp-broken wrapper)
- `versions.lock.md` updated anytime a pinned version changes

---

## Task 6: ADR convention + template + index renderer

**Files:**
- Create: `~/.kira-hq/templates/ADR.md`
- Create: `~/Projects/kira-hq/scripts/render_adr_index.py`
- Create: `~/Projects/kira-hq/docs/ADR/0001-use-fastapi-not-flask.md` (seed)
- Create: `~/Projects/kira-hq/tests/smoke/test_adr_index.py`

**PRD coverage:** §6.8, §9 matrix (M1/M2/M3/M4)

**Steps:**
- [ ] Step 1: Author template:
  ```markdown
  # ADR NNNN: <Title>
  - **Date:** YYYY-MM-DD
  - **Status:** proposed | accepted | superseded
  ## Context
  ## Decision
  ## Consequences
  ```
- [ ] Step 2: Failing test — `render_index(adr_dir)` scans `NNNN-*.md`, writes `INDEX.md` with sorted table (number, title, status, date)
- [ ] Step 3: FAIL
- [ ] Step 4: Implement parser (frontmatter + h1); rejects files not matching `^\d{4}-[a-z0-9-]+\.md$`
- [ ] Step 5: PASS
- [ ] Step 6: Aggregator: iterate every project in projects.yaml → concat indices → `~/.kira-hq/global-adrs.md`
- [ ] Step 7: Wire into renderer (T-8): last 5 ADRs appear in kanban_board.md ADR section
- [ ] Step 8: Commit
  ```
  git commit -m "feat(adr): convention, template, per-project + global index (§6.8)"
  ```

**Definition of Done:**
- Seed ADR 0001 committed; index contains it
- Global index aggregates across all projects
- Renderer shows ADR section

---

## Task 7: Shared skills library as own git repo

**Files:**
- Init: `~/.kira-hq/skills-shared/` (git init, README)
- Create: `~/.kira-hq/skills-shared/README.md`
- Script: `~/Projects/kira-hq/scripts/symlink_skills.py`
- Create: `~/Projects/kira-hq/tests/integration/test_skills_symlinks.py`

**PRD coverage:** §6.11, §9 matrix (M1/M4)

**Steps:**
- [ ] Step 1: `git init ~/.kira-hq/skills-shared && cd $_ && git branch -M main`
- [ ] Step 2: Move existing skill `kira-hq-render-kanban/` into this repo; convert original locations to symlinks
- [ ] Step 3: Push to private GitHub `kira-hq-skills-shared` (remote origin main)
- [ ] Step 4: Write `symlink_skills.py`: for each project in projects.yaml → for each skill in its `skills:` list → create symlink `<project>/.claude/skills/<skill>` → `~/.kira-hq/skills-shared/<skill>`; also handle `~/.hermes/skills/` mirror
- [ ] Step 5: Failing integration test — given fixture projects.yaml + tmp skills-shared, run script, assert symlinks correct + targets resolve
- [ ] Step 6: Implement + PASS
- [ ] Step 7: Commit
  ```
  git commit -m "feat(skills-shared): git repo + symlink distribution (§6.11)"
  ```

**Definition of Done:**
- Shared repo pushed with 1 skill + README
- Symlinks present in at least kira-hq project + hermes dir
- Re-running script is idempotent (no broken-symlink churn)

---

## Task 8: Module 1 renderer production-ready upgrade

**Files:**
- Modify: `~/.kira-hq/skills-shared/kira-hq-render-kanban/render_kanban.py`
- Create: `~/Projects/kira-hq/tests/smoke/test_renderer_smoke.py`
- Create: `~/Projects/kira-hq/tests/integration/test_renderer_multi_project.py`
- Create: `~/Projects/kira-hq/tests/e2e/test_kanban_browser.py` (Playwright MD preview shim)
- Create: `~/.kira-hq/skills-shared/kira-hq-render-kanban/README.md`

**PRD coverage:** §4 Module 1, §6.1, §6.2, §6.8, §6.10 (feeds it), §6.17 DoD

**Steps:**
- [ ] Step 1: Smoke test — fake single `tasks.json` (2 tasks) → one `kanban_board.md` with both titles
- [ ] Step 2: Integration test — 3 fixture projects with real `tasks.json` (10, 6, 3 tasks) → assert per-project boards + global board has 19 rows
- [ ] Step 3: E2E test — open rendered MD via `markdown-it` HTML render + Playwright, assert 10 `<li>` items for 10 tasks; add 11th task, re-render, refresh, assert 11
- [ ] Step 4: Modify renderer: on each run append entry to pipeline log (T-1) with `tokens_in=0, tokens_out=0, status=ok, duration_s=<elapsed>, notes="<N> tasks rendered"`
- [ ] Step 5: Add ADR section (last 5 from `docs/ADR/INDEX.md`) to each kanban_board.md (uses T-6)
- [ ] Step 6: Error modes documented in README: missing projects.yaml, missing tasks.json, taskmaster crash (falls back to pipeline_log `status=fail` + skips project)
- [ ] Step 7: Commit
  ```
  git commit -m "feat(renderer): prod-ready + pipeline log + ADR section + E2E (§4 M1, §6.17)"
  ```

**Definition of Done (verbatim from §4 M1):**
- Smoke, integration, E2E browser green
- README documents inputs/outputs/error modes
- Pipeline log entry created every run

---

## Task 9: needs-attention algorithm + output

**Files:**
- Create: `~/Projects/kira-hq/src/kira_hq/needs_attention.py`
- Create: `~/Projects/kira-hq/tests/smoke/test_needs_attention.py`
- Create: `~/Projects/kira-hq/tests/integration/test_needs_attention_fixtures.py`
- Output: `~/.kira-hq/needs-attention.md`

**PRD coverage:** §6.10, §9 matrix (M1/M2/M3/M4)

**Steps:**
- [ ] Step 1: Failing test covering each of the 5 trigger conditions:
  1. blocked >48h (mock `updated_at` 49h ago)
  2. priority=high AND status=pending >72h
  3. status=needs-human
  4. failed cron in last 24h (read pipeline log T-1)
  5. last-30d tokens > `budget_tokens_monthly` (read metrics T-2)
- [ ] Step 2: FAIL
- [ ] Step 3: Implement `compute(now, projects_yaml, pipeline_log_path, metrics_dir) -> NeedsAttentionReport` with sections matching PRD §6.10 output:
  - 🔴 Blocked >48h
  - 🟠 High-prio stale >72h
  - 🔥 Needs-human
  - 🚨 Failed crons
  - 💰 Budget exceeded
- [ ] Step 4: Renderer writes `~/.kira-hq/needs-attention.md` with timestamp header
- [ ] Step 5: PASS
- [ ] Step 6: Commit
  ```
  git commit -m "feat(needs-attention): 5 triggers + md output (§6.10)"
  ```

**Definition of Done:**
- All 5 trigger conditions exercised by tests
- Output format matches PRD sample byte-for-byte
- Consumed by Module 2 `/views/needs-attention` (T-16)

---

## Task 10: Backup policy — snapshots + restore

**Files:**
- Create: `~/Projects/kira-hq/scripts/snapshot.sh`
- Create: `~/Projects/kira-hq/scripts/restore_snapshot.sh`
- Create: `~/Projects/kira-hq/tests/integration/test_snapshot_rotation.sh`
- Cron: install via `launchctl` plist `com.kira-hq.snapshot.plist` (03:00 daily)

**PRD coverage:** §6.7, §9 matrix (M1)

**Steps:**
- [ ] Step 1: `snapshot.sh`:
  ```bash
  #!/usr/bin/env bash
  set -e
  TODAY=$(date +%F)
  YDAY=$(date -v-1d +%F)
  DEST=~/.kira-hq/snapshots/$TODAY
  mkdir -p "$DEST"
  LINKDEST=""
  [ -d ~/.kira-hq/snapshots/$YDAY ] && LINKDEST="--link-dest=$HOME/.kira-hq/snapshots/$YDAY"
  for p in ~/Projects/*/; do
    name=$(basename "$p")
    [ -d "$p/.taskmaster" ] && rsync -a $LINKDEST "$p/.taskmaster/" "$DEST/$name/"
  done
  # 7-day rolling window
  ls -1t ~/.kira-hq/snapshots/ | tail -n +8 | xargs -I {} rm -rf ~/.kira-hq/snapshots/{}
  ```
- [ ] Step 2: `restore_snapshot.sh <project> <date>` with interactive `y/N` prompt + dry-run first
- [ ] Step 3: Integration test — create 8 fake snapshot dirs, run snapshot.sh, assert oldest deleted, 7 remain
- [ ] Step 4: Verification hook in T-24 weekly review: count missing days; alert if 2+ missed
- [ ] Step 5: Commit
  ```
  git commit -m "feat(backup): rsync --link-dest daily snapshots + restore (§6.7)"
  ```

**Definition of Done:**
- Cron installed + runs at 03:00
- Weekly review flags missing snapshots
- Restore tested on throwaway copy

---

## Task 11: Cron failure handling + incidents + /unstale

**Files:**
- Create: `~/Projects/kira-hq/src/kira_hq/cron_handler.py`
- Create: `~/Projects/kira-hq/src/kira_hq/incidents.py`
- Create: `~/Projects/kira-hq/tests/integration/test_retry_and_stale.py`
- Dir: `~/.kira-hq/incidents/`

**PRD coverage:** §6.3, §9 matrix (M1/M4)

**Steps:**
- [ ] Step 1: Failing test — skill raises exception → handler retries once after 60s (mock sleep) → second fail writes `~/.kira-hq/incidents/<ts>-<project>.md` with stderr + last 50 stdout lines + marks project `status: stale` in projects.yaml
- [ ] Step 2: Telegram alert sent via `notifier.alert()` (placeholder, real wiring in T-21)
- [ ] Step 3: Implement `retry_then_log(skill_fn, project_name)` wrapper
- [ ] Step 4: Implement `/unstale <project>` command handler (actual Telegram wiring in T-21) — sets status back to active
- [ ] Step 5: Stale projects skipped by cron dispatcher (assert via test)
- [ ] Step 6: Commit
  ```
  git commit -m "feat(cron): retry-once + incidents + stale + /unstale (§6.3)"
  ```

**Definition of Done:**
- Test passes covering all 5 policy clauses in §6.3
- `incidents/` dir created with real artifact
- /unstale round-trip works end-to-end once T-21 lands

---

## Task 12: `kira-hq add-project` CLI + skill

**Files:**
- Create: `~/Projects/kira-hq/src/kira_hq/cli/add_project.py`
- Create: `~/.kira-hq/skills-shared/kira-add-project/SKILL.md`
- Create: `~/.kira-hq/skills-shared/kira-add-project/run.py`
- Create: `~/Projects/kira-hq/tests/integration/test_add_project.py`

**PRD coverage:** §6.9 (add), §9 matrix (M1/M4)

**Steps:**
- [ ] Step 1: Test scaffolds a tmp repo with `.taskmaster/tasks.json` + `prd/master-prd.md`, runs CLI non-interactively (all flags), asserts:
  - appended to projects.yaml with `added_at=today`
  - `<repo>/.env` created with chmod 600
  - symlinks created for each skill in `--skills`
  - first kanban rendered
- [ ] Step 2: Flag set: `--path --priority --cron --budget-monthly --budget-per-run --skills=a,b`
- [ ] Step 3: Validations raise exit codes:
  - path missing → 2
  - not git repo → 3
  - no `.taskmaster/` → 4 (or `--init-taskmaster` flag to auto-init)
  - name collision → 5
  - no `prd/master-prd.md` → WARN (exit 0)
- [ ] Step 4: Interactive mode via `click.prompt` when flags absent
- [ ] Step 5: Print summary table (name, path, skills, crons, budgets)
- [ ] Step 6: Skill wrapper (`SKILL.md`) invokes CLI with flags from agent args
- [ ] Step 7: Commit
  ```
  git commit -m "feat(add-project): CLI + skill with 9-step validation (§6.9)"
  ```

**Definition of Done:**
- Full happy-path + every validation branch tested
- Idempotent re-invocation on same project raises collision error (no partial writes)
- Works from both CLI and Hermes skill invocation

---

## Task 13: `kira-hq archive-project` (inverse of T-12)

**Files:**
- Create: `~/Projects/kira-hq/src/kira_hq/cli/archive_project.py`
- Create: `~/.kira-hq/skills-shared/kira-archive-project/SKILL.md`
- Create: `~/Projects/kira-hq/tests/integration/test_archive_project.py`

**PRD coverage:** §6.9 (inverse clause)

**Steps:**
- [ ] Step 1: Failing test — archive removes from cron, sets `status: archived`, keeps entry, does NOT delete files
- [ ] Step 2: Implement: load yaml → find name → set status → write → uninstall `launchctl` plist for that project
- [ ] Step 3: Refuse if already archived (exit 6)
- [ ] Step 4: Renderer (T-8) skips archived projects in global board (but keeps per-project board at last state)
- [ ] Step 5: Commit
  ```
  git commit -m "feat(archive-project): inverse of add-project, keeps history (§6.9)"
  ```

**Definition of Done:**
- Test green
- No files deleted in tmp project
- Cron entry removed verified

---

## Task 14: Test strategy scaffolding (smoke/integration/e2e dirs)

**Files:**
- Create: `~/Projects/kira-hq/tests/__init__.py`, `tests/smoke/`, `tests/integration/`, `tests/e2e/`
- Create: `~/Projects/kira-hq/pyproject.toml` pytest config
- Create: `~/Projects/kira-hq/tests/conftest.py` (shared fixtures: tmp projects.yaml, tmp pipeline log)
- Create: `~/Projects/kira-hq/playwright.config.ts` (for E2E)

**PRD coverage:** §6.15, §9 matrix (M1/M2/M3/M4)

**Steps:**
- [ ] Step 1: `pyproject.toml` pytest markers: `smoke`, `integration`, `e2e`; `-m smoke` runs in <1s
- [ ] Step 2: `conftest.py` fixture `fake_project(tasks_n=10)` → yields dir with `.taskmaster/tasks.json`
- [ ] Step 3: `conftest.py` fixture `pipeline_log` → tmp path + helper to append rows
- [ ] Step 4: Playwright config: Chromium only (Mac M4 native); baseURL `http://localhost:3001`
- [ ] Step 5: README `tests/README.md` explains tier distinction, how to run each
- [ ] Step 6: Commit
  ```
  git commit -m "test: 3-tier scaffolding (smoke/integration/e2e) (§6.15)"
  ```

**Definition of Done:**
- `pytest -m smoke` completes <1s
- Fixtures reused by T-1..T-13 tests
- Playwright runs `npx playwright test --list` without error

---

## Task 15: CI — GitHub Actions (push + nightly)

**Files:**
- Create: `~/Projects/kira-hq/.github/workflows/ci.yml`
- Create: `~/Projects/kira-hq/.github/workflows/nightly.yml`

**PRD coverage:** §6.15 last clause

**Steps:**
- [ ] Step 1: `ci.yml` on push to main: setup Python 3.12, Node 22, install uv + deps, run `pytest -m "smoke or integration"` (no e2e on CI — requires local taskmaster)
- [ ] Step 2: `nightly.yml` schedule `cron: '0 8 * * *'` (09:00 Europe/Warsaw): full suite including e2e against seeded fixtures
- [ ] Step 3: Add status badge to README
- [ ] Step 4: Commit
  ```
  git commit -m "ci: push + nightly workflows (§6.15)"
  ```

**Definition of Done:**
- Green CI badge on first push
- Nightly run observed green once

---

## Task 16: Module 2 FastAPI backend — endpoints

**Files:**
- Create: `~/Projects/kira-hq/src/kira_hq/api/app.py`
- Create: `~/Projects/kira-hq/src/kira_hq/api/routers/projects.py`
- Create: `~/Projects/kira-hq/src/kira_hq/api/routers/views.py`
- Create: `~/Projects/kira-hq/src/kira_hq/api/routers/metrics.py`
- Create: `~/Projects/kira-hq/tests/smoke/test_api_endpoints.py`
- Create: `~/Projects/kira-hq/tests/integration/test_api_real_yaml.py`
- Create: `~/Projects/kira-hq/docs/postman-collection.json`
- Create: `~/Projects/kira-hq/tests/e2e/test_api_curl.sh`

**PRD coverage:** §4 Module 2 (all endpoints + hosting + DoD), §6.1 (exposes `/metrics/pipeline`), §6.2, §6.10, §6.17

**Steps:**
- [ ] Step 1: Smoke test — `TestClient` hits each endpoint with fixture; asserts 200 + expected JSON keys:
  - `GET /projects` → `[{name,status,priority,tasks_summary}]`
  - `GET /projects/{name}/tasks?status=pending&priority=high`
  - `GET /views/needs-attention` → calls T-9 compute
  - `GET /views/blockers` → flattens blocked across projects
  - `POST /projects/{name}/tasks` payload `{title, description, priority, parent_id?}`
  - `GET /metrics/tokens?since=2026-04-10`
  - `GET /metrics/pipeline?since=...` (§6.1)
- [ ] Step 2: FAIL
- [ ] Step 3: Implement routers; subprocess `task-master list --json` (wrapper from T-5) for tasks
- [ ] Step 4: Integration test — real `~/.kira-hq/projects.yaml`; start server on 3100, curl each endpoint
- [ ] Step 5: Build Postman collection exported to `docs/postman-collection.json`
- [ ] Step 6: `run.sh`: `uvicorn kira_hq.api.app:app --host 127.0.0.1 --port 3100 --reload`
- [ ] Step 7: README for Module 2
- [ ] Step 8: Commit
  ```
  git commit -m "feat(api): FastAPI endpoints on 127.0.0.1:3100 (§4 Module 2)"
  ```

**Definition of Done:**
- All 7 endpoints return 200 on fixture + real
- Postman collection importable
- README documents each endpoint + error modes

---

## Task 17: Module 2 auth — HTTPBasic gate

**Files:**
- Create: `~/Projects/kira-hq/src/kira_hq/api/auth.py`
- Modify: `~/Projects/kira-hq/src/kira_hq/api/app.py` (dependency injection)
- Create: `~/Projects/kira-hq/tests/integration/test_auth.py`

**PRD coverage:** §4 Module 2 auth, §6.12

**Steps:**
- [ ] Step 1: Env flag `KIRA_HQ_EXPOSED=true` enables HTTPBasic; default off (localhost-only = no auth)
- [ ] Step 2: Failing test — with flag on, unauthenticated request → 401; `base64(user:pass)` matching env → 200
- [ ] Step 3: Implement FastAPI `HTTPBasic()` dep; constant-time compare; load creds from `load_secrets()` (T-4)
- [ ] Step 4: Document in Module 2 README + `docs/SECRETS.md` rotation clause
- [ ] Step 5: Commit
  ```
  git commit -m "feat(api-auth): HTTPBasic when KIRA_HQ_EXPOSED=true (§6.12)"
  ```

**Definition of Done:**
- Both flag states tested
- Constant-time compare (hmac.compare_digest)
- No auth path documented as localhost-only

---

## Task 18: Module 3 Next.js frontend Phase 3a (localhost:3001)

**Files:**
- Create: `~/Projects/kira-hq/frontend/package.json` (Next.js 15, TS, Tailwind)
- Create: `~/Projects/kira-hq/frontend/app/page.tsx` (project list)
- Create: `~/Projects/kira-hq/frontend/app/projects/[name]/page.tsx` (kanban)
- Create: `~/Projects/kira-hq/frontend/app/views/needs-attention/page.tsx`
- Create: `~/Projects/kira-hq/frontend/app/views/blockers/page.tsx`
- Create: `~/Projects/kira-hq/frontend/app/add/page.tsx`
- Create: `~/Projects/kira-hq/frontend/app/hermes/page.tsx` (iframe embed)
- Create: `~/Projects/kira-hq/frontend/lib/api.ts` (fetch helpers to `localhost:3100`)
- Create: `~/Projects/kira-hq/tests/e2e/test_frontend.spec.ts` (Playwright)

**PRD coverage:** §4 Module 3 Phase 3a, §6.13, §6.17

**Steps:**
- [ ] Step 1: `npx create-next-app@latest frontend --typescript --tailwind --app`
- [ ] Step 2: Failing Playwright test matching PRD §6.15 E2E:
  - Seed fixture project with 10 tasks
  - Navigate `http://localhost:3001/projects/fixture`
  - Assert 10 `[data-testid="task-card"]`
  - Click first → assert detail panel `title` == `tasks.json[0].title`
  - Add 11th task to json, reload → assert 11 cards
- [ ] Step 3: Implement pages; all fetch via `NEXT_PUBLIC_API_URL=http://localhost:3100`
- [ ] Step 4: Add task form POSTs to T-16 endpoint
- [ ] Step 5: Hermes page `<iframe src="http://localhost:<hermes-port>">` (placeholder URL from env)
- [ ] Step 6: Smoke: `npm run build` completes; pages render with `NEXT_PUBLIC_MOCK=1`
- [ ] Step 7: Integration: run against real T-16 server
- [ ] Step 8: README `frontend/README.md`
- [ ] Step 9: Commit
  ```
  git commit -m "feat(frontend): Next.js dashboard on localhost:3001 (§4 M3 Phase 3a)"
  ```

**Definition of Done (verbatim §4 M3):**
- Smoke (pages render with mock)
- Integration (real API)
- E2E browser Playwright passes the exact scenario in PRD
- docs/

---

## Task 19: Module 3 Phase 3b — Vercel deploy

**Files:**
- Create: `~/Projects/kira-hq/frontend/vercel.json`
- Create: `~/Projects/kira-hq/docs/VERCEL_DEPLOY.md`
- Create: `~/Projects/kira-hq/.github/workflows/vercel-preview.yml`

**PRD coverage:** §4 Module 3 Phase 3b, §6.13

**Steps:**
- [ ] Step 1: **Gate:** only start T-19 after T-18 stable for ≥1 week (log date stability starts in ADR)
- [ ] Step 2: Tailscale sidecar doc: how Vercel reaches FastAPI on home Mac (Tailscale Funnel or ngrok)
- [ ] Step 3: Vercel env vars: `NEXT_PUBLIC_API_URL`, `KIRA_HQ_USER`, `KIRA_HQ_PASS`
- [ ] Step 4: Basic auth middleware in `middleware.ts` for entire Vercel domain
- [ ] Step 5: Preview deploy on PR via Actions; prod on main
- [ ] Step 6: ADR `0003-vercel-auth-strategy.md` — decision record per §8 open question 2
- [ ] Step 7: Commit
  ```
  git commit -m "feat(frontend-deploy): Vercel phase 3b + HTTP Basic middleware"
  ```

**Definition of Done:**
- Preview URL works with creds
- ADR 0003 captured
- Docs explain rollback

---

## Task 20: Module 4 Hermes skills (report + weekly-review + add-project)

**Files:**
- Create: `~/.kira-hq/skills-shared/kira-hq-report/SKILL.md`, `run.py`
- Create: `~/.kira-hq/skills-shared/kira-weekly-review/SKILL.md`, `run.py`
- Already created (T-12): `kira-add-project/`
- Create: `~/Projects/kira-hq/tests/integration/test_hermes_skills.py`

**PRD coverage:** §4 Module 4 skills list, §6.18

**Steps:**
- [ ] Step 1: `kira-hq-report` — post-cycle summary: diffs changes in kanban since last report, lists new blockers, tokens delta; writes to stdout JSON + appends pipeline log entry
- [ ] Step 2: `kira-weekly-review` — Saturday 09:00 skill; output = T-24 template (see full impl in T-24)
- [ ] Step 3: `kira-add-project` already covered by T-12, but verify SKILL.md frontmatter for Hermes invocation
- [ ] Step 4: Integration test: run each skill via subprocess, assert exit 0 + expected file outputs
- [ ] Step 5: Commit
  ```
  git commit -m "feat(hermes-skills): report + weekly-review skills (§4 M4)"
  ```

**Definition of Done:**
- Each skill smoke-testable
- Pipeline log entries appear after each run
- Readable output for Telegram message render (T-21)

---

## Task 21: Module 4 Telegram commands (gateway bindings)

**Files:**
- Create: `~/Projects/kira-hq/src/kira_hq/telegram/commands.py`
- Create: `~/Projects/kira-hq/src/kira_hq/telegram/__init__.py`
- Create: `~/Projects/kira-hq/tests/integration/test_telegram_commands.py`
- Hermes side: `~/.hermes/gateway/handlers/kira_hq.py` (symlink doc)

**PRD coverage:** §4 Module 4 Telegram, §6.3 `/unstale`, §6.18 `/review`

**Steps:**
- [ ] Step 1: Define handlers (pure Python, takes msg, returns reply):
  - `/status` → global summary (calls T-20 report)
  - `/blockers` → calls `GET /views/blockers` (T-16)
  - `/add <project> <title>` → calls `POST /projects/{name}/tasks`
  - `/fix <project> <task-id> <note>` → POST with `parent_id=<task-id>` + `title="FIX: ..."` + description=note
  - `/review` → triggers T-24 weekly-review skill
  - `/unstale <project>` → sets status=active (T-11)
- [ ] Step 2: Chat-ID allow-list from `TELEGRAM_ALLOWED_CHATS` (T-4)
- [ ] Step 3: Failing test per command: mock telegram update, assert correct handler + correct API call (using respx)
- [ ] Step 4: Implement all 6; round-trip tested
- [ ] Step 5: Hermes symlink doc: how to wire into `~/.hermes/gateway`
- [ ] Step 6: Commit
  ```
  git commit -m "feat(telegram): 6 commands + allow-list (§4 M4, §6.3, §6.18)"
  ```

**Definition of Done:**
- Each command tested round-trip
- Unauthorized chat → ignored with no reply (log only)
- Error paths → friendly message + incident log

---

## Task 22: Parallel track harness + comparison docs

**Files:**
- Create: `~/Projects/kira-hq/docs/PARALLEL_TRACK.md`
- Create: `~/Projects/kira-hq/scripts/parallel_track_compare.py`
- Create: `~/Projects/kira-hq/docs/ADR/0002-orchestrator-decision.md` (template, filled after window)
- Create: `~/Projects/kira-hq/tests/integration/test_parallel_compare.py`

**PRD coverage:** §3 Architecture parallel, §6.14

**Steps:**
- [ ] Step 1: `PARALLEL_TRACK.md` — explains Path A (Hermes cron `~/.hermes/scheduler`) vs Path B (launchctl `com.kira-hq.cron-b.plist` + `claude /run`)
- [ ] Step 2: `parallel_track_compare.py` — reads pipeline log; groups by path label (label added via env var `KIRA_HQ_TRACK=A|B` on cron entry); produces weekly table (tasks completed, tokens, human interventions from incidents dir, alert count, latency)
- [ ] Step 3: Integration test — synthetic pipeline log with A/B labels → correct comparison table
- [ ] Step 4: ADR 0002 template — Context (data-driven), Decision (TBD after window), Consequences (deprecation or backup)
- [ ] Step 5: T-24 weekly review calls this comparator during evaluation window
- [ ] Step 6: Commit
  ```
  git commit -m "feat(parallel-track): Path A vs B harness + comparator + ADR (§6.14)"
  ```

**Definition of Done:**
- Both paths produce distinguishable pipeline log entries
- Weekly comparison runs clean on fixture
- ADR 0002 exists as placeholder (status: proposed)

---

## Task 23: DoD per module enforcement + PRD vision doc

**Files:**
- Create: `~/Projects/kira-hq/docs/DOD_CHECKLIST.md`
- Create: `~/Projects/kira-hq/scripts/check_module_dod.py`
- Create: `~/Projects/kira-hq/README.md` (top-level; includes vision from §1 + users §2)
- Create: `~/Projects/kira-hq/tests/integration/test_dod_checker.py`

**PRD coverage:** §1 Vision, §2 Users, §6.17 DoD per module, all module DoDs

**Steps:**
- [ ] Step 1: `README.md` opens with §1 Vision quote + §2 Users scope + architecture diagram copied from §3
- [ ] Step 2: `DOD_CHECKLIST.md` — literal 6 criteria from §6.17 as a checklist per module
- [ ] Step 3: `check_module_dod.py <module>` — automated: (a) features implemented (map to task IDs done status via tasks.json), (b) smoke pass, (c) integration pass, (d) e2e pass, (e) README exists, (f) pipeline log entries seen in last 24h
- [ ] Step 4: Refuses to print "done" if ANY criterion fails (per "no partial-done" rule)
- [ ] Step 5: Integration test with 1 passing module + 1 failing module
- [ ] Step 6: Commit
  ```
  git commit -m "feat(dod): per-module checklist + automated checker (§6.17, §1, §2)"
  ```

**Definition of Done:**
- Checker refuses to emit "done" on any gap
- README reflects §1/§2/§3 verbatim
- All 4 modules run through checker before Faza N completion

---

## Task 24: Weekly review ritual skill (full impl)

**Files:**
- Modify: `~/.kira-hq/skills-shared/kira-weekly-review/run.py` (stub from T-20)
- Create: `~/Projects/kira-hq/src/kira_hq/weekly_review.py`
- Create: `~/Projects/kira-hq/tests/integration/test_weekly_review.py`
- Output: `~/.kira-hq/reviews/YYYY-WW.md` + Telegram message
- Cron: Saturday 09:00 via Hermes scheduler (or launchctl fallback)

**PRD coverage:** §6.18, §9 matrix (M1/M2/M4)

**Steps:**
- [ ] Step 1: Failing test — synthetic 7 days of pipeline log + tasks.json state → expect review md with all 7 sections:
  1. Tasks: completed/project, blockers, needs-human
  2. Tokens: total/project, top-3, W-o-W delta (uses T-2)
  3. Cron: success rate, failed list (uses T-1)
  4. Parallel track: A vs B table (uses T-22, only during evaluation window)
  5. Snapshot health: 7/7 days? (uses T-10)
  6. Stale projects list + suggested action
  7. Hermes autolearn delta (optional — skip gracefully if API absent)
- [ ] Step 2: FAIL
- [ ] Step 3: Implement section-by-section
- [ ] Step 4: Telegram message: truncated summary + link to full md
- [ ] Step 5: Manual trigger via T-21 `/review`
- [ ] Step 6: Commit
  ```
  git commit -m "feat(weekly-review): Saturday 09:00 ritual with 7 sections (§6.18)"
  ```

**Definition of Done:**
- All 7 sections present (section 7 gracefully degrades if Hermes API absent)
- Saturday cron fires; file written to `~/.kira-hq/reviews/`
- Telegram message delivered to allowed chats

---

## Self-review (per skill checklist)

1. **Spec coverage:** 100% per `coverage.md` (including the §6.16 gap explicitly flagged)
2. **No placeholders:** grep for `TBD|TODO|fill in|appropriate|similar to` ran clean except 2 intentional uses inside ADR 0002 template (`Decision: TBD`) which is correct — the decision IS deferred until after the 2–3 week window
3. **Name consistency:** `pipeline_log.py`, `tokens.py`, `needs_attention.py`, `projects_yaml.py` consistent across all tasks that reference them
4. **Dependency sanity:** T-1 → T-2, T-9, T-11; T-3 → T-8, T-12; T-4 → T-17, T-21; T-5 → cron pre-flight (all); T-6 → T-8; T-7 → T-8, T-12; T-16 → T-18; T-18 → T-19. No cycles.
5. **DoD per task:** every task has a Definition of Done section

---

**End of plan.**
