---
name: add-intake-channel
description: Use when adding or scaffolding a new inbound document/message channel for BoekVastAI (e.g. email, web upload form, WhatsApp, or any future channel). Ensures the channel conforms to the immutable-raw-storage pattern, deduplication, sender-matching, and config-only onboarding rules defined in gemini.md and the requirements analysis. Trigger on requests like "add WhatsApp intake", "add a new upload channel", "wire up a new inbox source".
---

# Add Intake Channel

## Purpose

Every intake channel (email, web form, WhatsApp, and any future channel) must funnel into the same immutable `InboundItem` pipeline. This skill exists so a new channel is never scaffolded as a one-off special case that bypasses dedup, sender-matching, or tenant scoping.

## Before writing code

1. Re-read [gemini.md](file:///Users/alexanderschmitt/Schmitt%20Software/projects/BoekVastAI/BoekVastAI/gemini.md) §3 (non-negotiable architecture rules), specifically points 1 (raw/extracted separation), 2 (multi-tenant), and 6 (config-only onboarding).
2. Confirm the requirement ID this channel maps to (FR-01 email, FR-02 web form, FR-03 WhatsApp, or a new ID if this is a genuinely new channel not yet in the requirements doc — if so, flag to the user that the requirements analysis should be updated).
3. Check whether a `Source` configuration model already exists in the codebase. If not, this channel is likely the first — design `Source` as a generic, reusable config record (channel type, org_id, credentials/webhook config, enabled flag), not a channel-specific table.

## Required behavior for any new channel

A new channel implementation must, in this order:

1. **Receive** the inbound payload (webhook, polling, IMAP fetch, etc.) and identify the source `Organization` via `Source` config — never hardcode which kantoor a channel belongs to.
2. **Deduplicate** using the channel-native message ID (email Message-ID, WhatsApp message ID, form-submission token). Reject/ignore duplicates before persisting anything (FR-04).
3. **Persist the raw payload unaltered** as an `InboundItem` + `Attachment`(s), before any interpretation happens (FR-05). This write must happen even if downstream classification/extraction later fails — raw persistence and AI processing are separate steps, never combined into one transaction that could lose the raw item on AI failure.
4. **Attempt sender matching** against known `Client` records for that `org_id` (FR-06). On no match, queue for one-time human confirmation (FR-07) rather than guessing or silently creating a new client record.
5. **Never leak across tenants** — the channel handler must resolve `org_id` from the `Source` config, not from any client-supplied field that could be spoofed.

## Config-only onboarding check

Before finishing, verify: could a second kantoor be onboarded onto this same channel type by adding a new `Source` config row, with zero code changes? If the answer is no, the implementation is too channel-instance-specific — refactor so channel *type* is code, channel *instance* (per kantoor) is config (NFR-07).

## Output

- New/updated channel handler code
- `Source` config schema update if needed
- Tests covering: dedup on repeated message ID, raw persistence surviving a simulated extraction failure, sender-match hit and miss paths, tenant isolation (a payload for org A never resolves against org B's clients)
- A one-line note to the user suggesting whether `requirements-analysis-boekhoudkantoren-ai.md` needs a corresponding FR entry, if this channel wasn't already listed there
