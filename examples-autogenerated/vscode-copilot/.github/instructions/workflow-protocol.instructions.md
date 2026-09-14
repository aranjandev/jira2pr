---
description: "How to evaluate worker output and transition between workflow states."
---

# Workflow Protocol

Every state has bounded retries (default max attempts: 1). Exhausting retries **escalates** the workflow rather than looping forever.

## Success Criteria

| Key | Required Labels |
|-----|------------------|
| `implementation` | tests_pass, lint_pass, plan_followed |
| `jira-ingest` | issue_fetched, requirements_extracted |
| `planning` | requirements_covered, implementation_feasible, test_strategy_defined |
| `review` | no_critical_findings |
| `submit` | pr_created |

Evaluation mode: **all_pass** — every label must be satisfied for the outcome to be `success`.

## Supervisor Output Schema

```json
{"outcome": "success|failure|escalate", "reason": "...", "feedback": "...", "violations": []}
```

## Criteria Evaluation Rules

- Each label under the state's success_criteria key must be checked independently against the worker's produced artifacts and repository evidence.
- Any label that cannot be verified as satisfied is appended to `violations` by its label name.
- If `violations` is empty, the outcome is "success".
- If `violations` is non-empty but the cause is objectively fixable by the worker (e.g. missing section, failing test, incomplete artifact), the outcome is "failure" and `feedback` must describe exactly what to fix.
- If `violations` is non-empty and the cause requires information or a decision the worker cannot obtain on its own (conflicting requirements, undocumented architecture decision, missing business input), the outcome is "escalate" instead of "failure" — escalation always takes precedence over failure when human judgment is required.

Terminal states: `done` (outcome: success), `human-review` (outcome: escalated).
