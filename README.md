# kira-hq

[![CI](https://github.com/CoderMariusz/kira-hq/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/CoderMariusz/kira-hq/actions/workflows/ci.yml)
[![Nightly](https://github.com/CoderMariusz/kira-hq/actions/workflows/nightly.yml/badge.svg)](https://github.com/CoderMariusz/kira-hq/actions/workflows/nightly.yml)

Command center for AI-driven projects (PRD v2.0).

## Overview

Kira-HQ coordinates multiple parallel AI coding projects — task-master state,
token budgets, cron pipelines, incident logs, and the kanban board — around a
single global projects registry at `~/.kira-hq/projects.yaml`.

See `prd/master-prd.md` for the authoritative spec and
`benchmark/C-hybrid/plan.md` for the 25-task Faza 2 execution plan.

## Tests

```bash
# Fast suite (runs on CI on every push)
.venv/bin/pytest -m "smoke or integration" -v

# Full suite including e2e (runs nightly 09:00 Europe/Warsaw)
.venv/bin/pytest -v

# Shell smoke + integration tests
bash tests/smoke/*.sh
bash tests/integration/*.sh
```

## CI

- **`ci.yml`** — push + PR to `main`. Runs smoke + integration suite on
  Python 3.12, plus all shell tests.
- **`nightly.yml`** — schedule `0 8 * * *` UTC (≈09:00 Europe/Warsaw).
  Full suite including `-m e2e` with Playwright (chromium) and
  task-master-ai@0.43.1 installed globally.

Both workflows gate expensive/taskmaster-dependent repros behind
`KIRA_RUN_EXPENSIVE_CRASH_REPRO=0`.
