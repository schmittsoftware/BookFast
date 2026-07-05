---
name: feature-cycle
description: Drives one full BoekVastAI feature cycle per docs/WORKFLOW.md — evaluate app state, pick one slice, define data model, design, gate on artifacts, AI-assisted build, review & retro. Resumable; reads the active cycle from docs/features/*/brief.md and continues at the recorded phase. Trigger on "/feature-cycle", "start de volgende cyclus", "nieuwe feature-cyclus", "ga verder met de cyclus", or when the user wants to pick/build the next feature.
---

# Feature Cycle

One cycle = one small feature slice, fully done (evaluated → chosen → modeled → designed → built → reviewed). The process contract is `docs/WORKFLOW.md`; this skill executes it. Never build outside an active cycle.

## Step 0 — Resume or start

1. Look for `docs/features/*/brief.md` with `status` other than `afgerond`/`gestopt`.
2. If one exists: state which cycle and phase is active, and continue at that phase.
3. If none exists: start Phase 1.
4. Multiple active cycles is a process violation — ask the user which one to close or continue before doing anything else.

## Phase 1 — Evaluate (`status` n.v.t. — pre-cycle)

Build an honest snapshot, grounded in commands, not memory:

- Run from `backend/`: `pytest -q`, `ruff check .`, `black --check .` (venv at repo root: `../.venv/bin/...`). Boot check: import the app.
- Inventory what exists: models (`backend/app/models/`), services, routes, adapters, templates (`frontend/`).
- Map coverage against the FR/NFR list in `requirements-analysis-boekhoudkantoren-ai.md` (use the `trace-requirement` skill): done / partial / missing.
- Note debt: failing checks, stubs still in place (extractor, sender), missing tests.

Write the result to `docs/STATE.md` (overwrite; git history preserves old snapshots). Keep it under one page: works / partial / missing / debt / risks.

## Phase 2 — Select one slice (`status: selectie`)

- Candidates come from `docs/BACKLOG.md` + gaps in `docs/STATE.md`. Respect CLAUDE.md §6 build order and §4 out-of-scope list — a conflicting candidate is rejected here, not discovered in Phase 6.
- Score the top candidates briefly (pilot value / effort / risk / dependencies) and give a recommendation, but **the pick is the user's decision — ask.**
- Slice sizing rule: buildable in 1–2 focused sessions. Too big → split and pick the first part.
- Create `docs/features/<slug>/` from `docs/features/_template/`, fill in the brief: why now, scope-wél, **scope-niet (explicit)**, timebox. Set `status: datamodel`.

## Phase 3 — Data model (`status: datamodel`)

- Fill `data-model.md`: new/changed entities, key fields, and relations to **existing** models (Mermaid ERD includes the old entities it touches).
- Walk the CLAUDE.md §3 checklist in the template per entity. Any violation → back to Phase 2 or adjust; log it in the beslissingenlog.
- Note migration impact (dev DB reset vs. Alembic). Set `status: ontwerp`.

## Phase 4 — Design (`status: ontwerp`)

- Storyboard the slice in the brief (trigger → actoren → stappen → uitkomst), same format as `01-requirements-en-storyboards.md`.
- UI work: sketch against the design language in `design/` (or a Claude Design link if the user makes one).
- Write 3–6 **testable** acceptance criteria in the brief. These become tests in Phase 6 and the checklist in Phase 7.

## Phase 5 — Artifact gate

Hard gate — check, then **ask the user for go/no-go**:

- [ ] Brief complete incl. scope-niet and acceptance criteria, ≤1 page
- [ ] Data model complete incl. §3 checklist, ≤1 page
- [ ] Slice fits the timebox
- [ ] No conflict with CLAUDE.md §3/§4

Outcomes: **go** → `status: bouw`. **Shrink/adjust** → back to Phase 2–4, one line in the beslissingenlog. **Stop** → `status: gestopt`, candidate back to BACKLOG.md with the reason. Never write feature code before this gate passes.

## Phase 6 — Build (`status: bouw`)

- Tests first for tenancy (NFR-06) and any routing/threshold rules the slice touches; then implement in small, runnable increments.
- Use existing seams (`app/interfaces.py`, `app/container.py`) — new swappable behavior gets a Protocol + adapter, never provider logic in services. Use `scaffold-module` / `add-intake-channel` where they apply.
- Commit per coherent step with FR/NFR ids (`trace-requirement`).
- **Anti-creep valve:** anything tempting that is not in scope-wél goes to `docs/BACKLOG.md`, one line, and you keep building the slice. If the slice itself must change, log it in the beslissingenlog first.
- Blocked by a wrong earlier decision → go back to the relevant phase, log it, continue. That is the loop working, not failure.

## Phase 7 — Review & retro (`status: review`)

- Fill `review.md`: walk every acceptance criterion with evidence (test name or preview verification), run the checks list (pytest/ruff/black, `check-multi-tenant`, `/code-review` at the user's choice).
- Demonstrate the slice working in the preview.
- Retro: 3 short answers; process fixes go into `docs/WORKFLOW.md`, deferred work into BACKLOG.md.
- Set `status: afgerond`. Next invocation starts Phase 1 fresh — the retro plus new STATE.md feed it.

## Ground rules for this skill

- The brief's `status` field is the single source of truth for where the cycle stands; update it at every phase transition.
- Artifacts stay one page each. If an artifact wants to grow, the slice is too big.
- Two mandatory user decisions per cycle: the feature pick (Phase 2) and the gate (Phase 5). Everything else: recommend and proceed.
