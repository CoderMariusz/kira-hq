# kira-hq

[![CI](https://github.com/CoderMariusz/kira-hq/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/CoderMariusz/kira-hq/actions/workflows/ci.yml)
[![Nightly](https://github.com/CoderMariusz/kira-hq/actions/workflows/nightly.yml/badge.svg)](https://github.com/CoderMariusz/kira-hq/actions/workflows/nightly.yml)

Command center for AI-driven projects (PRD v2.0).

## Vision

Kira-HQ is a local-first command center for running **10–15 AI-driven projects in parallel** on one Mac M4. It aggregates task state, kanban views, token usage, incidents, backups, and pipeline logs into one place so the owner can see what needs attention quickly.

Kira-HQ is **the project manager, not the executor**. Hermes remains the orchestrator/executor layer and uses Kira-HQ as the source of project state, dashboards, and module-level views.

## Users

- **Primary user:** Mariusz, solo owner-operator.
- **Operating model:** one always-on local Mac M4, morning dashboard review, Telegram alerts during the day.
- **Scale target:** 10–15 active projects max; no horizontal scaling target in v2.0.

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│ HERMES (orchestrator / executor)                           │
│ - cron scheduler                                           │
│ - agent invocation                                         │
│ - Telegram gateway                                         │
│ - memory / autolearn                                       │
└────────────┬────────────────────────────────────────────────┘
             │ invokes skills, reads/writes state
             ▼
┌─────────────────────────────────────────────────────────────┐
│ KIRA-HQ (project manager, data + views)                    │
│ - Module 1: markdown renderer                              │
│ - Module 2: FastAPI backend                                │
│ - Module 3: Next.js dashboard                              │
│ - Module 4: Hermes integration skills + commands           │
│ - cross-cutting: logs, secrets, ADRs, backups, token rollups│
└────────────┬────────────────────────────────────────────────┘
             │ reads projects.yaml + task state
             ▼
┌─────────────────────────────────────────────────────────────┐
│ PROJECTS (~/Projects/<name>/)                              │
│ - .taskmaster/tasks/tasks.json                             │
│ - kanban_board.md / pipeline.log.md                        │
│ - prd/master-prd.md                                        │
│ - docs/ADR/                                                │
└─────────────────────────────────────────────────────────────┘
```

## Modules

- **Module 1** — markdown renderer producing per-project and global kanban views.
- **Module 2** — FastAPI API for projects, tasks, views, and metrics.
- **Module 3** — Next.js dashboard over Module 2.
- **Module 4** — Hermes-facing skills, Telegram commands, and execution harnesses.

## Inputs / Outputs / Error modes

### Inputs
- `~/.kira-hq/projects.yaml`
- per-project `.taskmaster/tasks/tasks.json`
- per-project and global `.env` files
- pipeline logs, ADRs, review artifacts, and metrics rollups

### Outputs
- `kanban_board.md` per project
- `~/.kira-hq/global-kanban.md`
- `pipeline.log.md` per project plus global aggregate
- FastAPI JSON responses
- dashboard pages and Hermes skill outputs

### Error modes
- missing or invalid `projects.yaml`
- malformed or stale `.taskmaster/tasks/tasks.json`
- failed cron/skill runs recorded in `pipeline.log.md` and incidents
- missing docs or missing pipeline activity causing DoD checker failure

## Definition of Done

- Canonical checklist: `DOD_CHECKLIST.md`
- Automated checker: `python scripts/check_module_dod.py <module>`

Examples:

```bash
python scripts/check_module_dod.py module-1
python scripts/check_module_dod.py 2
```

The checker is strict: if any criterion fails, the module status is `in-progress` and never partial-`done`.

## Tests

```bash
uv run pytest tests/smoke tests/integration -q
uv run pytest -m e2e tests/e2e -q
```

See `tests/README.md` for tier conventions.
