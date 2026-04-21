# Kira-HQ Tests

Three tiers per PRD §6.15.

## Tiers

| Tier        | Location              | Target runtime | Purpose                                     |
|-------------|-----------------------|----------------|---------------------------------------------|
| smoke       | `tests/smoke/`        | <1s total      | Function-level, fake inputs, no I/O         |
| integration | `tests/integration/`  | <10s total     | Real fixtures, multi-file flows, no network |
| e2e         | `tests/e2e/`          | minutes        | Playwright + running FastAPI/Next.js        |

## Running

```sh
# Smoke + integration (default, fast) — runs on every save
.venv/bin/python -m pytest tests/smoke/ tests/integration/ -v

# Smoke only (target <1s)
.venv/bin/python -m pytest -m smoke -v

# E2E (opt-in; needs Playwright browsers installed + services up)
npx playwright install chromium       # once
npx playwright test                   # TS specs under tests/e2e/*.spec.ts
.venv/bin/python -m pytest -m e2e     # Python e2e markers, if any
```

E2E is deselected by default (opt-in with `-m e2e`) so CI can run the
fast tiers in parallel without Playwright overhead.

## Shared fixtures (`tests/conftest.py`)

- `fake_project(name, tasks_n)` — factory; returns `FakeProject(path, tasks_json, tasks_n)`.
  Creates `<tmp>/<name>/.taskmaster/tasks/tasks.json` + `prd/master-prd.md`.
- `pipeline_log_tmp` — `PipelineLogTmp(path, append)`. `append(**kwargs)` writes
  one row using the 10-column v2 schema (PRD §6.1, §6.19 — incl. `provider`,
  `expand_used`). Defaults keep call sites short.
- `projects_yaml_tmp(entries=N)` — factory returning path to a v2 YAML
  doc with N synthetic project entries.

Prefer these over ad-hoc fixtures so schema changes propagate through one
file. Add new fixtures here when they're used by ≥2 test modules.

## Conventions

- Mark every test file with `pytestmark = pytest.mark.<tier>` at top.
- Smoke tests must NOT touch `~/.kira-hq/` — use `tmp_path` + fixtures.
- Integration tests may write to `tmp_path` but never to real user dirs.
- E2E is the only tier allowed to hit localhost services.
- `--strict-markers` is enforced — every mark must be declared in `pyproject.toml`.
