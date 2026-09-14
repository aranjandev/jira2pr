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

Agents in this project execute **workflows** — deterministic state machines defined in `.jira2pr/workflows/*.workflow.yaml` (e.g. `feature`). Each state names a worker agent, the artifacts it consumes/produces, and success criteria; the **supervisor** agent evaluates the worker's output against those criteria and returns `success`, `failure`, or `escalate`, which drives the transition to the next state.

Workflow state is the single source of truth and lives outside `.github/`, in `.jira2pr/state/<TICKET-KEY>.yaml` — this keeps it identical regardless of which platform (Copilot, Aider) is executing the workflow. Artifacts produced along the way (`requirements.md`, `plan.md`, `review.md`, ...) are written under `.jira2pr/artifacts/<TICKET-KEY>/`.

**State lifecycle (feature workflow):** `jira-ingest` → `plan` → `implement` → `review` → `submit` → `done` (or `human-review` on escalation). Retries are bounded per state (`retry.max_attempts`); exhausting retries escalates rather than looping forever.

### State & Artifact Architecture

| Layer | Location | Audience | Owner |
|-------|----------|----------|-------|
| **Workflow state** | `.jira2pr/state/<TICKET-KEY>.yaml` | Agents — source of truth | runtime executor only; workers read, never write |
| **Artifacts** | `.jira2pr/artifacts/<TICKET-KEY>/<name>.md` | Agents + human reviewers | produced by the worker named in the current state |
| **PR body** | GitHub PR (live) | Human reviewers | `pr-author`, once the `submit` state runs |

The state file is committed to git alongside code changes so context survives session restarts. At workflow completion it is archived to `.jira2pr/state/archive/<TICKET-KEY>.yaml`.


### Agent Roster

7 agents are available:

| Agent | Kind | Model | Artifact |
|-------|------|-------|----------|
| **supervisor** | supervisor | Claude Sonnet 4.6 | — |
| **jira reader** | worker | GPT-5 mini | `requirements-schema.md` |
| **researcher** | worker | Claude Haiku 4.5 | `decision-schema.md` |
| **planner** | worker | Claude Sonnet 4.6 | `plan-schema.md` |
| **coder** | worker | Claude Haiku 4.5 | — |
| **reviewer** | worker | Claude Opus 4.6 | `review-schema.md` |
| **pr author** | worker | Claude Haiku 4.5 | `pr-schema.md` |

Agent definitions live in `.github/agents/`. Each file is a `.agent.md` with YAML frontmatter declaring its `description`, `tools`, and `model`.

### Workflows

| Workflow | Initial State | States |
|----------|---------------|--------|
| `feature` | `jira-ingest` | `jira-ingest`, `plan`, `implement`, `review`, `submit`, `done`, `human-review` |

### Capabilities

| Capability | Type | Resolution |
|------------|------|------------|
| `diff.read` | context | native platform tool |
| `git.commit` | action | `python3 runtime/integrations/git.py commit <message>` |
| `git.push` | action | `python3 runtime/integrations/git.py push` |
| `git.status` | context | `python3 runtime/integrations/git.py status` |
| `jira.read` | context | `python3 runtime/integrations/jira.py <ticket_key_or_url>` |
| `pr.update` | action | `python3 runtime/integrations/github.py update --pr-number <pr_number> --body-file <body_file>` |
| `test.results` | context | native platform tool |
| `web.search` | context | native platform tool |

### Model Tiers

- **Tier 0** — Cheapest — simple extraction, formatting, and API calls: Simple, deterministic tasks (GPT-5 mini)
- **Tier 1** — Light reasoning — templated output, formulaic writing: Formulaic tasks (Claude Haiku 4.5)
- **Tier 2** — Strong reasoning — planning, code generation, implementation: Implementation and orchestration (Claude Sonnet 4.6)
- **Tier 3** — Highest capability — deep analysis, risk assessment, complex review: Thorough review and analysis (Claude Opus 4.6)

