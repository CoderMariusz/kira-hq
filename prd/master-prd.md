# Kira-HQ — Product Requirements Document

## Vision
Kira-HQ is a command center for managing multiple AI-driven projects
in parallel. Each project runs its own pipeline (Taskmaster + skills + Hermes cron),
and Kira-HQ aggregates their state into one dashboard.

## Users
- Primary user: Mariusz (owner, solo)
- Usage pattern: 24/7 local server on Mac M4

## Modules

### Module 1: Markdown Renderer (Phase 0)
- Script that reads projects.yaml
- For each project, reads .taskmaster/tasks.json
- Generates kanban_board.md per project
- Also generates global `needs-attention.md` across all projects

### Module 2: FastAPI Backend (Phase 1 — later)
- REST API exposing project state
- Endpoints:
  - GET /projects
  - GET /projects/{name}/tasks
  - GET /views/needs-attention
  - POST /projects/{name}/tasks (add task/fix)
- Reads tasks.json via `task-master list --json` subprocess

### Module 3: Next.js Frontend (Phase 2 — later)
- Project list page
- Project detail with kanban view
- Cross-project "needs attention" view
- Add task/fix form
- Embedded iframe for Hermes dashboard

### Module 4: Hermes Integration (Phase 3 — later)
- Skill `kira-hq-report` that Hermes calls after each cron cycle
- Telegram commands: /add-task, /status, /fix
