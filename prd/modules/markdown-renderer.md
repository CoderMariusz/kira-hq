# Module: Markdown Renderer

## Goal
Python script that reads projects.yaml + tasks.json files,
renders kanban_board.md for each project.

## Requirements
- Read ~/.kira-hq/projects.yaml
- For each active project:
  - Run `task-master list --json` in project dir
  - Parse result into categories (needs-attention, in-progress, done-today, backlog, fixes)
  - Render Polish/English markdown per section
  - Write to <project>/kanban_board.md
- Also generate ~/.kira-hq/global-kanban.md (cross-project aggregation)

## Technical
- Python 3.12+
- Dependencies: pyyaml, subprocess (stdlib)
- Executable: `python3 scripts/render_kanban.py`
- Exit codes: 0 = success, 1 = projects.yaml not found, 2 = some project errored

## Output Format
Markdown with sections:
- 🔴 Wymaga uwagi
- 🟡 In progress
- ✅ Done today
- 📥 Backlog (sorted by dependencies)
- 🐛 Fixes reported
