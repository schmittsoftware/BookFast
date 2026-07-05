---
name: trace-requirement
description: Use when writing commits, PR descriptions, or module docstrings for BoekVastAI, or when asked to check requirement coverage/traceability. Links code changes to the FR/NFR IDs in requirements-analysis-boekhoudkantoren-ai.md, and flags work that doesn't map to any listed requirement. Trigger on requests like "which FR does this cover", "check requirement coverage", "write a traceable commit message", or before marking a build-order item (gemini.md §6) as done.
---

# Trace Requirement

## Purpose

The requirements analysis defines specific, numbered FR/NFR IDs (FR-01 … FR-51, NFR-01 … NFR-08) and an explicit MVP build order ([gemini.md](file:///Users/alexanderschmitt/Schmitt%20Software/projects/BoekVastAI/BoekVastAI/gemini.md) §6). This skill keeps development traceable back to those IDs so the team — and eventually an auditor or a compliance-conscious kantoor — can answer "what requirement does this code satisfy" without archaeology.

## When writing new code

1. Identify the FR/NFR ID(s) the change implements. Look them up in [requirements-analysis-boekhoudkantoren-ai.md](file:///Users/alexanderschmitt/Schmitt%20Software/projects/BoekVastAI/BoekVastAI/requirements-analysis-boekhoudkantoren-ai.md) §3–4 rather than guessing from memory — ID numbers and priorities matter (Must/Should/Could).
2. If the change doesn't map to any existing ID:
   - Check if it's infrastructure/plumbing that indirectly enables a requirement (acceptable, note the enabled ID).
   - If it's genuinely new product behavior not in the requirements doc, flag this to the user explicitly — don't silently expand scope. Suggest whether the requirements analysis should be updated first.
3. Format commit messages and PR titles as: `<FR/NFR-ID>: <short description>` (e.g. `FR-13: route low-confidence extractions to review queue`). If a change spans multiple IDs, list them comma-separated.
4. Add a one-line docstring/comment at the top of new modules or major functions noting which ID(s) they implement, e.g. `# Implements FR-11 (field extraction), FR-12 (per-field confidence)`.

## When asked to check requirement coverage

1. Walk the requirements table(s) in [requirements-analysis-boekhoudkantoren-ai.md](file:///Users/alexanderschmitt/Schmitt%20Software/projects/BoekVastAI/BoekVastAI/requirements-analysis-boekhoudkantoren-ai.md) §3.
2. For each ID, search the codebase (commit history, docstrings, module names) for a reference.
3. Produce a coverage table: ID | Priority | Status (not started / in progress / done) | Reference (file, commit, or module).
4. Cross-check against the MVP build order in [gemini.md](file:///Users/alexanderschmitt/Schmitt%20Software/projects/BoekVastAI/BoekVastAI/gemini.md) §6 — flag if a later-order item has more implementation than an earlier, higher-priority one. That's a sequencing risk worth surfacing, not silently accepting.
5. Cross-check Must-priority items specifically against the pilot acceptance criteria in [requirements-analysis-boekhoudkantoren-ai.md](file:///Users/alexanderschmitt/Schmitt%20Software/projects/BoekVastAI/BoekVastAI/requirements-analysis-boekhoudkantoren-ai.md) §9 — a Must item with no coverage is a pilot blocker, call it out as such rather than listing it neutrally alongside Could items.

## Output

- Traceable commit/PR message or docstring, as requested
- Or: a coverage table plus a short flagged list of gaps, prioritized by Must > Should > Could and by position in the build order
