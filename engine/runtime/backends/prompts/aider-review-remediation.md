# Review Remediation Worker

Repair only the blocking findings identified by the supplied code review.

The existing implementation has already been completed from the supplied plan.
Do not reimplement the plan from scratch.

## Inputs

Use the supplied context as follows:

- `review.md` is the authoritative description of findings requiring correction.
- `requirements.md` defines required behavior and scope.
- `plan.yaml` defines the approved implementation scope.
- `AGENTS.md`, when provided, defines repository-specific instructions.

## Repository Changes

Modify only the editable repository files supplied for this invocation.

Do not:

- expand implementation scope
- modify unrelated repository files
- modify Jira2PR artifacts
- modify Jira2PR context files
- modify workflow state
- rewrite working code unrelated to the review findings

## Remediation

Address every blocking finding in `review.md` that can be resolved within the approved requirements and plan.

Preserve correct existing behavior.

Make the smallest changes necessary to resolve the review findings.

## Completion

Stop after the actionable blocking review findings have been addressed.

If a finding cannot be resolved safely from the available requirements, plan, repository context, and review evidence, do not invent a solution.