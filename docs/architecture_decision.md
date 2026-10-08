# Architecture Decision Memo

## Decision
Ship **single** as the MVP. Keep the staged boundary available for a later review-heavy workflow.

## Evidence
Both architectures were evaluated against the same six public cases.

| Metric | Single agent | Staged / 2-agent |
|---|---:|---:|
| Cases passing minimum checks | 6/6 | 6/6 |
| Average latency | 6.6 ms | 6.5 ms |
| Average LLM calls | 0 | 0 |
| Average tool calls | 7 | 8 |
| Public policy/grounding failures | None | None |

## Trade-offs
Both modes pass all public minimum checks. Staged mode provides an explicit evidence handoff that is easier to inspect and extend, but adds one orchestration boundary and one telemetry event. The deterministic policy engine remains the source of truth in both modes.

## Risks and limitations
Before production, validate authorization around every data source, real API timeouts and retries, policy versioning, adversarial request text, regional privacy rules, and human approval audit trails. The local fallback is conservative but is not a substitute for a production risk-service cache or SLA. Google Gemini is used only for optional reviewer context in the UI; it cannot approve, purchase, or override deterministic controls.

## Why this is the right MVP
The client needs grounded recommendations and deterministic controls more than open-ended generation. Single is the smallest auditable workflow: tools gather facts, deterministic rules decide required reviews, and humans retain authority. Staged is useful when evidence review needs a separate owner, but it adds complexity without improving the current public results.
