---
description: "Run the feature workflow end-to-end from a JIRA ticket."
agent: "supervisor"
argument-hint: "JIRA ticket key (e.g., PROJ-123) or URL"
---

# /feature

Execute the `feature` workflow defined in `.jira2pr/workflows/feature.workflow.yaml`, starting from `jira-ingest`.

## States

| State | Worker | Success Criteria | Max Attempts |
|-------|--------|-------------------|---------------|
| `jira-ingest` | `jira-reader` | `jira-ingest` | 1 |
| `plan` | `planner` | `planning` | 2 |
| `implement` | `coder` | `implementation` | 2 |
| `review` | `reviewer` | `review` | 1 |
| `submit` | `pr-author` | `submit` | 1 |
| `done` | — | terminal (outcome: success) | — |
| `human-review` | — | terminal (outcome: escalated) | — |

For each non-terminal state: invoke the named worker agent, then invoke `supervisor` to evaluate its output against the state's success criteria (see `.github/instructions/workflow-protocol.instructions.md` for the full protocol and `.jira2pr/artifacts/` for artifact schemas). Persist the outcome to `.jira2pr/state/<TICKET-KEY>.yaml` before transitioning to the next state.
