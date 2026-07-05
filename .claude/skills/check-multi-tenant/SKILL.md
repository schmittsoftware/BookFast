---
name: check-multi-tenant
description: Use before finishing any change that adds or modifies a database query, API endpoint, or background job touching core BoekVastAI entities (Organization, Client, InboundItem, ExtractedData, Case, Action, AuditLog). Audits the diff for tenant-isolation gaps per NFR-06. Trigger on requests like "check this for multi-tenant issues", "review tenant isolation", or proactively before marking a data-touching task complete.
---

# Check Multi-Tenant Isolation

## Purpose

NFR-06 states one kantoor's data must never be visible to another — described in the requirements as a baseline requirement, not optional, from day one. This is the kind of bug that's invisible in a single-tenant pilot with one test kantoor and catastrophic the moment a second one is onboarded. This skill is a mechanical checklist to run before considering data-layer work done.

## Checklist

Walk the diff (or the module, if reviewing existing code) and check each item explicitly — don't skim.

1. **Every query against a core entity filters by `org_id`.** Core entities: `Organization`, `Source`, `InboundItem`, `Attachment`, `ExtractedData`, `Client`, `Case`/`Dossier`, `Action`/`Task`, `AuditLog`. A `SELECT`, ORM query, or aggregation missing an `org_id` filter is a finding, even if "it's fine because there's only one tenant right now."
2. **`org_id` is resolved from a trusted source** (authenticated session, API key → org mapping, or webhook signature → registered Source), never taken directly from an unauthenticated request body or query parameter. Flag any endpoint where a client could pass an arbitrary `org_id`.
3. **Joins don't leak across tenants.** If a query joins two tables (e.g. `Case` to `InboundItem`), confirm both sides are scoped to the same `org_id` — a missing join condition can silently return cross-tenant rows even when each table individually has an `org_id` column.
4. **Background jobs/batch processes iterate per-org, not globally.** A nightly job that computes dashboards or checks for missing documents must process one `org_id` at a time or explicitly group by it — never run an ungrouped query across all orgs and split client-side after the fact.
5. **Error messages and logs don't cross-contaminate.** Confirm error responses or audit log entries triggered by org A's request never surface identifiers or content belonging to org B (e.g. in a "similar document" suggestion or a generic error path).
6. **Tests exist for the negative case**, not just the positive one: a test that inserts data for org A and org B, then asserts a query scoped to org A returns zero rows from org B — not just that org A's own data comes back correctly.

## Output

Report findings as a short list: file/line, what's missing, and the fix (usually "add `.filter(org_id=...)`" or "resolve org_id from session, not from payload"). If everything checks out, say so explicitly rather than silently passing — this is a trust-critical checklist and the user should see it was actually run, not assumed.
