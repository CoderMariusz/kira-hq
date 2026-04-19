# Pipeline Log

**PRD reference:** §6.1, §6.19 (token economics column additions)

## What

Append-only markdown-table log recording every skill invocation (cron or manual) across Kira-HQ projects.

## Where

- **Per-project:** `<project>/pipeline.log.md` (e.g. `~/Projects/kira-hq/pipeline.log.md`)
- **Global aggregate:** `~/.kira-hq/global-pipeline.log.md` (union across all projects)

## Schema (10 columns)

```
| timestamp | project | skill | provider | expand_used | tokens_in | tokens_out | status | duration_s | notes |
```

| Column        | Type     | Notes                                                          |
|---------------|----------|----------------------------------------------------------------|
| `timestamp`   | str      | ISO-8601 UTC (e.g. `2026-04-18T03:00:12`)                      |
| `project`     | str      | Matches `name` in `~/.kira-hq/projects.yaml`                   |
| `skill`       | str      | Skill/workflow identifier                                      |
| `provider`    | str      | LLM provider used (sonnet-4.6, kimi-2.6, qwen3-coder, etc.)   |
| `expand_used` | bool     | `true` if `kira-hq-execute` expanded into subtasks (§6.16)    |
| `tokens_in`   | int      | Input tokens consumed                                          |
| `tokens_out`  | int      | Output tokens generated                                        |
| `status`      | enum     | `ok` \| `fail` \| `skip`                                       |
| `duration_s`  | float    | Wall-clock duration in seconds                                 |
| `notes`       | str      | Free-form short note (keep <80 chars)                          |

## API

```python
from kira_hq.pipeline_log import log_execution

log_execution(
    project_path="~/Projects/kira-hq",
    project="kira-hq",
    skill="kira-hq-render-kanban",
    provider="sonnet-4.6",
    expand_used=False,
    tokens_in=0,
    tokens_out=0,
    status="ok",
    duration_s=1.2,
    notes="6 tasks rendered",
)
```

Writes to BOTH per-project and global log in one call. `timestamp` defaults to `datetime.now(timezone.utc)` if omitted.

## Retention

- Per-project logs: unbounded (git history provides snapshots)
- Global log: unbounded for v2.0. If size becomes an issue (~100MB), weekly review skill (§6.18) will propose rollover to monthly files

## Failure handling

`append_entry` is fire-and-forget. If path creation fails, exception propagates to caller (writer skill). No silent swallowing. Callers should catch and fall back (e.g. `kira-hq-execute` wrapper logs to stdout when writer unavailable — MVP phase).

## Consumers

- **`kira-hq-execute`** (T-25) — writes one entry per task/subtask execution
- **FastAPI Module 2** (T-16) — exposes `GET /metrics/pipeline?since=...` reading this log
- **`kira-weekly-review`** skill (T-24, §6.18) — aggregates last 7 days: tokens/project, success rate, top-3 consumers
- **Snapshot backup** (T-10, §6.7) — included in daily rsync

## Token economics integration (§6.19)

- `tokens_in`/`tokens_out` enable weekly top-3 consumer report
- Alert if single run exceeds `budget_tokens_per_run` from projects.yaml v2
- Cache hit rate NOT tracked here (provider-specific — query Hermes analytics API)

## Sample row

```markdown
| 2026-04-18T03:01:05 | monopilot | monopilot-night-crew | sonnet-4.6 | false | 12450 | 3201 | ok | 47.3 | task #5 → reviewed |
```
