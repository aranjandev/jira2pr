# Project Instructions

## Overview

This repo curates ready-to-use configuration files that enable AI coding agents to work end-to-end — from reading a JIRA ticket to submitting a Pull Request. Each top-level folder contains a complete setup for a specific tool/IDE combination. End users copy the relevant setup folder into their project, customize the templates, and start using agents immediately.

## Code Style

- Languages: Markdown, Shell script (Bash/Zsh), Python, JSON
- Formatter: None enforced — keep Markdown clean and consistent with existing files
- Shell scripts: Use `set -euo pipefail`, quote variables, prefer `$()` over backticks
- Key patterns to follow: see `vscode-copilot/.github/` for the canonical example of a setup folder

## Architecture

- Project type: Multi-folder template collection (not a runnable application)
- Key directories:
  - `vscode-copilot/` — Complete VS Code + GitHub Copilot agent setup (agents, skills, prompts, workflows, instructions, scripts)
  - `.github/` — This repo's own Copilot config (used when developing this repo itself)
- Each setup folder mirrors the structure expected by its target tool:
  - `vscode-copilot/.github/` contains `agents/`, `skills/`, `prompts/`, `agent-workflows/`, `instructions/`, `scripts/`, `model-tiers.json`, and `copilot-instructions.md`
- Future setup folders (e.g., `claude-code/`, `cursor/`) will follow the same pattern: self-contained, copy-and-customize

## Build and Test

This repo has no build step or runtime dependencies. Validation is manual:

```bash
# Verify Python scripts are syntactically valid
python3 -m py_compile vscode-copilot/.github/scripts/apply_model_tiers.py
python3 -m py_compile vscode-copilot/.github/skills/git-operations/scripts/git_helper.py
python3 -m py_compile vscode-copilot/.github/skills/read-jira-ticket/scripts/fetch_jira.py
python3 -m py_compile vscode-copilot/.github/skills/create-pull-request/scripts/pr_helper.py

# Check JSON is valid
python3 -m json.tool vscode-copilot/.github/model-tiers.json > /dev/null
```

## Conventions

- All template files that users must customize contain `<!-- CUSTOMIZE: ... -->` comment markers explaining what to fill in
- Agent files (`.agent.md`) include YAML frontmatter with `description`, `tools`, and `model` fields
- Skill files live in `skills/<skill-name>/SKILL.md` with structured sections (Description, When to Use, Steps, Output Format)
- Instruction files (`.instructions.md`) include YAML frontmatter with `description` and `applyTo` globs
- Prompt files (`.prompt.md`) are user-facing entry points (e.g., `/feature`, `/bugfix`)
- Workflow files define multi-step sequences for GitHub Actions or agent orchestration
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) — see `.github/instructions/commit-conventions.instructions.md`
- Keep template content generic and project-agnostic; users fill in specifics

## Dependencies

- No runtime dependencies
- Shell scripts require `curl`, `jq`, `gh` (GitHub CLI) — documented in each setup's README
- No package registries; this is pure configuration

## Environment

- Required env vars for the agent tools (used when developing/testing this repo):
  - `JIRA_API_TOKEN` — Personal access token for JIRA REST API
  - `JIRA_BASE_URL` — Base URL of your JIRA instance (e.g., `https://yourcompany.atlassian.net`)
  - GitHub CLI (`gh`) must be authenticated via `gh auth login`


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
- **Never use `python3 -c "..."` with double outer quotes** — the shell expands `$variables` and backticks inside.
- **Always use `python3 -c '...'` with single outer quotes** and `\n` for newlines — this is the only reliable pattern:
  ```bash
  python3 -c 'open("/tmp/file.md","w").write("line1\nline2\n")'
  # With dynamic values, concatenate inside the expression
  python3 -c 'import datetime; ts=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"); open("/tmp/file.md","w").write("# Title\nTimestamp: "+ts+"\n")'
  ```


### Model Tiers

`.github/model-tiers.json` maps model tiers (0–3) to concrete Copilot model names. The `scripts/apply_model_tiers.py` script stamps the correct model into each agent file at setup time. Tier assignment reflects cost/capability trade-offs:

- **Tier 0** — Cheapest (GPT-4o mini): simple, deterministic tasks like reading tickets
- **Tier 1** — Lightweight (GPT-4o mini / Haiku): formulaic tasks like committing and pushing
- **Tier 2** — Capable (Claude Sonnet): complex reasoning and implementation
- **Tier 3** — Most powerful (Claude Opus): thorough review and risk analysis
