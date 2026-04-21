# Kira-HQ frontend app (Module 3)

Module 3 ships the operator-facing Next.js frontend for Kira-HQ. It renders the approved dashboard surfaces, proxies browser requests to the FastAPI backend, and keeps a mock mode so the UI remains explorable during backend outages or local-only frontend work.

## Routes/pages shipped in Module 3

The shipped app exposes 6 user-facing routes/pages:

1. `/` — **Projects** overview with project cards, progress, and status counters.
2. `/projects/[name]` — **Project detail** page with a 4-column kanban (`pending`, `in-progress`, `blocked`, `done`) and selectable task cards.
3. `/tasks/new` — **Add Task** form for creating a task in a selected project.
4. `/views/needs-attention` — **Needs Attention** dashboard with the 5 trigger sections used by QA.
5. `/views/blockers` — **Blockers** table listing blocked tasks and reasons.
6. `/hermes` — **Hermes** embed page with iframe plus a permanent “open in new window” escape hatch.

Known route note: the approved prototype used `/add`; the shipped Module 3 app uses `/tasks/new`. Existing docs/spec references to `/add` should be read as the task-create page now mounted at `/tasks/new`.

## Environment variables

Client-visible env:

- `NEXT_PUBLIC_API_URL` — backend base URL used by the server-side proxy when no server override is set. Default: `http://localhost:3100`.
- `NEXT_PUBLIC_MOCK` — set to `1` to enable mock/fallback data in the frontend fetch layer.
- `NEXT_PUBLIC_HERMES_URL` — target URL for the Hermes iframe and popout link. Default: `http://localhost:4000`.

Server-side env used by the proxy/auth layer:

- `KIRA_HQ_API_URL` — optional server-only override for the backend base URL. If present, this wins over `NEXT_PUBLIC_API_URL`.
- `KIRA_HQ_USER` — optional server-only Basic auth username for backend proxy calls.
- `KIRA_HQ_PASS` — optional server-only Basic auth password for backend proxy calls.

`.env.example` currently documents the public vars; if server-side auth is required in your environment, add the `KIRA_HQ_*` vars locally or in deployment secrets.

## Commands

From `frontend/app`:

```bash
npm install
npm run dev
npm run build
npm run start
npm run test:e2e
npm run test:e2e:list
```

Use `npm run dev` for local iteration, `npm run build` as the production compile gate, and `npm run test:e2e:list` / `npm run test:e2e` for Playwright coverage.

## Mock mode vs live mode

### Live mode

When `NEXT_PUBLIC_MOCK` is not `1`, the UI fetches via Next.js route handlers under `/api/*`, and those route handlers proxy to the backend defined by `KIRA_HQ_API_URL` or `NEXT_PUBLIC_API_URL`.

### Mock mode

When `NEXT_PUBLIC_MOCK=1`, reads use mock fallback data if the proxied fetch fails:

- `/` falls back to fixture project cards.
- `/projects/[name]` falls back to fixture project/task data.
- `/views/needs-attention` falls back to the 5 canned attention sections.
- `/views/blockers` falls back to canned blocker rows.

Task creation is intentionally different: the add-task submit path still posts to `/api/projects/[name]/tasks` and does **not** fabricate a client-only success result if the POST fails. In other words, mock mode provides resilient read behavior, but create remains an actual write path and surfaces `Failed` on unsuccessful submission.

## Data flow and proxy layer

Browser code does not call the backend directly. The flow is:

`page/component -> src/lib/api.ts -> frontend /api/* route -> src/lib/server-api.ts -> FastAPI backend`

Proxy routes in Module 3:

- `GET /api/projects`
- `GET /api/projects/[name]/tasks`
- `POST /api/projects/[name]/tasks`
- `GET /api/views/needs-attention`
- `GET /api/views/blockers`

Why this exists:

- keeps backend origin/auth details on the server side,
- allows server-side Basic auth injection,
- gives the frontend a stable same-origin API surface,
- enables read-time mock fallback in `src/lib/api.ts` when backend requests fail.

## Add-task behavior and auth stance

The add-task page at `/tasks/new` collects project, title, description, priority, and optional parent task ID, then posts a `TaskCreate`-shaped payload to `/api/projects/{project}/tasks`.

Important details:

- the selected project is used in the URL path, not duplicated into the JSON body;
- the browser sends JSON to the frontend proxy only;
- optional Basic auth, when configured, is attached server-side inside `src/lib/server-api.ts` using `KIRA_HQ_USER` / `KIRA_HQ_PASS`.

Client-side Basic auth is not shipped because exposing static credentials in browser code would leak backend secrets to every user, every devtools session, and every intercepted request. Module 3 therefore keeps auth attachment on the server boundary and Playwright explicitly verifies that no public Authorization header is emitted by the browser add-task flow.

## Error modes and fallback behavior

- **Backend unavailable + mock mode on (`NEXT_PUBLIC_MOCK=1`)**: read views fall back to built-in mock data so the frontend remains navigable.
- **Backend unavailable + mock mode off**: read fetches throw; pages depending on those requests will not receive data and can fail visibly rather than silently inventing production data.
- **Task create failure**: `/tasks/new` shows `Failed`; it does not fake persistence in mock mode.
- **Hermes iframe blocked** (for example by `X-Frame-Options` / CSP): the embed may fail, but `/hermes` still renders the wrapper and a persistent popout link using `NEXT_PUBLIC_HERMES_URL` so operators can open Hermes directly.
- **Projects list fetch fails on add-task page**: the page keeps a local fallback project list (`kira-hq`, `monopilot`, `sandbox`, `fixture`) so the form still renders.

## Verification evidence (Module 3 DoD)

Module 3 frontend verification is based on one production build gate plus Playwright coverage.

### Build evidence

Observed on this branch from `frontend/app`:

- `npm run build` **passed**.
- Next.js reported `Compiled successfully`, completed static generation, and emitted the expected app routes including `/`, `/projects/[name]`, `/tasks/new`, `/views/blockers`, `/views/needs-attention`, `/hermes`, plus the `/api/*` proxy handlers.

### Playwright evidence

Observed on this branch from `frontend/app`:

- `npm run test:e2e:list` **passed**.
- Current Playwright inventory is **7 specs (7/7 listed)**:

1. `projects.spec.ts` — smoke for projects overview cards/counters.
2. `project-detail.spec.ts` — smoke for project detail kanban layout.
3. `needs-attention.spec.ts` — smoke for all 5 attention sections.
4. `blockers.spec.ts` — smoke for blockers table rows.
5. `hermes.spec.ts` — smoke for Hermes iframe wrapper and popout link.
6. `add-task.spec.ts` — integration coverage for add-task POST shape and no public auth header.
7. `prd-scenario.spec.ts` — integration scenario matching PRD §6.15: 10 visible tasks, inspect first, add, refresh to 11.

For this frontend module:

- **Smoke** means the page renders the expected operator surface and core UI structure.
- **Integration** means the frontend makes the right same-origin API call(s), preserves payload shape, and respects the proxy/auth boundary.

When updating Module 3 behavior, refresh this section with the latest command output rather than leaving generic framework boilerplate.
