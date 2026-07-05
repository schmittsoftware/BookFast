# CLAUDE.md — BoekVastAI

This file is read automatically by Claude Code at the start of every session in this repo. It defines what this project is, the decisions already made, and the ground rules that must hold across all future work — including work done in future sessions with no memory of this one.

**Read the full context docs before non-trivial design/scope decisions:**
- `project-overview-boekhoudkantoren-ai.md` — business context, roles, phase plan
- `requirements-analysis-boekhoudkantoren-ai.md` — full FR/NFR list, data requirements, acceptance criteria
- `01-requirements-en-storyboards.md` — requirements synthesis + 3 storyboards
- `02-diagrammen.md` — system flow diagrams + high-level architecture (Mermaid)

---

## 1. What this is

An AI-assisted workflow layer for small independent Belgian accounting firms (3–15 employees). It does **not** compete on invoice OCR/booking (commoditized by Yuki/Silverfin/Exact/Billit). It automates the layer around that: document intake, classification, human-reviewed extraction, client follow-up drafting, and dossier preparation. Currently in the 90-day validate → pilot → sell phase; the first working slice must support a real pilot with 2 accounting firms.

## 2. Stack & tooling

- **Backend:** Python, FastAPI. Not Node/TS — decided for this build.
- **Package management:** `poetry` (preferred) or `pip` with `requirements.txt` if the project hasn't standardized yet — check for `pyproject.toml` before assuming.
- **Testing:** `pytest`. Every new module needs tests before being considered done, especially anything touching confidence-threshold routing (FR-12/13) or tenant scoping (NFR-06).
- **Lint/format:** `ruff` for linting, `black` for formatting. Run both before considering a change complete.
- **LLM/AI calls:** use managed LLM APIs (not self-hosted models) — team is solo/small, per constraint in requirements section 7.
- **Storage:** EU-region only (e.g., S3-compatible in an EU region). Never default to a non-EU region in config or examples.

Run checks with (adjust once `pyproject.toml`/`Makefile` exist):
```
pytest
ruff check .
black --check .
```

## 3. Non-negotiable architecture rules

These come directly from decisions already locked in `project-overview-boekhoudkantoren-ai.md` §8 and the NFRs. Do not silently deviate — if a task seems to require deviating, stop and flag it instead of proceeding.

1. **Raw/extracted separation is physical, not conventional.** Inbound data (`InboundItem`, `Attachment`) is stored immutable and untouched. AI-interpreted data (`ExtractedData`) lives in a separate store/table and is always reproducible from the raw item. Never let a "fix" touch the raw record.
2. **Multi-tenant from day one.** Every core entity (`InboundItem`, `Client`, `Case`, `Action`, `AuditLog`, etc.) carries `org_id`. Every query must be scoped by `org_id` — there is no code path where one kantoor's data can be visible to another (NFR-06). Treat a missing tenant filter as a bug, not a style nit.
3. **Extracted fields are schema-flexible JSON**, not rigid relational columns — invoice fields and general request/document fields are structurally different. Validation lives in application code, not the DB schema.
4. **Confidence is per-field, not per-document.** Every extracted field carries its own confidence score (FR-12). A document isn't "high confidence" or "low confidence" as a whole — individual weak fields route to review while the rest can proceed.
5. **Never a silent failure path.** If extraction fails or confidence is low, the item goes to the human review queue — never dropped, never silently retried into nothing (NFR-05). If you're writing an error branch, ask "where does this land for a human to see?" before merging.
6. **No config-only-breaking changes.** Onboarding a new kantoor must not require new code (NFR-07). New source/channel logic belongs in configuration (`Organization`/`Source` records), not per-tenant conditionals in application code.
7. **Outbound client communication requires human approval before sending, in the pilot phase.** No code path may auto-send a follow-up message without an explicit approval step (FR-31). Treat this as a compliance/trust boundary, not a temporary MVP shortcut to be "optimized away."

## 4. Explicitly out of scope — do not build or propose

- Any integration with Yuki, Silverfin, Exact Online, or Billit (booking push, API sync, etc.). Deferred post-pilot, revisit only if a kantoor explicitly asks.
- Any automatic submission of data to tax/government systems.
- Replacing or migrating the kantoor's core bookkeeping software.
- Financial or tax advice generation of any kind.
- A mobile app — the web upload form is sufficient for the pilot.

If a task seems to imply any of the above, stop and confirm with the user rather than assuming it's now in scope.

## 5. Data model (target — build incrementally, don't over-engineer upfront)

Core entities per `requirements-analysis-boekhoudkantoren-ai.md` §5:

`Organization` (kantoor) · `Source` (channel config) · `InboundItem` (raw, immutable) · `Attachment` · `ExtractedData` (flexible JSON + confidence + review status) · `Client` (kantoor's own customer) · `Case`/`Dossier` · `Action`/`Task` (follow-up drafts awaiting approval) · `AuditLog`

No formal ERD/migrations exist yet as of this writing — if you're the first to touch persistence, propose the schema explicitly before writing migrations, and check whether a data-model doc has since been added to this repo.

## 6. Build order (do not reorder without discussion)

The MVP-critical slice, in dependency order:

1. FR-01 — email intake
2. FR-05 — immutable raw storage
3. FR-06 — sender-to-client matching
4. FR-10 — document classification
5. FR-11 — field extraction
6. FR-12 — per-field confidence scoring
7. FR-13 — low-confidence routing to review
8. FR-20 — review screen (original + extracted fields side by side)

Everything else (WhatsApp intake, follow-up automation, dossier export, dashboards) is real product value but not blocking for running an actual pilot. Don't let it creep ahead of the slice above without the user asking for it explicitly.

## 7. Working conventions for Claude Code sessions

- **All feature work follows the cycle in `docs/WORKFLOW.md`** (run the `feature-cycle` skill): evaluate → select one slice → data model → design → artifact gate → build → review. One slice per cycle; artifacts live in `docs/features/<slug>/`; tempting extras go to `docs/BACKLOG.md`, never into the running slice. Do not write feature code outside an active cycle whose artifact gate has passed.
- Reference the FR/NFR ID a change implements in commit messages and PR descriptions where applicable (e.g. `FR-11: add vendor/amount/date extraction`). See the `trace-requirement` skill.
- Before adding a new intake channel or a new module, check `.claude/skills/` for a matching skill (`add-intake-channel`, `scaffold-module`) rather than freehand-scaffolding — they encode the raw/extracted and multi-tenant conventions above.
- Run the `check-multi-tenant` skill's checklist on any new query or endpoint that touches a core entity, before considering it done.
- This is a two-person team building toward a paying pilot in 90 days, not an enterprise platform. Prefer boring, well-understood solutions over clever ones. A non-technical kantoor owner and a solo/two-person team both need to be able to trust and operate whatever gets built.
