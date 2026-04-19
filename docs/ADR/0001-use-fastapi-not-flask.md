# ADR 0001: Use FastAPI (not Flask) for Module 2

- **Date:** 2026-04-16
- **Status:** accepted

## Context

Module 2 (PRD §4) needs a local REST API that serves project state to the
Next.js frontend (Module 3) and Hermes/Telegram commands (Module 4). The
API runs on `localhost:3100` on a single Mac M4, serves one user, and is
read-heavy (kanban aggregation, needs-attention views, token metrics).

Two realistic Python options were considered: **Flask** (battle-tested,
minimal) and **FastAPI** (async-native, pydantic-based schemas, OpenAPI
for free).

## Decision

We will use **FastAPI** for Module 2.

## Consequences

Easier:
- Request/response schemas reuse pydantic models already introduced in
  §6.6 (projects.yaml v2) — no duplicate DTO layer.
- Auto-generated OpenAPI doc at `/docs` satisfies §4 M2 "E2E curl +
  Postman collection" without hand-writing a spec.
- Async subprocess calls to `task-master list --json` don't block the
  event loop if we later aggregate many projects concurrently.

Harder / traded off:
- Slightly heavier dependency footprint vs. Flask.
- One more framework idiom (`Depends`, `HTTPBasic`) to remember; mitigated
  because the code surface is tiny (≤6 endpoints per §4 M2).

Knock-on effects:
- §4 M2 auth ("HTTPBasic when exposed") uses `fastapi.security.HTTPBasic` —
  trivial wiring.
- §6.15 E2E suite targets `localhost:3100` via `httpx`, no change needed.

## References

- PRD §4 Module 2, §6.12 FastAPI auth
