# Parallel track comparison

Task 22 implements the Track A weekly comparator as a lightweight report over the existing pipeline log schema.

## Source of truth

- Input: `pipeline.log.md` in the existing 10-column schema.
- Track selection: read from `notes` via `track=A` or `track=B`.
- No schema changes are required or allowed for this report.

## Metrics

The comparator produces one weekly markdown table grouped by track with:

- tasks completed — summed from `tasks_completed=<n>` in `notes`
- tokens — `tokens_in + tokens_out`
- human interventions — count of rows carrying an `incident=...` reference in `notes`
- alerts — summed from `alerts=<n>` in `notes`
- avg latency — average `duration_s` for rows in the ISO week

## Script

Run:

```bash
python scripts/parallel_track_compare.py --pipeline-log ~/.kira-hq/global-pipeline.log.md
```

Optional `--now <iso8601>` pins the ISO week for deterministic reporting and tests.

## Example notes field

```text
track=A tasks_completed=2 alerts=1 incident=INC-100
```

Only rows with an explicit `track=A` or `track=B` tag participate in the comparison.
