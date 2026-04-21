# Taskmaster commands audit — keep / replace / skip

**Date:** 2026-04-16
**Context:** After `task-master parse-prd` benchmark failure (lost Module 3 silently), audit every other task-master subcommand for similar LLM-driven content-loss risks.

## Risk classification

- **🟢 Safe** — deterministic operation (file I/O, status updates, queries). LLM not involved. Keep.
- **🟡 Caution** — uses LLM, low blast radius. Keep but monitor.
- **🔴 Replace** — uses LLM with high content-loss risk. Replace with deterministic alternative or our own skill.
- **⚫ Skip** — feature we don't need.

## Per-command verdict

### Project setup
| Command | Risk | Verdict | Notes |
|---|---|---|---|
| `init` | 🟢 | KEEP | Pure file scaffold |
| `models --set-*` | 🟢 | KEEP | Edits config.json only |
| `models --setup` | 🟢 | KEEP | Interactive but no LLM call |

### Task generation
| Command | Risk | Verdict | Replacement |
|---|---|---|---|
| `parse-prd` | 🔴 | **REPLACE** with `prd-decompose-hybrid` skill | Benchmark proved content loss (Module 3 dropped silently) |
| `generate` | 🟢 | KEEP | Just splits tasks.json into per-task .md files. No LLM. |

### Task management
| Command | Risk | Verdict | Notes |
|---|---|---|---|
| `list` | 🟢 | KEEP | Read-only |
| `set-status` | 🟢 | KEEP | Pure write of status field |
| `sync-readme` | 🟢 | KEEP | Markdown formatter, no LLM |
| `update --from --prompt` | 🔴 | **AVOID** | LLM rewrites multiple tasks based on free-form prompt → content drift |
| `update-task <id> <prompt>` | 🔴 | **AVOID** | Same risk per single task. If you need to edit a task, edit tasks.json directly OR re-run `prd-decompose-hybrid` on updated PRD |
| `update-subtask --id --prompt` | 🟡 | **OK for status notes only** | Append-mode is lower risk than rewrite. Use sparingly for runtime annotations (e.g. "tried X, failed because Y") |
| `add-task --prompt` | 🔴 | **AVOID** | LLM expands prompt → unpredictable. Use our own `kira-hq add-project` (T-12) for project onboarding, or write task directly to tasks.json |
| `remove-task --id` | 🟢 | KEEP | Pure deletion, requires `-y` |

### Subtask management
| Command | Risk | Verdict | Notes |
|---|---|---|---|
| `add-subtask --parent --title` | 🟢 | KEEP | Manual title, no LLM |
| `add-subtask --task-id` (convert) | 🟢 | KEEP | Pure restructure |
| `remove-subtask` | 🟢 | KEEP | Pure deletion |
| `clear-subtasks --id` | 🟢 | KEEP | Pure deletion |
| `clear-subtasks --all` | 🟢 | KEEP | Pure deletion |

### Task analysis & breakdown
| Command | Risk | Verdict | Notes |
|---|---|---|---|
| `analyze-complexity` | 🔴 | **SKIP** | LLM scoring, opinionated, no value-add over our DoD-per-task convention |
| `complexity-report` | ⚫ | SKIP | Output of analyze-complexity, irrelevant if we skip that |
| `expand --id` | 🔴 | **REPLACE** with `kira-hq-execute` (T-25) | LLM regenerates subtasks → may drift from plan.md. Our wrapper auto-populates from plan.md byte-for-byte, eliminating drift |
| `expand --all` | 🔴 | **AVOID** | Same risk × N tasks. Never bulk-expand |
| `research` | 🟡 | **OK for ad-hoc only** | LLM web search inside task context. Useful for "research before T-X" workflows. Don't pipe output back into tasks.json automatically |

### Navigation
| Command | Risk | Verdict | Notes |
|---|---|---|---|
| `next` | 🟢 | KEEP | Dependency walker, read-only |
| `show <id>` | 🟢 | KEEP | Read-only |

### Tags
| Command | Risk | Verdict | Notes |
|---|---|---|---|
| `tags` (list) | 🟢 | KEEP | Read-only |
| `tags add` | 🟢 | KEEP | Pure write |
| `tags use` | 🟢 | KEEP | Pure write of state.json |
| `tags remove`/`rename`/`copy` | 🟢 | KEEP | Pure ops |

### Dependencies
| Command | Risk | Verdict | Notes |
|---|---|---|---|
| `add-dependency` / `remove-dependency` | 🟢 | KEEP | Pure edits |
| `validate-dependencies` | 🟢 | KEEP | Read-only check |
| `fix-dependencies` | 🟢 | KEEP | Deterministic graph fix (removes invalid refs) |

## Summary

Of 30+ subcommands:
- **5 use LLM** with high content-loss risk: `parse-prd`, `update`, `update-task`, `add-task --prompt`, `expand`, `analyze-complexity`
- **25+ are safe** deterministic operations (CRUD on tasks.json, status, tags, deps)

**The LLM commands are the only attack surface.** Everything else is safe to use freely.

## Replacement matrix (canonical)

| Task-master cmd you'd reach for | Use instead |
|---|---|
| `parse-prd <prd>` | `prd-decompose-hybrid` skill (Claude/Hermes) |
| `expand --id N` | `kira-hq-execute --task-id N --provider <weak>` (auto-populates from plan.md) |
| `expand --all` | NEVER. Expand per-task on-demand only |
| `analyze-complexity` | We use explicit DoD per task in PRD §6.17 |
| `update --from --prompt` | Edit tasks.json by hand OR re-run `prd-decompose-hybrid` on updated PRD |
| `update-task <id> <prompt>` | Edit tasks.json by hand |
| `update-subtask --id --prompt` | OK for status notes; avoid for content rewrite |
| `add-task --prompt` | `kira-hq add-project` (T-12) for projects; manual JSON for one-off tasks |
| `research <prompt>` | OK ad-hoc; don't pipe to tasks.json |

## Convention going forward

1. **Source of truth** = `prd/master-prd.md` + `docs/plans/<plan>.md` (writing-plans format with code in steps)
2. **Orchestration** = `.taskmaster/tasks/tasks.json` (just IDs, deps, status)
3. **Decomposition** = `prd-decompose-hybrid` skill (PRD → plan + tasks)
4. **Execution** = `kira-hq-execute` skill (provider-aware granularity, plan-sourced subtasks)
5. **Status updates** = `task-master set-status` (deterministic, safe)
6. **Reading** = `task-master list / show / next` (deterministic, safe)

Anything else that touches LLM goes through our skills, not task-master directly.
