---
name: scaffold-module
description: Use when starting a new backend module/service for BoekVastAI (e.g. classification, review queue, dossier grouping, reporting). Scaffolds FastAPI routers, Pydantic models, and persistence layers that conform to the raw/extracted data separation and multi-tenant conventions in CLAUDE.md. Trigger on requests like "start the review queue module", "scaffold the dossier service", "set up the extraction module".
---

# Scaffold Module

## Purpose

Keep every new backend module structurally consistent with the architecture decisions already locked in for this project, so modules don't drift into ad-hoc patterns as the team grows past two people.

## Before scaffolding

1. Identify which architecture zone this module belongs to (see `02-diagrammen.md` and CLAUDE.md §5–6): Intake, Classification/Extraction, Review, Communication, Dossier, or Reporting.
2. Identify which FR/NFR IDs this module implements — list them in the module's docstring or README.
3. Check for an existing shared `db`/`models` layer before creating new base classes — entities like `Organization`, `Client`, `AuditLog` should be shared, not redefined per module.

## Standard module structure (FastAPI/Python)

```
app/
  <module_name>/
    __init__.py
    router.py        # FastAPI routes, org_id resolved from auth/session, never from request body alone
    schemas.py        # Pydantic models — request/response, keep extracted-data fields as flexible JSON, not rigid typed columns
    service.py         # business logic, no direct DB access here if avoidable — keep it testable without a live DB
    repository.py       # persistence layer, every query takes/filters by org_id
    models.py          # ORM models if this module owns new tables
  tests/
    test_<module_name>.py
```

## Non-negotiable checks while scaffolding

1. **org_id on every table and every query.** If `repository.py` has a method that reads/writes a core entity without an `org_id` filter, that's a bug, not a shortcut for later (NFR-06).
2. **Raw vs. extracted separation stays physical.** If this module touches both an `InboundItem`/`Attachment` and `ExtractedData`, they remain separate models/tables with a foreign key, never merged into one record.
3. **No silent failure branches.** Any `except` block or validation failure in `service.py` must route the item to a human-visible state (review queue, error status field) — never a bare log-and-drop (NFR-05).
4. **Confidence lives at the field level** if this module touches extracted data — don't collapse it into a single document-level score.
5. **Config over conditionals.** If you're tempted to write `if org.name == "kantoor_x":`, stop — that behavior belongs in `Organization`/`Source` config, not application code (NFR-07).

## Output

- Module skeleton following the structure above
- At least one test per non-negotiable check above that plausibly applies to this module
- A short note listing which FR/NFR IDs this module now covers, for the user to fold into requirement traceability (see `trace-requirement` skill)
