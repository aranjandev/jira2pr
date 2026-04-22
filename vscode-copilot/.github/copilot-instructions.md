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

### Git Push Authentication

Agents push code using the `git-operations` skill (`git_helper.py push`). The script reads `.env` at the repo root and injects credentials automatically via `GIT_ASKPASS` — no system credential helper or `gh auth` required.

**Required `.env` variables for HTTPS remotes:**
- GitHub: `GITHUB_TOKEN=<personal-access-token>` (needs `repo` scope)
- Bitbucket: `BITBUCKET_TOKEN=<app-password>` and `BITBUCKET_USERNAME=<your-username>`

SSH remotes do not require these variables.

> **Critical:** If `GITHUB_TOKEN` is absent or expired, `git push` will hang or fail silently. Do **not** attempt to work around this by calling `gh` CLI or modifying the remote URL manually — fix the token in `.env` instead.

---

## Shell Command Rules

> This section is managed by the jira2pr agent setup. Do not modify.

Applies whenever an agent runs shell commands in a terminal. Violations produce silent, hard-to-debug corruption:

- **Never write file content using heredocs** (`<< 'EOF' ... EOF`) — they get mangled in agent terminal sessions.
- **Never use `python3 -c "..."` with double outer quotes** — the shell expands `$variables` and backticks inside.
- **Always use `python3 -c '...'` with single outer quotes** and `\n` for newlines — this is the only reliable pattern:
  ```bash
  python3 -c 'open("/tmp/file.md","w").write("line1\nline2\n")'
  # With dynamic values, concatenate inside the expression
  python3 -c 'import datetime; ts=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"); open("/tmp/file.md","w").write("# Title\nTimestamp: "+ts+"\n")'
  ```

---

## How Agents Contribute to Code

> This section is managed by the jira2pr agent setup. Do not remove or modify it — agents rely on it to understand available tools and workflows.

Agents in this project follow a structured, phase-driven workflow: they read a JIRA ticket, plan and implement the change, self-review, and submit a Pull Request. All agent behaviour is coordinated through the files under `.github/`.

### Agent Roster

Five agents are available. Each has a defined scope and model tier:

| Agent | Role | Model |
|-------|------|-------|
| **Orchestrator** | End-to-end workflow driver — reads the ticket, plans, implements, delegates, and submits the PR | Claude Sonnet 4 |
| **JIRA Reader** | Fetches a JIRA ticket and produces a structured requirements document | GPT-4o mini |
| **Researcher** | Lightweight research — evaluates packages, APIs, and algorithms | GPT-4o mini |
| **Reviewer** | Thorough code review — identifies risks, missing tests, and security issues | Claude Opus 4 |
| **PR Author** | Commits changes, pushes the branch, and finalises the draft PR | Claude Haiku 3.5 |

Agent definitions live in `.github/agents/`. Each file is a `.agent.md` with YAML frontmatter declaring its `description`, `tools`, `model`, and which subagents it may invoke.

### Skills

Skills are reusable, domain-specific instruction sets that agents load on demand. They live in `.github/skills/<skill-name>/SKILL.md`.

| Skill | Purpose |
|-------|---------|
| `read-jira-ticket` | Fetch and parse a JIRA ticket into structured requirements |
| `git-operations` | Create branches, stage commits with conventional messages, and push |
| `create-pull-request` | Open a draft PR with the canonical PR body template |
| `update-pull-request` | Update mutable blocks and append to append-only blocks in an existing PR |
| `summarize-changes` | Produce a human-readable summary of a git diff, grouped by component |
| `identify-risks` | Analyse changes for breaking changes, security issues, and missing tests |

### Agent Prompts

User-facing entry points are defined as `.prompt.md` files in `.github/prompts/`. Invoke them with a `/` slash command in the Copilot chat:

| Prompt | Slash command | What it does |
|--------|---------------|--------------|
| `feature.prompt.md` | `/feature` | Full feature workflow from JIRA ticket to PR, or resume from a PR link |
| `bugfix.prompt.md` | `/bugfix` | Bugfix workflow from JIRA ticket to PR, or resume |
| `review.prompt.md` | `/review` | Standalone code review of current changes |

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
| `commit-conventions.instructions.md` | All commits | [Conventional Commits](https://www.conventionalcommits.org/) format — type, scope, body, footers |
| `pr-schema.instructions.md` | PR bodies | Block definitions, mutability rules, idempotency, and ownership model |
| `pr-template.instructions.md` | PR bodies | Canonical PR body template that agents populate and update |

### Model Tiers

`.github/model-tiers.json` maps model tiers (0–3) to concrete Copilot model names. The `scripts/apply_model_tiers.py` script stamps the correct model into each agent file at setup time. Tier assignment reflects cost/capability trade-offs:

- **Tier 0** — Cheapest (GPT-4o mini): simple, deterministic tasks like reading tickets
- **Tier 1** — Lightweight (GPT-4o mini / Haiku): formulaic tasks like committing and pushing
- **Tier 2** — Capable (Claude Sonnet): complex reasoning and implementation
- **Tier 3** — Most powerful (Claude Opus): thorough review and risk analysis
