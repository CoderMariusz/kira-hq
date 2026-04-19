# Kira-HQ Module 2 — FastAPI Backend

REST API over project state. PRD §4 Module 2.

## Quick start

```bash
# one-time
uv venv
uv pip install -e .

# run
./scripts/run-api.sh           # dev mode, --reload
./scripts/run-api.sh --prod    # no reload

# sanity
curl http://127.0.0.1:3100/health
# → {"status":"ok","service":"kira-hq","version":"0.2.0"}
```

Port **3100** is verified free on the target host (see PRD §4).

## Endpoints

All 7 endpoints return JSON. HTTP 200 unless noted. Base URL: `http://127.0.0.1:3100`.

| Method | Path                                 | Purpose                                                        |
|--------|--------------------------------------|----------------------------------------------------------------|
| GET    | `/health`                            | Liveness probe                                                 |
| GET    | `/projects`                          | List all projects + per-status task counters                   |
| GET    | `/projects/{name}/tasks`             | List tasks; `?status=` / `?priority=` filters                  |
| POST   | `/projects/{name}/tasks`             | Append a new task (201 on success)                             |
| GET    | `/views/needs-attention`             | Run T-9 needs-attention engine over current state (PRD §6.10)  |
| GET    | `/views/blockers`                    | Flatten all `status: blocked` tasks across active projects     |
| GET    | `/metrics/tokens?since=YYYY-MM-DD`   | Per-project tokens_in/out aggregate from the pipeline log      |
| GET    | `/metrics/pipeline?since=<ISO>`      | Raw pipeline log rows ≥ since (PRD §6.1)                       |

### `GET /projects`

```json
[
  {
    "name": "kira-hq",
    "path": "/Users/you/Projects/kira-hq",
    "status": "active",
    "priority": "high",
    "tasks_summary": {"done": 15, "in-progress": 1, "pending": 9, "total": 25}
  }
]
```

### `GET /projects/{name}/tasks`

Query params:
- `status` — one of `pending|in-progress|blocked|done|needs-human` (any string accepted; unmatched → empty)
- `priority` — one of `high|medium|low`

Returns the full task objects from `task-master list --json` (id, title, description, priority, status, dependencies, …).

Errors:
- `404` — project name not in `~/.kira-hq/projects.yaml`

### `POST /projects/{name}/tasks`

Request body:
```json
{
  "title": "Add Stripe webhook",
  "description": "Handles invoice.paid events",
  "priority": "high",
  "parent_id": null
}
```

Returns `201` with the created task (new id auto-assigned, status = `pending`).

Errors:
- `404` — unknown project
- `409` — project has no `.taskmaster/tasks/tasks.json`
- `422` — invalid payload (priority must be `high|medium|low`)

**Important:** this endpoint writes directly to `tasks.json` (atomic temp-file swap). It does **not** invoke `task-master add-task` because that would spawn `claude-agent-sdk` on every POST — too expensive and fragile for synchronous HTTP. Use Module 4 cron skills for LLM-backed task expansion.

### `GET /views/needs-attention`

Runs the full T-9 engine (5 triggers: blocked >48h, stale high-prio >72h, needs-human, failed crons, budget exceeded) against live state. Returns the `NeedsAttentionReport` dataclass serialized to JSON:

```json
{
  "generated_at": "2026-04-19T10:30:00",
  "blocked": [...],
  "high_prio_stale": [...],
  "needs_human": [...],
  "failed_crons": [...],
  "budget_exceeded": [...]
}
```

### `GET /views/blockers`

Flat list of all `status: blocked` tasks across every `status: active` project:

```json
[
  {"project": "monopilot", "id": "12", "title": "Setup Stripe webhook",
   "priority": "high", "dependencies": ["8"]}
]
```

### `GET /metrics/tokens`

Aggregates `tokens_in` + `tokens_out` per project from the global pipeline log (`~/.kira-hq/global-pipeline.log.md`). Defaults to last 30 days if `since` is omitted.

```json
{
  "since": "2026-04-01",
  "until": "2026-04-19",
  "log": "/Users/you/.kira-hq/global-pipeline.log.md",
  "projects": {
    "kira-hq": {"tokens_in": 15234, "tokens_out": 4521}
  }
}
```

### `GET /metrics/pipeline`

Raw pipeline log rows (PRD §6.1 10-column schema). Each row:
```json
{
  "timestamp": "2026-04-19T08:00:00",
  "project": "kira-hq",
  "skill": "kira-hq-render-kanban",
  "provider": "sonnet-4.6",
  "expand_used": "false",
  "tokens_in": 0,
  "tokens_out": 0,
  "status": "ok",
  "duration_s": "1.2",
  "notes": ""
}
```

## Architecture

```
kira_hq/api/
├── app.py                 # make_app(...) factory + default loaders
└── routers/
    ├── projects.py        # /projects, /projects/{name}/tasks (GET+POST)
    ├── views.py           # /views/{needs-attention,blockers}
    └── metrics.py         # /metrics/{tokens,pipeline}
```

### Dependency injection

`make_app(...)` accepts 5 optional callables — used by tests to avoid real disk / subprocess:

| Parameter                 | Default                                   | Replaced by                         |
|---------------------------|-------------------------------------------|-------------------------------------|
| `projects_loader`         | `default_projects_yaml_loader`            | Lambda returning dict in tests      |
| `projects_yaml_path`      | `~/.kira-hq/projects.yaml`                | tmp yaml path in tests              |
| `taskmaster_runner`       | `default_taskmaster_runner` (subprocess)  | Lambda reading `tasks.json` direct  |
| `taskmaster_add_task`     | `default_taskmaster_add_task` (atomic JSON write) | Lambda capturing calls      |
| `pipeline_log_loader`     | `~/.kira-hq/global-pipeline.log.md` path  | tmp log path                        |
| `tokens_dir_loader`       | `~/.kira-hq/metrics/`                     | tmp metrics dir                     |
| `needs_attention_compute` | `kira_hq.needs_attention.compute`         | fake returning static report        |

All routers read dependencies from `app.state.*` — never from module-level globals — so a single FastAPI instance never closes over shared state, making parallel test sessions safe.

## Auth

**Localhost only** → no auth required. When exposed beyond 127.0.0.1 (Tailscale / Vercel later):
- HTTP Basic via FastAPI `HTTPBasic` dependency (T-17)
- Credentials in `~/.kira-hq/.env`: `KIRA_HQ_USER`, `KIRA_HQ_PASS`

Never expose `--host 0.0.0.0` without finishing T-17 first.

## Testing

```bash
# smoke (fake loaders, no I/O)
pytest tests/smoke/test_api_endpoints.py -v

# integration (real uvicorn on :3100, real projects.yaml)
pytest tests/integration/test_api_real_yaml.py -v

# e2e (curl against a running server)
./scripts/run-api.sh &
BASE_URL=http://127.0.0.1:3100 bash tests/e2e/test_api_curl.sh
```

Postman collection: `docs/postman-collection.json` — importable, covers all 7 endpoints with example payloads.

## Error modes (quick reference)

| Symptom                             | Likely cause                                    | Fix                                                    |
|-------------------------------------|-------------------------------------------------|--------------------------------------------------------|
| `GET /projects` → `[]`              | `~/.kira-hq/projects.yaml` missing or empty     | Add projects via `kira-hq add-project`                 |
| `tasks_summary.total == 0` for X    | `task-master list` subprocess failed silently   | Check `.taskmaster/` exists under project path         |
| 500 on `/views/needs-attention`     | pipeline log malformed                          | Check `~/.kira-hq/global-pipeline.log.md` header row   |
| `POST` → 409 `tasks.json missing`   | Project has no `.taskmaster/` yet               | Run `task-master init` in that project                 |
| `POST` → 422 `priority`             | Payload priority ∉ {high, medium, low}          | Fix payload                                            |
| Uvicorn exits with `Address already in use` | :3100 occupied                          | `lsof -iTCP:3100 -sTCP:LISTEN` → kill or set `KIRA_HQ_API_PORT` |
| `task-master` RangeError in logs    | CLAUDECODE env var leaked into subprocess       | Use `scripts/run-api.sh` (strips the 4 trigger vars)   |
