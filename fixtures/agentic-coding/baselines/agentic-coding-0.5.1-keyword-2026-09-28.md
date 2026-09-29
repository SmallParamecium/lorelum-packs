# Retrieval evaluation: agentic-coding-queries vs agentic-coding@0.5.1

- Generated: 2026-09-28T08:08:27+00:00  |  lore 0.1.0-alpha.3  |  mode(s): keyword  |  top-k threshold: 3
- Store: tmp\issue26-release-store  |  Queries: 176 runnable, 0 skipped, 0 retired
- Source: store

## keyword — gate PASSED (positive top-3 99.1% vs fixture minimum 90.0%)

- Positive queries: top-1 93.4% (106 queries), top-3 99.1%
- Neighbor queries: expected selected top-1 58.6% (70 queries), in top-3 88.6%, trap top-1 (query selects the Practice it resembles) 20.0%

Positive queries that missed top-3 (rewrite-priority input):

| query | actual top-3 |
|---|---|
| `testing.anchor-tests-to-requirements.p3` | implementation.choose-smallest-sufficient-design, testing.justify-regression-protection, planning.keep-acceptance-path-completable |

Most confused neighbor selections (queries worded near 'resembles' that selected 'actual top-1' instead of the expected neighbor):

| resembles | actual top-1 selection | count |
|---|---|---|
| `testing.justify-regression-protection` | `testing.justify-regression-protection` | 2 |
| `requirements.ground-user-goal` | `requirements.ground-user-goal` | 1 |
| `requirements.define-acceptance-and-non-goals` | `requirements.define-acceptance-and-non-goals` | 1 |
| `requirements.define-acceptance-and-non-goals` | `planning.derive-committed-set-from-concerns` | 1 |
| `planning.plan-sufficient-evidence` | `requirements.define-acceptance-and-non-goals` | 1 |
| `planning.decide-scope-and-stop-conditions` | `planning.decide-scope-and-stop-conditions` | 1 |
| `planning.keep-acceptance-path-completable` | `implementation.preserve-responsibility-boundaries` | 1 |
| `implementation.limit-investigation-to-current-decision` | `implementation.limit-investigation-to-current-decision` | 1 |

> Evaluation-only evidence: observed retrieval selection for the fixture queries on one machine and one Pack revision. It is not a claim about content quality, other queries, other modes that were unavailable, or downstream Agent behavior.
