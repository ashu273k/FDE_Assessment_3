# Workflow and Architecture Notes

## Shared workflow

```text
Request
  -> request / employee / budget / catalog / history tools
  -> vendor registry + vendor-risk API
  -> required-field, injection, overlap, budget and threshold checks
  -> security / privacy / legal rules
  -> ProcurementDecision
  -> optional Google Gemini reviewer context
  -> human approvals (no autonomous purchase)
```

## Visible tools

`request_lookup`, `employee_lookup`, `budget_lookup`, `vendor_registry_lookup`, `software_catalog_lookup`, `purchase_history_lookup`, and `vendor_risk_api` are separate tools in telemetry. The first six are deterministic data tools. The policy engine is also deterministic and is the source of truth for thresholds, budget comparisons, review dates, and required specialist approvals.

## Architecture A: single

One orchestration pass gathers evidence and invokes the policy engine. It has no LLM dependency in the decision path, so outputs are reproducible and auditable. A failed risk call produces `vendor_risk_unavailable` and manual review rather than a favorable assumption.

## Architecture B: staged / 2-agent variant

Stage 1 gathers and normalizes evidence. An explicit `staged_evidence_handoff` then passes that fact bundle to stage 2, which applies the same policy engine and formats the contract. This creates a reviewable boundary without duplicating business rules or adding model calls.

## Optional Google reviewer context

When `GOOGLE_API_KEY` is configured, the Streamlit UI can request a short Gemini summary of the already-collected evidence. This note is advisory only. It does not modify `ProcurementDecision`, required approvals, risk flags, or the human-review requirement. If the API is unavailable, the deterministic result remains available.

## Handoff and escalation

The handoff contains the request, requester/department, budget, catalog matches, purchase history, vendor registry record, risk-service result/error, and the fixed policy reference date (`2026-09-30`). Missing data, prompt injection, conflicts, stale assessments, and specialist reviews are surfaced in structured fields. Human review is always required.

## Intentionally not built

The copilot does not approve spend, purchase software, modify budgets, accept legal terms, or override Security, Privacy, Legal, Finance, or Procurement.
