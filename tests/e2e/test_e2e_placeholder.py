"""E2E smoke placeholder — marker-deselected by default.

Real E2E tests (Playwright) live here under @pytest.mark.e2e. They hit a
running FastAPI (localhost:3100) and Next.js (localhost:3001) — see PRD
§4 M2/M3. To run:

    cd ~/Projects/kira-hq
    npx playwright install chromium   # once
    .venv/bin/python -m pytest -m e2e tests/e2e/

Landing this file alongside the Playwright config gives T-16/T-18 a
ready-to-extend scaffold without introducing a failing test today.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


@pytest.mark.e2e
def test_e2e_placeholder_skipped_by_default():
    # Only reachable when user opts in with `-m e2e`.
    pytest.skip("E2E scaffolding placeholder — replace when Module 2/3 land (T-16/T-18)")
