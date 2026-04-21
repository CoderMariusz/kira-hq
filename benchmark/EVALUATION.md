# Benchmark Evaluation — PRD Decomposition (3 approaches)

**Date:** 2026-04-16
**PRD under test:** `~/Projects/kira-hq/prd/master-prd.md` (379 linii, 4 moduły, 18 cross-cutting, macierz §9)
**Approaches:** A=`task-master parse-prd`, B=Superpowers `writing-plans`, C=`prd-decompose-hybrid` (skill stworzony na potrzeby tego benchmarku)

Wszystkie 3 dostały identyczny PRD. Wszystkie 3 produkowały w izolowanych katalogach. Ocena surowa, bez taryf ulgowych.

---

## Wyniki liczbowe

| Metryka                     | A: task-master | B: writing-plans | C: hybrid       |
|-----------------------------|----------------|------------------|-----------------|
| Tasków                      | 35             | 36               | 24              |
| Stepów (mikro-akcji)        | brak (tylko title+desc) | 187              | 165             |
| Tokeny                      | 275 256        | n/d (nie raportuje) | n/d           |
| Wall time                   | 6m32s          | ~50min           | ~50min          |
| Wyjście wykonalne           | tasks.json ✅   | tylko markdown ❌ | tasks.json + plan.md ✅✅ |
| Wykrył typo PRD §6.16       | ❌ NIE          | ✅ TAK            | ✅ TAK           |
| Wykrył drugie/trzecie gap'y | ❌ NIE          | ✅ TAK (4)        | ✅ TAK (10)      |

---

## Coverage — pokrycie treści PRD (NAJWAŻNIEJSZE kryterium)

### A: task-master parse-prd — **MAJOR FAIL**

**Krytyczne content loss potwierdzone.** Z 35 wygenerowanych tasków:

- **Module 3 (Next.js Frontend) — w całości znikł.** Zero tasków dotyczących: Next.js, React, frontend UI, dashboardu, Vercel, Playwright, projekt list page, kanban view page, add-task form, Hermes iframe. **Cały moduł 3 z PRD §4.M3 + §6.13 + §9 macierz M3 = wycięty bez ostrzeżenia.**
- **Macierz §9 (4 moduły × 18 cross-cutting concerns) = zwinęta** w 4 generyczne cross-cutting taski (#29-32). Per-modułowa aplikacja cross-cutting concerns jest stracona.
- **Telegram commands (`/status`, `/blockers`, `/add`, `/fix`, `/review`, `/unstale`)** — zwinięte do jednego stuba (#25).
- **`kira-add-project` jako skill** (PRD §4.M4) — pominięty (tylko CLI w #10).
- **§6.4 SDK pinning** — oznaczony jako medium prio, mimo że PRD traktuje jako fundamentalny.

**Werdykt:** task-master parse-prd **w pełni potwierdza zarzut o content loss**. Nie tylko gubi treść, ale robi to **bez sygnału ostrzegawczego** — outputuje 35 tasków z pewną miną i zostawia użytkownika z fałszywym poczuciem kompletności.

### B: Superpowers writing-plans — **EXCELLENT, brutalnie szczery**

- 30/30 numerowanych sekcji PRD zmapowane
- Wykrył typo §6.16 (jak C)
- **Wykrył też 3 własne gap'y w swoim planie** (uczciwie self-flagowane):
  - GAP-1: brak page'a "Add task form" w jego planie (mimo że PRD §4.M3 wymaga)
  - GAP-3: istniejący Faza 1 renderer nie został przepiętrzony do orchestrator wrapper
  - GAP-4: `/views/needs-attention` ma stuby zwracające 0 zamiast pełnej integracji
- Macierz §9 zweryfikowana **cell-by-cell** (sampling 22 komórek pokazany w coverage doc)
- §7 out-of-scope explicit acknowledged dla każdego z 6 punktów
- §8 open questions seedowane jako proposed ADRs 0003-0005

**Werdykt:** Najbardziej rygorystyczna analiza. Skill ma w DNA "Spec coverage" check i to widać.

### C: prd-decompose-hybrid — **EXCELLENT + executable**

- 26/26 sekcji z treścią pokryte (100%)
- Wykrył typo §6.16 (jak B)
- **Wyłapał 10 buried details** które naive parser by pominął:
  1. `/unstale` Telegram command zakopany w prozie §6.3
  2. `GET /metrics/pipeline?since=...` endpoint stated w §6.1 prose, NIE w §4.M2 endpoint list
  3. `archive-project` jednozdanie na końcu §6.9
  4. Cross-task dep §6.7 ↔ §6.18 (snapshot health check)
  5. §9 matrix M1 cell forces T-8 ↔ T-22 dependency
  6. Drugi symlink target w §6.11 (`~/.hermes/skills/`)
  7. §6.18 graceful degrade dla Hermes autolearn
  8. §6.17 "no partial-done" wymaga automated checker
  9. §3 mid-paragraph "parallel track decision date"
  10. §9 macierz cell-by-cell applicability
- **Wyjście podwójne:** plan.md (writing-plans format, 165 steps) + tasks.json (taskmaster schema, 24 entries) + coverage.md
- DAG: 41 edges, 0 cykli, foundation-first

**Werdykt:** Najlepszy stosunek rygor/wykonalność. Output gotowy do importu do Taskmastera + plan dla człowieka + audit trail.

---

## Inne kryteria (ocena 1-10, surowo)

| Kryterium                 | A | B | C  | Komentarz                                                  |
|---------------------------|---|---|----|------------------------------------------------------------|
| Coverage (no content loss)| 3 | 9 | 10 | A zgubił cały Moduł 3 — to jest dyskwalifikujące          |
| Granularność              | 3 | 9 | 8  | A: tylko title+desc; B: micro 5/task; C: tighter clustering|
| Wykonalność (steps+code)  | 4 | 9 | 9  | A: brak code; B/C: pełne snippets w każdym kroku           |
| Dependencies (DAG)        | 7 | 6 | 9  | A: avg 1.8; B: sequential markdown; C: explicit DAG        |
| Testowalność (DoD/test)   | 5 | 9 | 9  | A: generic testStrategy; B/C: explicit per-task DoD       |
| Priority sanity           | 5 | n/d | 8 | A: SDK workaround = medium (powinno być high)             |
| Audit trail / coverage doc| 0 | 9 | 10 | A: brak; B: ręczna self-review; C: explicit audit MD       |
| Wyjście Taskmaster-ready  | 9 | 0 | 9  | A: native; B: tylko md; C: emituje JSON kompatybilny       |
| Speed                     | 10| 4 | 5  | A: 6m32s; B/C: ~50min                                      |
| **Średnia (ważona)**      |**5.1**|**6.9**|**8.5**| Coverage ma najwyższą wagę                          |

---

## Werdykt — ranking

### 🥇 1 miejsce: **C (prd-decompose-hybrid)**

Najlepszy balans. Łapie wszystko co B + emituje gotowy JSON dla Taskmastera + ma explicit audit trail. Wykrył 10 buried details. Mniej tasków (24) niż B (36) ale lepiej zaklastrowane. Plan + tasks.json + coverage = trzy artefakty pokrywające 3 różne potrzeby (czytanie/wykonanie/audit).

### 🥈 2 miejsce: **B (Superpowers writing-plans)**

Najbardziej brutalnie szczery — sam zgłosił 3 własne gap'y w swoim planie (GAP-1/3/4). Macierz §9 zweryfikowana cell-by-cell. Ale **brak Taskmaster JSON** = trzeba ręcznie konwertować = friction dla pipeline. Plan jest sztuka (3819 linii), ale dla zarządzania Kira-HQ potrzebujemy też danych strukturalnych.

### 🥉 3 miejsce: **A (task-master parse-prd)**

**Zarzut o content loss POTWIERDZONY i to spektakularnie.** Wyciął cały Moduł 3 (Next.js + Vercel + Playwright = ~30% scope frontendu) bez słowa ostrzeżenia. Zwinął macierz §9. Zwinął Telegram commands. Plus mark SDK workaround jako medium zamiast high. Szybki (6m32s) ale szybkość nie kompensuje cichego zgubienia 30% modułu.

---

## Rekomendacja dla Faza 2

**Użyć Approach C (prd-decompose-hybrid).**

Workflow:
1. Wziąć tasks.json z `~/Projects/kira-hq/benchmark/C-hybrid/tasks.json` jako podstawę
2. Skonsultować z planem `C-hybrid/plan.md` per-task podczas wykonania
3. Coverage doc `C-hybrid/coverage.md` jako audit checkpoint
4. **Dodatkowo:** zaadresować §6.16 PRD typo (decyzja użytkownika: usunąć / wypełnić / zachować numerację)
5. **Dodatkowo:** rozważyć GAPy które B znalazł ale C nie (głównie GAP-1: explicit "add task form" frontend page) — porównać z C tasks #18 (Module 3 Phase 3a) czy form jest tam ujęty

**NIE używać Approach A** dla tego PRD ani podobnie złożonych. task-master parse-prd nadaje się tylko do trywialnych PRD (1 moduł, brak cross-cutting, brak macierzy).

**Approach B** przydatny jako sanity check: jeśli kiedyś C będzie miał wątpliwości, B jest najbardziej "paranoidalny" w wykrywaniu własnych gapów.

---

## Co zrobić z istniejącymi 6 taskami w `~/Projects/kira-hq/.taskmaster/`?

Faza 1 wygenerowała 6 tasków modułu markdown-renderer. Te NIE pochodzą z C-benchmark. Opcje:

1. **Merge:** zachować istniejące 6 (renumerować) + zaimportować 24 z C → 30 tasków total
2. **Replace:** wywalić istniejące, użyć tylko 24 z C (C task #8 "Module 1 renderer production-ready upgrade" pokrywa renderer, ale na innym poziomie abstrakcji)
3. **Hybrid:** zachować 6 jako "Module 1 sub-tasks" pod C task #8

Decyzja użytkownika — następny krok.
