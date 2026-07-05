# Project Overview: AI-diensten voor Boekhoudkantoren

**Status:** Pre-pilot / validation phase
**Team:** 2 co-founders — one business/accounting/finance background, one technical
**Last updated:** July 2026

> This document is the shared reference for the founding team and for any AI agent assisting on this project. Read this before making product, technical, or scope decisions — it defines what we're building, for whom, and why, and what's explicitly out of bounds for now.

---

## 1. The Business, in One Paragraph

We sell an AI-assisted workflow service to small independent Belgian accounting firms (3–15 employees, Kempen/Antwerpen region). We are not selling document-OCR or invoice automation — that's already commoditized by tools these firms already use (Yuki, Silverfin, Exact Online). We sell automation of the messy human layer around that software: chasing clients for missing documents, classifying and routing ambiguous inbound items, preparing dossiers for the accountant, and handling routine client communication. We start as a hands-on service (we operate it for them), and productize into standalone software once the workflow is proven.

## 2. Why This, Why Now

- Accountant is a top-shortage profession in Belgium — firms can't hire their way out of the workload problem.
- Firms are digitized (most run Yuki/Silverfin/Exact) but the *last mile* — exceptions, follow-ups, dossier prep — stays manual even at firms that consider themselves automated. One industry source distinguishes "digitizing" (an AI-suggested booking a human still checks) from true automation (untouched unless something's actually wrong) — most firms are stuck at the former.
- This gap is under-served precisely because the big platforms compete on core booking automation, not on this workflow layer.

## 3. Target Customer

- Independent boekhoudkantoor, 3–15 employees, Kempen/Antwerpen
- Already using a modern cloud bookkeeping platform (Yuki, Silverfin, Exact Online, or similar)
- Feels the staffing shortage acutely; open to paying for time savings, but risk-averse about financial data handling
- Decision-maker: owner/partner, reachable directly (small firm, no procurement layer)

## 4. Business Model

| | |
|---|---|
| Phase 1 | Hands-on service, built on existing AI tools, priced per kantoor |
| Setup fee | €2,000–5,000 |
| Recurring | €300–800/month per kantoor |
| Target | 20 kantoren → €10k+ MRR |
| Phase 2 | Productize into self-serve software once workflow is validated across several kantoren |

## 5. Roles

- **Business partner:** accounting/finance domain expertise, client relationships, sales, validation calls, pricing, kantoor-side trust and compliance conversations (verwerkersovereenkomst, GDPR positioning)
- **Technical (you):** system design, build, AI integration, data handling, security/compliance implementation
- **Division of decision authority:** domain/customer/pricing calls → business partner leads; architecture/build/tooling calls → technical partner leads; both weigh in on scope and positioning

## 6. Current Phase & Plan

90-day validate → pilot → sell cycle:
1. **Weeks 1–3:** 20 validation calls — confirm which platform prospects use, and specifically probe how much manual "last mile" work remains despite that platform
2. **Weeks 4–8:** free/cheap pilot with 2 kantoren, measure hours saved
3. **Weeks 9–13:** convert pilot proof into 5 paying kantoren

We are currently past business framing and into technical design, ahead of the validation calls being complete. Architecture decisions below are provisional and should hold up regardless of exact pilot findings, but confidence-threshold tuning and integration scope may shift based on what validation calls surface.

## 7. Product Scope (MVP)

**In scope:** multi-channel document/message intake (email, upload form, WhatsApp), AI classification and field extraction with confidence scoring, human review queue, client follow-up drafting (human-approved before send), dossier/case grouping, time-saved reporting.

**Explicitly out of scope for MVP:** any automatic submission to tax/government systems, replacing the kantoor's core bookkeeping software, financial/tax advice generation, direct API push into Yuki/Silverfin/Exact (revisit post-pilot), mobile app.

Full functional/non-functional requirements: see `requirements-analysis-boekhoudkantoren-ai.md`.

## 8. Technical Decisions Made So Far

| Decision | Choice | Rationale |
|---|---|---|
| Backend stack | Node.js/TypeScript or Python (FastAPI) — not Rust, not Spring Boot | Workload is I/O-bound (webhooks, LLM calls, storage), not compute-bound; solo/small team needs iteration speed over raw performance or enterprise structure |
| Data storage principle | Raw inbound data stored immutable and separate from AI-interpreted data | AI extraction will sometimes be wrong; need audit trail and reprocessing without data loss |
| Extracted-data schema | Flexible JSON fields, not rigid relational columns | Invoice fields and general request fields are structurally different; validation logic lives in application code |
| Tenancy | Multi-tenant from day one, `org_id` on all core entities | Will serve multiple kantoren; isolation is a baseline requirement, not a later add-on |
| Data residency | EU-hosted storage only | GDPR + matches client/market expectation (competitors advertise this explicitly) |
| Trust mechanism | Confidence score per extracted field, routes low-confidence items to human review | This is the core mechanism that makes the system usable by a risk-averse accountant — prioritize getting this right before extraction accuracy tuning |
| Kantoor-software integration | None in MVP | Avoids scope, security surface, and vendor negotiation before workflow value is proven |

## 9. Open Questions (to resolve via validation calls or team decision)

- Auto-match inbound sender to known client, or require human confirmation on first contact? (leaning: human-confirm first time, auto after)
- Exact confidence threshold per field type — needs real extraction data to tune, not guessable upfront
- Whether WhatsApp intake is a Should-have or a Must-have — depends on what validation calls reveal about how kantoren's own clients currently send documents

## 10. Documents in This Project

- `requirements-analysis-boekhoudkantoren-ai.md` — detailed functional/non-functional requirements, data model, acceptance criteria
- This document — shared context/overview

## 11. Ground Rules for AI Agents Working on This Project

- Do not propose kantoor-software (Yuki/Silverfin/Exact) integrations as MVP work — explicitly deferred, see section 7/8
- Do not propose replacing existing bookkeeping software or generating tax/financial advice — out of scope, and a compliance risk
- Any new inbound channel or data type must fit the immutable-raw / flexible-extracted data pattern in section 8
- Prioritize solutions that a non-technical kantoor owner could trust and a solo/two-person team could actually operate — this is a pilot-stage service, not an enterprise platform
