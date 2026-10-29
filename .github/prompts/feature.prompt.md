---
description: "Run the feature workflow end-to-end from a JIRA ticket."
agent: "orchestrator"
argument-hint: "JIRA ticket key (e.g., PROJ-123) or URL"
---

# /feature

Execute the `feature` workflow defined in `.jira2pr/workflows/feature.workflow.yaml`, starting from `jira-ingest`.

## States

| State | Worker | Success Criteria | Max Attempts |
|-------|--------|-------------------|---------------|
| `jira-ingest` | `jira-reader` | `jira-ingest` | 2 |
| `plan` | `planner` | `planning` | 3 |
| `implement` | `coder` | `None` | 4 |
| `run-tests` | — (deterministic verification) | — | shared `implement-cycle` (5) |
| `review` | `reviewer` | `None` | shared `implement-cycle` (5) |
| `submit` | `pr-author` | `None` | 1 |
| `done` | — | terminal (outcome: success) | — |
| `human-review` | — | terminal (outcome: escalated) | — |

For each non-terminal state with a worker: invoke the named worker agent. Unless the state sets `validation.supervisor: false`, invoke `supervisor` to evaluate its output against the state's success criteria. For a verification state (no worker): run the project's test and lint commands and treat a zero exit code as success; on failure, route back to `implement` with the output as feedback (see `.github/instructions/workflow-protocol.instructions.md` for the full protocol and `.jira2pr/artifacts/` for artifact schemas). Persist the outcome to `.jira2pr/state/<TICKET-KEY>.yaml` before transitioning to the next state.
