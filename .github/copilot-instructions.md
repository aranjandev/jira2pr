# Project Instructions

## Overview

`jira2pr` is a multi-agent framework for AI-assisted feature development. It reads a JIRA ticket, then plans, implements, reviews, and submits a Pull Request, with developer supervision at every step. It runs on GitHub Copilot (agent-driven, `--platform copilot`) or on a Python runtime that uses LiteLLM and Aider (runtime-driven, `--platform runtime`). Its audience is developers who want AI agents to build features in a JIRA-tracked, git-based workflow.

## Code Style

- Languages: Python (3.10+; `.python-version` pins 3.11), Markdown, YAML, JSON
- Formatter: none enforced. Lint with `ruff` (default rules, no repo config); run `make lint` (`FIX=1 make lint` to auto-fix)
- Key conventions:
  - Keep canonical content (`canonical/`) generic and project-agnostic. Platform-specific details belong in `canonical/platform-extras/<platform>/`.
  - Use `from __future__ import annotations` and type hints in Python modules, following `engine/jira2pr/cli.py`.
  - Keep Markdown and YAML consistent with the existing files in `canonical/`.

## Architecture

- Project type: Python package (`engine/`) plus canonical definitions (`canonical/`). The canonical definitions are compiled into platform-specific output. This is not a standalone application.
- Key directories:
  - `canonical/` — Platform-agnostic source of truth for agents, workflows, artifact schemas, capabilities, and state templates. **Edit here, not in generated output.**
  - `engine/compiler/` — `assembler` package. Validates canonical definitions and renders platform output (`assembler/platforms/copilot.py`, `runtime.py`).
  - `engine/runtime/` — Workflow engine (`workflow/`), LLM backends (`backends/`), integrations for git, GitHub, and JIRA (`integrations/`), and artifact validation (`artifacts/`).
  - `engine/jira2pr/` — CLI entry point (`jira2pr init|check|run|resume|status|list|clear-cache`).
  - `engine/tests/` — Unit tests (pytest). `conftest.py` loads `canonical/` from the repo root.
  - `docs/` — Architecture notes (`platform-strategy.md`).
  - `.github/` and `.jira2pr/` — Generated output for Copilot and the platform-neutral core. Do not hand-edit; regenerate with `jira2pr init`.

## Build and Test

Run these from the repository root unless noted. They require [`uv`](https://docs.astral.sh/uv/).

```bash
# Install jira2pr from this checkout (editable)
make install

# Run the unit test suite
make test

# Lint with ruff (FIX=1 to auto-fix)
make lint

# Regenerate platform output from canonical/ (Copilot), then verify it is up to date
jira2pr init --platform copilot --target-dir <project-root>
jira2pr check --platform copilot --target-dir <project-root>
```

Alternative setup without `uv`, from `engine/`:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pytest tests/ -q
```

## Conventions

- All canonical definitions live in `canonical/`. Never edit generated output (`.github/`, `.jira2pr/`, `AGENTS.md`) directly; edit the source and re-run `jira2pr init`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/). See `.github/instructions/commit-conventions.instructions.md`.
- Workflow semantics must stay independent of the execution platform (Copilot, Aider, or future platforms). Platform differences belong in the platform shell.
- Keep the `AGENTS_SECTION:AUTO_GENERATED` block in this file intact. It is managed by `jira2pr`.
- Runtime data (workflow state under `.jira2pr/state/`, artifacts under `.jira2pr/artifacts/`) is never written by the compiler.

## Dependencies

- Python 3.10+ (3.11 recommended, per `.python-version`)
- `uv` for `make install`, `make test`, and `make lint`
- Runtime dependencies (`engine/pyproject.toml`): `PyYAML`, `aider`, `litellm`, `mcp`, `tree-sitter`, `tree-sitter-language-pack`
- Dev dependencies (`engine/pyproject.toml` dependency group `dev`): `pytest`, `ruff`
- External CLIs and services:
  - `git`
  - `gh` (GitHub CLI), used for PR operations
  - JIRA REST API access
  - Bitbucket or GitHub API access for PR creation
  - Model-provider credentials for the runtime platform (models are listed in `canonical/platform-extras/runtime/models.yaml`)

## Environment

Copy `.env.example` to `.env` at the project root and never commit it. The runtime and the PR integrations read these variables:

- `JIRA_BASE_URL` — Base URL of your JIRA instance, no trailing slash (e.g., `https://yourcompany.atlassian.net`)
- `JIRA_EMAIL` — Email for your JIRA account (`JIRA_USER` is accepted as a legacy alias)
- `JIRA_API_TOKEN` — JIRA API token, generated at `https://id.atlassian.com/manage-profile/security/api-tokens`
- `GITHUB_TOKEN` — GitHub PAT with pull request read and write access (required for PR creation via the REST API, unless `gh` is authenticated)
- `BITBUCKET_TOKEN` and `BITBUCKET_USERNAME` — Bitbucket app password and username, used instead of `GITHUB_TOKEN` for Bitbucket repositories
- GitHub CLI (`gh`) can be used instead of `GITHUB_TOKEN`. Authenticate it with `gh auth login`.

<!-- AGENTS_SECTION:AUTO_GENERATED -->

## How Agents Contribute to Code

> This section is managed by jira2pr. Do not remove or modify it. Agents rely on it to understand available agents and workflows.

Agents in this project execute **workflows**, deterministic state machines defined in `.jira2pr/workflows/*.workflow.yaml` (for example, `feature`). Each state defines its worker, consumed and produced artifacts, success criteria, retry policy, and transitions.

Workflow execution depends on the platform:

1. **Agent-driven platforms** such as Copilot and OpenCode use the **orchestrator** agent. It invokes the worker for the current state, asks the **supervisor** to evaluate the result, applies the workflow-defined transition, and persists state.
2. **Runtime-driven platforms** such as Aider do not use an orchestrator agent. The jira2pr runtime invokes workers and the **supervisor**, applies workflow-defined transitions, and persists state.

The **supervisor** has the same role in both models: evaluate completed worker output against the state's success criteria and return `success`, `failure`, or `escalate`. It does not define the next state; transitions come from the workflow YAML.

Workflow state is the single source of truth and lives at `.jira2pr/state/<TICKET-KEY>.yaml`, independent of the execution platform. Artifacts produced during execution (`requirements.md`, `plan.yaml`, `review.md`, etc.) are stored under `.jira2pr/artifacts/<TICKET-KEY>/`.

**Example feature lifecycle:** `jira-ingest` → `plan` → `implement` → `review` → `submit` → `done` (or `human-review` on escalation). The selected workflow YAML is authoritative. Retries are bounded per state; exhausting retries escalates rather than looping indefinitely.

### State & Artifact Architecture

| Layer | Location | Owner |
|-------|----------|-------|
| **Workflow state** | `.jira2pr/state/<TICKET-KEY>.yaml` | workflow executor; workers read, never write |
| **Artifacts** | `.jira2pr/artifacts/<TICKET-KEY>/<name>.md` | worker assigned to the current state |
| **PR body** | GitHub PR | `pr-author` during `submit` |

The state file is committed with the workflow changes so execution can resume across sessions. On completion, it is archived to `.jira2pr/state/archive/<TICKET-KEY>.yaml`.


### Agent Roster

8 agents are available:

| Agent | Kind | Model | Artifact |
|-------|------|-------|----------|
| **orchestrator** | orchestrator | `GPT-5.6 Luna (copilot)` | — |
| **supervisor** | supervisor | `GPT-5.6 Luna (copilot)` | — |
| **jira-reader** | worker | `GPT-5.6 Luna (copilot)` | `requirements-schema.md` |
| **researcher** | worker | `GPT-5.6 Luna (copilot)` | `decision-schema.md` |
| **planner** | worker | `Claude Sonnet 5.5 (copilot)` | `plan.schema.yaml` |
| **coder** | worker | `Claude Haiku 5.5 (copilot)` | — |
| **reviewer** | worker | `GPT-6.1 Sol (copilot)` | `review-schema.md` |
| **pr-author** | worker | `Claude Haiku 5.5 (copilot)` | `pr-schema.md` |

### Workflows

| Workflow | Initial State | States |
|----------|---------------|--------|
| `feature` | `jira-ingest` | `jira-ingest`, `plan`, `implement`, `run-tests`, `review`, `submit`, `done`, `human-review` |

### Capabilities

| Capability | Type | Resolution |
|------------|------|------------|
| `diff.read` | context | native platform tool |
| `git.commit` | action | `python3 .jira2pr/runtime/integrations/git.py commit <message> <files_from>` |
| `git.push` | action | `python3 .jira2pr/runtime/integrations/git.py push` |
| `git.status` | context | `python3 .jira2pr/runtime/integrations/git.py status` |
| `jira.read` | context | `python3 .jira2pr/runtime/integrations/jira.py <ticket_key_or_url>` |
| `pr.create` | action | `python3 .jira2pr/runtime/integrations/github.py create --title <title> --body-file <body_file>` |
| `pr.update` | action | `python3 .jira2pr/runtime/integrations/github.py update --pr-number <pr_number> --body-file <body_file>` |
| `test.results` | context | native platform tool |
| `web.search` | context | native platform tool |
