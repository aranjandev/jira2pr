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

> This section is managed by jira2pr. Do not remove or modify it. Agents rely on it to understand available agents and workflows.

Agents in this project execute **workflows**, deterministic state machines defined in `{{CORE_DIR}}/workflows/*.workflow.yaml` (for example, `feature`). Each state defines its worker, consumed and produced artifacts, success criteria, retry policy, and transitions.

Workflow execution depends on the platform:

1. **Agent-driven platforms** such as Copilot and OpenCode use the **orchestrator** agent. It invokes the worker for the current state, asks the **supervisor** to evaluate the result, applies the workflow-defined transition, and persists state.
2. **Runtime-driven platforms** such as Aider do not use an orchestrator agent. The jira2pr runtime invokes workers and the **supervisor**, applies workflow-defined transitions, and persists state.

The **supervisor** has the same role in both models: evaluate completed worker output against the state's success criteria and return `success`, `failure`, or `escalate`. It does not define the next state; transitions come from the workflow YAML.

Workflow state is the single source of truth and lives at `{{CORE_DIR}}/state/<TICKET-KEY>.yaml`, independent of the execution platform. Artifacts produced during execution (`requirements.md`, `plan.md`, `review.md`, etc.) are stored under `{{CORE_DIR}}/artifacts/<TICKET-KEY>/`.

**Example feature lifecycle:** `jira-ingest` → `plan` → `implement` → `review` → `submit` → `done` (or `human-review` on escalation). The selected workflow YAML is authoritative. Retries are bounded per state; exhausting retries escalates rather than looping indefinitely.

### State & Artifact Architecture

| Layer | Location | Owner |
|-------|----------|-------|
| **Workflow state** | `{{CORE_DIR}}/state/<TICKET-KEY>.yaml` | workflow executor; workers read, never write |
| **Artifacts** | `{{CORE_DIR}}/artifacts/<TICKET-KEY>/<name>.md` | worker assigned to the current state |
| **PR body** | GitHub PR | `pr-author` during `submit` |

The state file is committed with the workflow changes so execution can resume across sessions. On completion, it is archived to `{{CORE_DIR}}/state/archive/<TICKET-KEY>.yaml`.

<!-- AGENTS_SECTION:DYNAMIC_TABLES -->