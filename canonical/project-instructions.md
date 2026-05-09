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

> This section is managed by the jira2pr agent setup. Do not remove or modify it — agents rely on it to understand available tools and workflows.

Agents in this project follow a structured, phase-driven workflow: they read a JIRA ticket, plan and implement the change, self-review, and submit a Pull Request. All agent behaviour is coordinated through the files under `{{AGENTS_DIR}}/`.

The workflow maintains **two state layers in parallel** — the PR body (human-facing, updated via the `update-pull-request` skill) and a per-workflow state file under `{{AGENTS_DIR}}/state/` (agent-facing working memory, updated via the `manage-state` skill). Both layers must be kept in sync at every phase transition; neither alone is sufficient.

**Phase lifecycle:** `Planning` → `Implementing` → `Reviewing` → `Submitting` → `Ready`. The orchestrator drives all phase transitions and owns both state layers throughout. The pr-author acts only in the final phase: it commits and pushes code, finalizes the PR (marking it `Ready`), archives the state file, and registers the artifact.

### State & Artifact Architecture

The framework tracks state at two levels:

| Layer | File | Audience | Skill | Owner |
|-------|------|----------|-------|-------|
| **PR body** | GitHub PR (live) | Human reviewers + agents | `update-pull-request` | orchestrator (all phases), pr-author (finalize) |
| **Workflow state file** | `{{AGENTS_DIR}}/state/<TICKET-KEY>.md` | Agents only | `manage-state` | orchestrator (all phases), pr-author (archive) |

> **Invariant:** Both layers must be updated together at every phase boundary. Updating one without the other leaves the workflow in an inconsistent state.

The state file is committed to git alongside code changes so context survives session restarts. At workflow completion the pr-author archives it to `{{AGENTS_DIR}}/state/archive/<TICKET-KEY>.md`. The artifact registry at `{{AGENTS_DIR}}/artifacts/REGISTRY.md` receives exactly one append-only entry per completed workflow via the `register-artifact` skill.

<!-- AGENTS_SECTION:DYNAMIC_TABLES -->
