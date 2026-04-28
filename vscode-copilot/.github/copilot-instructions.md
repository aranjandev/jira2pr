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

Agents in this project follow a structured, phase-driven workflow: they read a JIRA ticket, plan and implement the change, self-review, and submit a Pull Request. All agent behaviour is coordinated through the files under `.github/`.

### Agent Roster

Five agents are available. Each has a defined scope and model tier:

| Agent | Role | Model |
|-------|------|-------|
| **Orchestrator** | End-to-end feature development orchestrator | Claude Sonnet 4 |
| **JIRA Reader** | Fetches and interprets JIRA tickets | GPT-4o mini |
| **Reviewer** | Reviews code changes for quality, correctness, and risks | Claude Opus 4 |
| **Researcher** | Lightweight research agent for technical investigation | Claude Haiku 3.5 |
| **PR Author** | Handles the final stage of a feature workflow: creating git commits with conventional commit messages, pushing the branch, and finalizing an existing draft PR by updating its state to Ready and marking it as ready for review | Claude Haiku 3.5 |

Agent definitions live in `.github/agents/`. Each file is a `.agent.md` with YAML frontmatter declaring its `description`, `tools`, `model`, and which subagents it may invoke.

### Skills

Skills are reusable, domain-specific instruction sets that agents load on demand. They live in `.github/skills/<skill-name>/SKILL.md`.

| Skill | Purpose |
|-------|---------|
| `read-jira-ticket` | Fetches a JIRA ticket by key or URL and extracts structured requirements including summary, description, acceptance criteria, subtasks, labels, and priority |
| `git-operations` | Performs git operations: creating branches from ticket keys, staging and committing changes with conventional commit messages, and pushing to origin |
| `create-pull-request` | Creates a draft Pull Request using the canonical PR body template |
| `update-pull-request` | Updates an existing PR body by modifying MUTABLE blocks and appending to APPEND-ONLY blocks |
| `summarize-changes` | Analyzes git diff output and produces a human-readable summary of all changes, grouped by component or module |
| `identify-risks` | Analyzes code changes for potential risks: breaking changes, missing error handling, untested paths, security concerns, performance regressions, and missing migrations |

### Agent Prompts

User-facing entry points are defined as `.prompt.md` files in `.github/prompts/`. Invoke them with a `/` slash command in the Copilot chat:

| Prompt | Slash command | What it does |
|--------|---------------|--------------|
| `feature.prompt.md` | `/feature` | Full feature workflow — start fresh from a JIRA ticket, or resume an in-progress feature from a PR link |
| `bugfix.prompt.md` | `/bugfix` | Bugfix workflow — start fresh from a JIRA ticket, or resume an in-progress bugfix from a PR link |
| `review.prompt.md` | `/review` | Reviews current code changes for quality, risks, and correctness |

### Workflows

Multi-phase workflow definitions live in `.github/agent-workflows/`. The Orchestrator reads the matching workflow file and executes it phase-by-phase:

| Workflow | Trigger | Phases |
|----------|---------|--------|
| `feature.md` | `/feature` | Bootstrap → Understand → Plan → Implement → Review → Submit |
| `bugfix.md` | `/bugfix` | Bootstrap → Understand → Diagnose → Fix → Review → Submit |
| `_resume.md` | Any PR link | Parses PR state and routes to the correct phase to continue |

All workflows include a **Phase 0: Bootstrap** that handles both fresh (JIRA input) and resume (PR link) modes automatically.

### Instructions

Persistent rules that apply across all agents are defined as `.instructions.md` files in `.github/instructions/`:

| File | Scope | What it governs |
|------|-------|-----------------|
| `commit-conventions.instructions.md` | PR bodies / commits | Conventional commit message format and rules for writing git commit messages |
| `pr-schema.instructions.md` | PR bodies / commits | PR state document schema — block definitions, mutability rules, ownership model, idempotency rules, and scope change protocol |
| `pr-template.instructions.md` | PR bodies / commits | Canonical PR body template for agent-maintained pull requests |

### Git Push Authentication for Agents

Agents push code using the `git-operations` skill (`git_helper.py push`). The script reads `.env` at the repo root and injects credentials automatically via `GIT_ASKPASS` — no system credential helper or `gh auth` required.

**Required `.env` variables for HTTPS remotes:**
- GitHub: `GITHUB_TOKEN=<personal-access-token>` (needs `repo` scope)
- Bitbucket: `BITBUCKET_TOKEN=<app-password>` and `BITBUCKET_USERNAME=<your-username>`

SSH remotes do not require these variables.

> **Critical:** If `GITHUB_TOKEN` is absent or expired, `git push` will hang or fail silently. Do **not** attempt to work around this by calling `gh` CLI or modifying the remote URL manually — fix the token in `.env` instead.

### Shell Command Rules for Agents

Applies whenever an agent runs shell commands in a terminal. Violations produce silent, hard-to-debug corruption:

- **Never write file content using heredocs** (`<< 'EOF' ... EOF`) — they get mangled in agent terminal sessions.
- **Never use `python3 -c "..."`  with double outer quotes** — the shell expands `$variables` and backticks inside.
- **Always use `python3 -c '...'` with single outer quotes** and `\n` for newlines — this is the only reliable pattern:
  ```bash
  python3 -c 'open("/tmp/file.md","w").write("line1\nline2\n")'
  # With dynamic values, concatenate inside the expression
  python3 -c 'import datetime; ts=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"); open("/tmp/file.md","w").write("# Title\nTimestamp: "+ts+"\n")'
  ```

### Model Tiers

`.github/model-tiers.json` maps model tiers (0–3) to concrete Copilot model names. The `scripts/apply_model_tiers.py` script stamps the correct model into each agent file at setup time. Tier assignment reflects cost/capability trade-offs:

- **Tier 0** — Cheapest — simple extraction, formatting, and API calls: Simple, deterministic tasks
- **Tier 1** — Light reasoning — templated output, formulaic writing: Formulaic tasks
- **Tier 2** — Strong reasoning — planning, code generation, implementation: Implementation and orchestration
- **Tier 3** — Highest capability — deep analysis, risk assessment, complex review: Thorough review and analysis

