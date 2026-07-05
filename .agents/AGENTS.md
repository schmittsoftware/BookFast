# Workspace Rules for Gemini — BoekVastAI

These rules apply specifically to all work done in this workspace. Follow them strictly.

## Stack & Commands
- **Backend:** FastAPI, SQLAlchemy, pytest, ruff, black.
- **Python Version:** >=3.12 (running in `.venv/`).
- **Run Tests:** `.venv/bin/pytest`
- **Lint Code:** `.venv/bin/ruff check .`
- **Format Code:** `.venv/bin/black --check .`
- **Run App:** `.venv/bin/uvicorn app.main:app --reload`

## Coding Principles
1. **Multi-Tenant Scoping (NFR-06):** Every DB model query MUST check and filter by `org_id` scoped by the logged-in user or source organization. Use the `check-multi-tenant` skill to audit queries before completion.
2. **Immutable Intake (FR-05):** Never modify `InboundItem` or `Attachment` raw records. AI extractions must reside exclusively in `ExtractedData` and corrections in `Correction`.
3. **Graceful Failures (NFR-05):** Never let a pipeline fail silently. Ensure all error pathways route documents to the review queue with an error message.
4. **Field-Level Confidence (FR-12):** Extract fields with individual confidence scores, not just a document-level rating.
5. **No Silent Onboarding Breaks (NFR-07):** Do not write tenant-specific conditionals. Configure all source and organizational details via `Organization` or `Source` tables.

## Development Workflow
- **Link Scheme:** Always format file and line references as clickable links using the `file://` scheme (e.g. `[main.py](file:///Users/alexanderschmitt/Schmitt%20Software/projects/BoekVastAI/BoekVastAI/app/main.py)`).
- **Traceability:** Map code modules, commit messages, and PR summaries to requirement IDs in `requirements-analysis-boekhoudkantoren-ai.md` (e.g., `FR-11`, `NFR-06`).
- **Planning Mode:** For non-trivial modifications, create `implementation_plan.md` and wait for user approval. Maintain `task.md` during execution.
