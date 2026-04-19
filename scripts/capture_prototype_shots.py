"""Capture 1440x900 screenshots of every prototype page for user review.

Usage:  .venv/bin/python scripts/capture_prototype_shots.py
Writes: frontend/screenshots/{01-projects,02-detail,03-needs,04-blockers,05-add,06-hermes}.png
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[1]
PROTO = REPO / "frontend" / "prototype.html"
OUT = REPO / "frontend" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("01-projects.png",        "#/"),
    ("02-project-detail.png",  "#/projects/kira-hq"),
    ("03-needs-attention.png", "#/views/needs-attention"),
    ("04-blockers.png",        "#/views/blockers"),
    ("05-add-task.png",        "#/add"),
    ("06-hermes.png",          "#/hermes"),
]


def main() -> int:
    if not PROTO.exists():
        print(f"missing {PROTO}", file=sys.stderr)
        return 1

    url_base = "file://" + str(PROTO.resolve())
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()
        for fname, route in PAGES:
            page.goto(url_base + route, wait_until="networkidle")
            # Wait for the route template to render
            page.wait_for_function(
                "document.querySelector('main#app').children.length > 0",
                timeout=3000,
            )
            out = OUT / fname
            page.screenshot(path=str(out), full_page=True)
            print(f"✓ {out.relative_to(REPO)}")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
