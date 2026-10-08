# Architecture Decision Memo

**Maximum length: 500 words**

## Decision
Ship **single** as the MVP. Keep the staged boundary available for a later
review-heavy workflow.

## Evidence
Summarize the comparison using the same evaluation set.

| Metric | Single agent | Staged / 2-agent |
|---|---:|---:|
| Cases passing your quality criteria | 6/6 | 6/6 |
| Avg latency | 6.6 ms | 6.5 ms |
| Avg LLM calls | 0 | 0 |
| Avg tool calls | 7 | 8 |
| Notable policy/grounding failures | None in public cases | None in public cases |

## Trade-offs
Both modes pass all public minimum checks. Staged mode gives an explicit evidence
handoff that is easier to inspect and extend, but adds one orchestration boundary
and one telemetry event. Neither mode uses paid model calls, so latency and cost
are dominated by the risk API and local lookups.

## Risks / limitations
Before production, validate authorization around every data source, real API
timeouts/retries, policy versioning, adversarial request text, regional privacy
rules, and human approval audit trails. The local fallback is conservative but is
not a substitute for a production risk-service cache or SLA.

## Why this is the right MVP
The client needs grounded recommendations and deterministic controls more than
open-ended generation. Single is the smallest auditable workflow: tools gather
facts, deterministic rules decide required reviews, and humans retain authority.
Staged is useful when evidence review needs a separate owner, but it adds
complexity without improving the current public results.
