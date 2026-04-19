# kira-hq — Kanban Board
**Last updated:** 2026-04-18T20:55
**Total tasks:** 25 | **Done:** 15 | **In progress:** 0 | **Needs attention:** 0

## 🔴 Wymaga Twojej uwagi (0)

## ⛔ Blocked (0)

## 🟡 In progress (0)

## ✅ Done today (0)

## 📥 Backlog (10)
- **16** — Module 2 FastAPI backend: all endpoints — priority: high — deps: [1,2,3,5,9] — uvicorn 127.0.0.1:3100 with 7 endpoints matching PRD.
- **18** — Module 3 Next.js frontend Phase 3a (localhost:3001) — priority: high — deps: [16] — Dashboard pages + Playwright E2E matching PRD §6.15 scenario exactly.
- **20** — Module 4 Hermes skills: report + weekly-review + add-project — priority: high — deps: [7,8,12,16] — Skills consumable by Hermes scheduler + manual Claude invocation.
- **21** — Module 4 Telegram commands: /status /blockers /add /fix /review /unstale — priority: high — deps: [4,11,16,20,24] — 6 command handlers with chat-ID allow-list.
- **22** — Parallel track harness: Path A (Hermes) vs Path B (Claude Code) — priority: high — deps: [1,11] — Dual cron paths + weekly comparator + ADR 0002 placeholder.
- **25** — Execution wrapper: provider-aware task expansion (kira-hq-execute skill) — priority: high — deps: [20,22,1,11] — Wrapper skill kira-hq-execute that detects active LLM provider and decides task 
- **17** — Module 2 auth: HTTPBasic when exposed — priority: medium — deps: [4,16] — Localhost = no auth; when KIRA_HQ_EXPOSED=true, HTTPBasic dependency gates every
- **23** — Definition-of-Done checker + top-level README (vision/users/architecture) — priority: medium — deps: [1,8,14,16,18,20] — Automated §6.17 checker refusing to emit 'done' on gaps + README capturing §1/§2
- **24** — Weekly review ritual skill (full impl, Saturday 09:00) — priority: medium — deps: [1,2,10,22] — 7-section review → ~/.kira-hq/reviews/YYYY-WW.md + Telegram summary.
- **19** — Module 3 Phase 3b: Vercel deploy + HTTPBasic middleware — priority: low — deps: [17,18] — Gated deploy after 3a stable ≥1 week; Basic auth at edge; ADR 0003 captures deci

## 🐛 Fixes reported (0)

## 📚 ADRs — last 1 (of 1 total)

- **0001** — [Use FastAPI (not Flask) for Module 2](docs/ADR/0001-use-fastapi-not-flask.md) — accepted — 2026-04-16
