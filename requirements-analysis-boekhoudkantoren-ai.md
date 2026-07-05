# Requirements Analysis: AI-diensten voor Boekhoudkantoren
### MVP / Pilot Scope — Kempen / Antwerpen accounting firms (3–15 employees)

**Version:** 0.1 (pre-pilot draft)
**Prepared for:** validation-to-pilot phase (first 90 days)
**Status:** Draft — to be revised after validation calls

---

## 1. Purpose & Scope

This document defines the requirements for the system supporting Idea 1: an AI-assisted service layer for small independent accounting firms, starting as a hands-on service and productizing over time.

**Explicit positioning (from competitive check):** core invoice OCR/booking is already commoditized by Yuki, Silverfin, Exact Online, and Billit — all widely used in this market. This system must **not** compete on document recognition itself. It targets the layer *around* the existing software stack: client communication, document chasing, exception handling, and dossier preparation — the work that stays manual even at firms that already "have AI."

**In scope for MVP:** intake of client documents/messages, AI-assisted classification and data extraction, human review workflow, client follow-up automation, dossier preparation support.

**Out of scope for MVP:** replacing existing bookkeeping software, automatic filing of statutory returns, any action that submits data to tax authorities, financial advice generation.

---

## 2. Stakeholders & Actors

| Actor | Description | Primary needs |
|---|---|---|
| **Kantoor owner/partner** | Buyer, decision-maker, 3-15 person firm | Time saved, no added risk, proof before paying |
| **Accountant/bookkeeper (staff)** | Daily user, reviews AI output | Low friction, trustworthy suggestions, fast override |
| **End client (of the kantoor)** | SME/self-employed sending documents | Simple submission channel, timely response |
| **You (service provider)** | Builds/operates the system | Repeatable setup, low support burden per client |

---

## 3. Functional Requirements

Grouped by module, each with a unique ID and MoSCoW priority for the **pilot** (first 2 kantoren, weeks 4–8).

### 3.1 Intake / Ingestion

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | System shall accept documents via a monitored email inbox per kantoor | Must |
| FR-02 | System shall accept documents via a simple web upload form (no login required for end clients) | Must |
| FR-03 | System shall accept documents/messages via WhatsApp | Should |
| FR-04 | System shall deduplicate inbound items using channel-native message IDs | Must |
| FR-05 | System shall preserve the original file unaltered, separate from any extracted/interpreted data | Must |
| FR-06 | System shall record sender identity (email/phone) and attempt to match it to a known client record | Must |
| FR-07 | System shall queue unmatched senders for one-time human confirmation rather than guessing silently | Should |

### 3.2 Classification & Extraction

| ID | Requirement | Priority |
|---|---|---|
| FR-10 | System shall classify each incoming document by type (invoice, receipt, request, unclear) | Must |
| FR-11 | System shall extract key fields per document type (vendor, amount, date, VAT no. for invoices) | Must |
| FR-12 | System shall attach a confidence score to each extracted field, not just the document as a whole | Must |
| FR-13 | System shall route low-confidence extractions to a human review queue automatically | Must |
| FR-14 | System shall allow the confidence threshold to be configured per kantoor and per field type | Could |
| FR-15 | System shall log which model/prompt version produced a given extraction | Should |

### 3.3 Human Review

| ID | Requirement | Priority |
|---|---|---|
| FR-20 | System shall provide a simple review screen showing original document + extracted fields side by side | Must |
| FR-21 | Staff shall be able to correct a field in under 3 clicks/actions | Must |
| FR-22 | System shall record every human correction against the original AI output (for accuracy tracking) | Must |
| FR-23 | System shall show a daily/weekly summary of items pending review, by kantoor | Should |

### 3.4 Client Communication

| ID | Requirement | Priority |
|---|---|---|
| FR-30 | System shall detect missing or incomplete documents for a case and draft a follow-up request | Must |
| FR-31 | Outbound follow-up messages shall require explicit human approval before sending in the pilot phase | Must |
| FR-32 | System shall track whether a follow-up was sent, opened (if possible), and resolved | Should |
| FR-33 | System shall support basic auto-responses to common client questions (status of a document, deadline reminders) | Could |

### 3.5 Dossier / Case Preparation

| ID | Requirement | Priority |
|---|---|---|
| FR-40 | System shall group related inbound items into a case/dossier per client per period | Must |
| FR-41 | System shall generate a summary view per dossier: what's in, what's missing, what needs review | Must |
| FR-42 | System shall export a dossier summary in a format the accountant can act on (PDF or structured note) | Should |

### 3.6 Reporting & Proof of Value

| ID | Requirement | Priority |
|---|---|---|
| FR-50 | System shall track hours/actions saved per kantoor (documents auto-processed vs. manually handled) | Must — this is the pilot's core success metric |
| FR-51 | System shall provide a simple dashboard or weekly report summarizing volume, accuracy, and time saved | Must |

---

## 4. Non-Functional Requirements

| ID | Requirement | Rationale |
|---|---|---|
| NFR-01 | All client financial data must be stored within the EU | GDPR + client expectation; competitors (Yuki) advertise this explicitly |
| NFR-02 | A data processing agreement (verwerkersovereenkomst) must be signable with each kantoor before pilot start | Legal requirement for handling client financial data |
| NFR-03 | System shall maintain a full audit trail: who/what changed which field, when | Required for accountant trust and eventual compliance review |
| NFR-04 | System shall be usable by non-technical staff with under 15 minutes of onboarding | Target users have no IT department |
| NFR-05 | System shall degrade gracefully — if AI extraction fails, item still lands in a human queue, never silently dropped | Trust is the product; a single lost invoice ends the pilot |
| NFR-06 | Multi-tenant isolation: one kantoor's data must never be visible to another | Baseline requirement, not optional, from day one |
| NFR-07 | System shall support onboarding a new kantoor without custom code (config only) | Needed to scale past 2 pilots to 5+ paying clients |
| NFR-08 | Target processing latency: document arrival to review-ready state under 5 minutes | Keeps the "same-day" value proposition credible |

---

## 5. Data Requirements (summary)

Reuses the ingestion model discussed earlier:
- `Organization` (kantoor), `Source` (channel config), `InboundItem` (raw, immutable), `Attachment`, `ExtractedData` (flexible JSON fields + confidence + review status)
- Plus for this layer: `Client` (kantoor's own customer), `Case/Dossier`, `Action/Task` (follow-up drafts awaiting approval), `AuditLog`

Extracted fields must remain schema-flexible (JSON) since invoice fields differ from general document/request fields — do not force a rigid relational schema at this stage.

---

## 6. Integration Requirements

| System | Integration need | Priority |
|---|---|---|
| Email (kantoor's existing inbox or a dedicated address) | Read access via IMAP or forwarding rule | Must |
| Yuki / Silverfin / Exact Online | **Not required for MVP.** Revisit only if a kantoor asks for direct push of approved bookings | Won't (MVP) |
| WhatsApp Business API | Inbound document/message capture | Should |
| Storage (EU-hosted, e.g. S3-compatible in an EU region) | Raw file storage | Must |

Deliberately **not** integrating with the kantoor's core bookkeeping software for MVP — it adds scope, security surface, and vendor negotiation before you've proven the workflow layer has value. Revisit post-pilot.

---

## 7. Constraints & Assumptions

- **Constraint:** Budget/timeline caps this at <€5.000 startup cost and a 90-day validate-pilot-sell cycle — this must stay a thin, config-driven system, not a platform build.
- **Constraint:** Solo/small team building this — favor managed services and existing LLM APIs over self-hosted infrastructure.
- **Assumption:** Pilot kantoren are willing to route a subset of real client documents through the system (not synthetic test data) — validate this explicitly in discovery calls, it's a hard blocker if false.
- **Assumption:** Kantoren already use Yuki, Silverfin, or Exact — confirm per prospect, since this changes which gap actually matters to them.

---

## 8. Out of Scope for MVP (explicitly)

- Automatic submission of any data to government/tax systems
- Replacing or migrating existing bookkeeping software
- Financial/tax advice generation
- Full API integration with core accounting platforms
- Mobile app (web form is sufficient for pilot)

---

## 9. Acceptance Criteria for Pilot Success (weeks 4–8)

The pilot is considered successful, and ready to convert to a paying engagement, if:

1. At least 70% of inbound documents are classified with a confidence score, and the confidence threshold correctly predicts which need human review (measured against actual correction rate)
2. Measured time saved per kantoor is clearly attributable and defensible in a sales conversation (FR-50/FR-51)
3. Zero incidents of a document being lost or silently mishandled
4. Kantoor staff report the review workflow as "faster than what we did before" in a direct follow-up conversation

---

## 10. Immediate Next Actions

1. Confirm with 2–3 validation-call prospects: which bookkeeping software they use, and how much of the "last mile" (chasing, exceptions, dossier prep) is still manual despite it
2. Lock the confidence-threshold and review-queue design (FR-12/13) before writing any extraction code — this is the trust mechanism the whole pitch depends on
3. Set up EU-region storage and a template data processing agreement before touching any real client document
4. Build FR-01, FR-05, FR-06, FR-10, FR-11, FR-12, FR-13, FR-20 first — this is the minimum slice that lets you run a real pilot
