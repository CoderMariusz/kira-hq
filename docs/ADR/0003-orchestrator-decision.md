# ADR 0003: Parallel-track orchestrator decision record

- **Date:** 2026-04-20
- **Status:** proposed

## Context

The product plan for Task 22 asked for `docs/ADR/0002-orchestrator-decision.md` to capture the eventual decision between Track A and Track B.

This repository already has an accepted `docs/ADR/0002-model-routing.md`. Reusing `0002` would create an ADR numbering collision and break the ADR index contract.

## Decision

Reserve a new ADR number for the parallel-track decision record.

This task introduces `ADR 0003` as the safe placeholder for the future final decision between Track A and Track B.

Until a final winner is chosen, `docs/PARALLEL_TRACK.md` and `scripts/parallel_track_compare.py` provide the operational weekly comparison artifact.

## Consequences

### Positive

- Avoids overwriting or renumbering an already accepted ADR.
- Keeps ADR filenames unique and consistent with the ADR index tooling.
- Documents the numbering conflict explicitly for future maintainers.

### Negative

- The plan reference to `0002-orchestrator-decision.md` is now superseded by `0003-orchestrator-decision.md` and should be read that way going forward.
