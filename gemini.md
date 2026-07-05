# gemini.md — BoekVastAI

This file provides context, rules, and guidelines for Gemini (Antigravity) sessions in this repository. It defines what this project is, the decisions already made, and the ground rules that must hold across all future work.

**Read the full context docs before making design/scope decisions:**
- [project-overview-boekhoudkantoren-ai.md](file:///Users/alexanderschmitt/Schmitt%20Software/projects/BoekVastAI/BoekVastAI/project-overview-boekhoudkantoren-ai.md) — business context, roles, phase plan
- [requirements-analysis-boekhoudkantoren-ai.md](file:///Users/alexanderschmitt/Schmitt%20Software/projects/BoekVastAI/BoekVastAI/requirements-analysis-boekhoudkantoren-ai.md) — full FR/NFR list, data requirements, acceptance criteria
- [01-requirements-en-storyboards.md](file:///Users/alexanderschmitt/Schmitt%20Software/projects/BoekVastAI/BoekVastAI/01-requirements-en-storyboards.md) — requirements synthesis + 3 storyboards
- [02-diagrammen.md](file:///Users/alexanderschmitt/Schmitt%20Software/projects/BoekVastAI/BoekVastAI/02-diagrammen.md) — system flow diagrams + high-level architecture (Mermaid)

---

## 1. What this is

An AI-assisted workflow layer for small independent Belgian accounting firms (3–15 employees). It does **not** compete on invoice OCR/booking (commoditized by Yuki/Silverfin/Exact/Billit). It automates the layer around that: document intake, classification, human-reviewed extraction, client follow-up drafting, and dossier preparation. Currently in the 90-day validate → pilot → sell phase; the first working slice must support a real pilot with 2 accounting firms.

---

## 2. Stack & Tooling

- **Backend:** Python, FastAPI.
- **Package Management:** `poetry` (preferred) or `pip` with `requirements.txt` via virtual environment in `.venv/`.
- **Testing:** `pytest` (tests exist under `tests/`).
- **Lint/Format:** `ruff` for linting, `black` for formatting. Run both before completing any changes.
- **LLM/AI calls:** Use managed LLM APIs (not self-hosted models).
- **Storage:** EU-region only (e.g., S3-compatible in an EU region). Never default to a non-EU region.

Run checks and verification with:
```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/black --check .
```

To run the local development server:
```bash
.venv/bin/uvicorn app.main:app --reload
```

---

## 3. Non-Negotiable Architecture Rules

These rules come directly from decisions already locked in the project docs. Do not deviate from these rules:

1. **Raw/Extracted separation is physical, not conventional.** Inbound data (`InboundItem`, `Attachment`) is stored immutable and untouched. AI-interpreted data (`ExtractedData`) lives in a separate store/table and is always reproducible from the raw item. Never let a "fix" touch the raw record.
2. **Multi-tenant from day one.** Every core entity (`InboundItem`, `Client`, `Case`, `Action`, `AuditLog`, etc.) carries `org_id`. Every query must be scoped by `org_id` — there is no code path where one kantoor's data can be visible to another (NFR-06). Treat a missing tenant filter as a bug, not a style nit.
3. **Extracted fields are schema-flexible JSON**, not rigid relational columns — invoice fields and general request/document fields are structurally different. Validation lives in application code, not the DB schema.
4. **Confidence is per-field, not per-document.** Every extracted field carries its own confidence score (FR-12). A document isn't "high confidence" or "low confidence" as a whole — individual weak fields route to review while the rest can proceed.
5. **Never a silent failure path.** If extraction fails or confidence is low, the item goes to the human review queue — never dropped, never silently retried into nothing (NFR-05). If you're writing an error branch, ask "where does this land for a human to see?" before merging.
6. **No config-only-breaking changes.** Onboarding a new kantoor must not require new code (NFR-07). New source/channel logic belongs in configuration (`Organization`/`Source` records), not per-tenant conditionals in application code.
7. **Outbound client communication requires human approval before sending.** No code path may auto-send a follow-up message without an explicit approval step (FR-31).

---

## 4. Explicitly Out of Scope

Do not build or propose:
- Any integration with Yuki, Silverfin, Exact Online, or Billit (booking push, API sync, etc.) during the pilot.
- Any automatic submission of data to tax/government systems.
- Replacing or migrating the kantoor's core bookkeeping software.
- Financial or tax advice generation of any kind.
- A mobile app — the web upload form is sufficient for the pilot.

---

## 5. Target Data Model

Core entities:
- `Organization` (kantoor)
- `Source` (channel config)
- `InboundItem` (raw, immutable)
- `Attachment`
- `ExtractedData` (flexible JSON + confidence + review status)
- `Client` (kantoor's own customer)
- `Case`/`Dossier`
- `ExpectedDocument` (defines what documents are expected for a dossier)
- `Action`/`Task` (follow-up drafts awaiting approval)
- `AuditLog` (tracks changes to fields and objects)

---

## 6. Build Order

The MVP-critical slice, in dependency order:
1. FR-01 — email intake
2. FR-05 — immutable raw storage
3. FR-06 — sender-to-client matching
4. FR-10 — document classification
5. FR-11 — field extraction
6. FR-12 — per-field confidence scoring
7. FR-13 — low-confidence routing to review
8. FR-20 — review screen (original + extracted fields side by side)

---

## 7. Working Conventions for Gemini sessions

- **Traceability:** Reference the FR/NFR ID a change implements in commit messages, PR descriptions, and walkthroughs where applicable (e.g. `FR-11: add vendor/amount/date extraction`).
- **Workspace Customizations:** Use the custom skills defined under [.agents/skills/](file:///Users/alexanderschmitt/Schmitt%20Software/projects/BoekVastAI/BoekVastAI/.agents/skills) to maintain consistency:
  - Use `check-multi-tenant` before completing any change that adds/modifies queries or endpoints.
  - Use `add-intake-channel` when setting up a new intake pipeline.
  - Use `scaffold-module` when scaffolding new services.
  - Use `trace-requirement` to check requirement mapping.
- **Clickable Links:** Always create clickable markdown links using the `file://` scheme for absolute paths of files and line ranges (e.g., [models.py](file:///Users/alexanderschmitt/Schmitt%20Software/projects/BoekVastAI/BoekVastAI/app/models.py)).
- **Planning Mode:** For non-trivial modifications, write an implementation plan (`implementation_plan.md`), request feedback from the user, and obtain approval before writing code. Update `task.md` checklist dynamically.
