# Project Instructions

<!-- CUSTOMIZE: Replace with a brief description of your project — what it does, who uses it, and its primary purpose. -->
## Overview

...

<!-- CUSTOMIZE: Replace with your project's language stack, formatting and linting tools, and any style rules agents should follow when generating or editing code. -->
## Code Style

- Languages: ...
- Formatter: ...
- Key conventions: ...

<!-- CUSTOMIZE: Describe your project's architecture — type of project, key directories, major modules, and how they relate. -->
## Architecture

- Project type: ...
- Key directories:
  - `src/` — ...
  - `tests/` — ...

<!-- CUSTOMIZE: Describe how to build, run, and test the project. Include the commands agents should use to verify their changes compile and tests pass. -->
## Build and Test

```bash
# Install dependencies
...

# Run tests
...

# Build
...
```

<!-- CUSTOMIZE: List any project-specific conventions agents must follow — naming patterns, file organisation rules, patterns to avoid, etc. -->
## Conventions

- ...

<!-- CUSTOMIZE: List runtime and development dependencies, including any CLIs or external services agents will need access to. -->
## Dependencies

- ...

<!-- CUSTOMIZE: Document required environment variables and any external tool authentication agents need (e.g. API tokens, CLI logins). -->
## Environment

- `ENV_VAR_NAME` — Description of what it's for
- GitHub CLI (`gh`) must be authenticated via `gh auth login`
- JIRA credentials:
  - `JIRA_API_TOKEN` — Personal access token for JIRA REST API
  - `JIRA_BASE_URL` — Base URL of your JIRA instance (e.g., `https://yourcompany.atlassian.net`)

<!-- AGENTS_SECTION:AUTO_GENERATED -->

## How Agents Contribute to Code

> This section is managed by the jira2pr agent setup. Do not remove or modify it — agents rely on it to understand available agents and workflows.

Agents in this project execute **workflows** — deterministic state machines defined in `{{CORE_DIR}}/workflows/*.workflow.yaml` (e.g. `feature`). Each state names a worker agent, the artifacts it consumes/produces, and success criteria. The **orchestrator** agent is the entry point: for each state it invokes the named worker, then invokes **supervisor** to evaluate that worker's output against the state's success criteria and return `success`, `failure`, or `escalate`, which the orchestrator uses to transition to the next state.

Workflow state is the single source of truth and lives outside `{{AGENTS_DIR}}/`, in `{{CORE_DIR}}/state/<TICKET-KEY>.yaml` — this keeps it identical regardless of which platform (Copilot, Aider) is executing the workflow. Artifacts produced along the way (`requirements.md`, `plan.md`, `review.md`, ...) are written under `{{CORE_DIR}}/artifacts/<TICKET-KEY>/`.

**State lifecycle (feature workflow):** `jira-ingest` → `plan` → `implement` → `review` → `submit` → `done` (or `human-review` on escalation). Retries are bounded per state (`retry.max_attempts`); exhausting retries escalates rather than looping forever.

### State & Artifact Architecture

| Layer | Location | Audience | Owner |
|-------|----------|----------|-------|
| **Workflow state** | `{{CORE_DIR}}/state/<TICKET-KEY>.yaml` | Agents — source of truth | runtime executor only; workers read, never write |
| **Artifacts** | `{{CORE_DIR}}/artifacts/<TICKET-KEY>/<name>.md` | Agents + human reviewers | produced by the worker named in the current state |
| **PR body** | GitHub PR (live) | Human reviewers | `pr-author`, once the `submit` state runs |

The state file is committed to git alongside code changes so context survives session restarts. At workflow completion it is archived to `{{CORE_DIR}}/state/archive/<TICKET-KEY>.yaml`.

<!-- AGENTS_SECTION:DYNAMIC_TABLES -->
