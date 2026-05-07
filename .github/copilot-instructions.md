<!-- This file is hand-maintained for the jira2pr repo itself. Do not regenerate with assemble.py. -->

# Project Instructions

## Overview

This repo provides a platform-agnostic multi-agent workflow system that enables AI coding agents to work end-to-end — from reading a JIRA ticket to submitting a Pull Request. All concepts (agents, skills, prompts, workflows, instructions) are defined once in the `canonical/` folder and assembled into platform-specific output folders by scripts in `scripts/`. End users run the assembler to generate a ready-to-use setup for their tool (e.g., VS Code Copilot, Claude Code), then copy the output into their project.

## Code Style

- Languages: Markdown, Shell script (Bash/Zsh), Python, JSON, YAML
- Formatter: None enforced — keep Markdown clean and consistent with existing files
- Shell scripts: Use `set -euo pipefail`, quote variables, prefer `$()` over backticks
- Key patterns to follow: see `canonical/` for authoritative definitions; see `scripts/assembler/` for platform-specific rendering logic

## Architecture

- Project type: Canonical definitions + assembler pipeline (not a runnable application)
- Key directories:
  - `canonical/` — Platform-agnostic source of truth for all agent concepts: agents, skills, prompts, workflows, instructions, and model tiers. **Edit here, not in the output folders.**
    - `canonical/platform-extras/` — Platform-specific fragments (e.g., Copilot frontmatter, CLAUDE.md boilerplate) that the assembler merges in during generation
  - `scripts/` — Assembler pipeline (`assemble.py` + `assembler/` package) that reads `canonical/` and writes platform-specific output
  - `vscode-copilot/` — Generated output for VS Code + GitHub Copilot (reference only; safe to delete and regenerate)
  - `claude-code/` — Generated output for Claude Code (reference only; safe to delete and regenerate)
  - `cursor/` — Planned output for Cursor (in progress; currently empty)
  - `.github/` — This repo's own Copilot config, hand-maintained to guide agents editing `canonical/` source files. **Not** assembler output — the generated reference copy lives in `vscode-copilot/.github/`
- The assembler is invoked as:
  ```bash
  python scripts/assemble.py --target-dir vscode-copilot --platform copilot
  python scripts/assemble.py --target-dir claude-code     --platform claude
  ```
- Adding a new platform means adding a renderer under `scripts/assembler/platforms/` and optional extras under `canonical/platform-extras/<platform>/`

## Build and Test

```bash
# Assemble output for a platform
python scripts/assemble.py --target-dir vscode-copilot --platform copilot
python scripts/assemble.py --target-dir claude-code     --platform claude

# Dry-run: verify no generated file would change (CI check)
python scripts/assemble.py --target-dir vscode-copilot --platform copilot --check

# Run unit tests
python -m pytest tests/

# Verify Python skill scripts are syntactically valid
python3 -m py_compile canonical/skills/git-operations/scripts/git_helper.py
python3 -m py_compile canonical/skills/read-jira-ticket/scripts/fetch_jira.py
python3 -m py_compile canonical/skills/create-pull-request/scripts/pr_helper.py
```

## Conventions

- All canonical definitions live in `canonical/`; never edit generated output in `vscode-copilot/` or `claude-code/` directly
- Each concept type has a `_registry.yaml` in its folder listing all members and their metadata (tier, tools, etc.)
- Agent source files in `canonical/agents/` are plain Markdown — the assembler adds platform-specific frontmatter during generation
- Skill source files in `canonical/skills/<skill-name>/SKILL.md` use structured sections (Description, When to Use, Steps, Output Format)
- Instruction source files in `canonical/instructions/` are plain Markdown — the assembler wraps them with platform-specific headers
- Prompt source files in `canonical/prompts/` are plain Markdown — assembled into `.prompt.md` files for Copilot, `CLAUDE.md` entries for Claude Code, etc.
- Workflow source files in `canonical/workflows/` define multi-step sequences in a platform-agnostic format
- Model tiers are defined in `canonical/model-tiers.yaml` and resolved to concrete model names per platform during assembly
- All template files that users must customize contain `<!-- CUSTOMIZE: ... -->` comment markers explaining what to fill in
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) — see `.github/instructions/commit-conventions.instructions.md`
- Keep canonical content generic and project-agnostic; platform-specific details belong in `canonical/platform-extras/`

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

Agents in this project follow a structured, phase-driven workflow: they read a JIRA ticket, plan and implement the change, self-review, and submit a Pull Request. All agent behaviour is defined in the platform-agnostic `canonical/` folder and assembled into platform-specific output by `scripts/assemble.py`.

### Agent Roster

Five agents are available. Each has a defined scope and model tier:

| Agent | Role | Model |
|-------|------|-------|
| **Orchestrator** | End-to-end workflow driver — reads the ticket, plans, implements, delegates, and submits the PR | Claude Sonnet 4 |
| **JIRA Reader** | Fetches a JIRA ticket and produces a structured requirements document | GPT-4o mini |
| **Reviewer** | Thorough code review — identifies risks, missing tests, and security issues | Claude Opus 4 |
| **Researcher** | Lightweight research — evaluates packages, APIs, and algorithms | Claude Haiku 3.5 |
| **PR Author** | Commits changes, pushes the branch, and finalises the draft PR | Claude Haiku 3.5 |

Agent definitions live in `canonical/agents/`. Each file is a plain Markdown file; the assembler adds platform-specific frontmatter (YAML for Copilot, CLAUDE.md entries for Claude Code) during generation.

### Skills

Skills are reusable, domain-specific instruction sets that agents load on demand. They live in `canonical/skills/<skill-name>/SKILL.md`.

| Skill | Purpose |
|-------|---------|
| `read-jira-ticket` | Fetch and parse a JIRA ticket into structured requirements |
| `git-operations` | Create branches, stage commits with conventional messages, and push |
| `create-pull-request` | Open a draft PR with the canonical PR body template |
| `update-pull-request` | Update mutable blocks and append to append-only blocks in an existing PR |
| `summarize-changes` | Produce a human-readable summary of a git diff, grouped by component |
| `identify-risks` | Analyse changes for breaking changes, security issues, and missing tests |

### Agent Prompts

User-facing entry points are defined in `canonical/prompts/`. The assembler renders them as `.prompt.md` slash commands for Copilot and equivalent entries for other platforms:

| Prompt | Slash command | What it does |
|--------|---------------|--------------|
| `feature.prompt.md` | `/feature` | Full feature workflow from JIRA ticket to PR, or resume from a PR link |
| `bugfix.prompt.md` | `/bugfix` | Bugfix workflow from JIRA ticket to PR, or resume |
| `review.prompt.md` | `/review` | Standalone code review of current changes |

### Workflows

Multi-phase workflow definitions live in `canonical/workflows/`. The Orchestrator reads the matching workflow file and executes it phase-by-phase:

| Workflow | Trigger | Phases |
|----------|---------|--------|
| `feature.md` | `/feature` | Bootstrap → Understand → Plan → Implement → Review → Submit |
| `bugfix.md` | `/bugfix` | Bootstrap → Understand → Diagnose → Fix → Review → Submit |
| `_resume.md` | Any PR link | Parses PR state and routes to the correct phase to continue |

All workflows include a **Phase 0: Bootstrap** that handles both fresh (JIRA input) and resume (PR link) modes automatically.

### Instructions

Persistent rules that apply across all agents are defined in `canonical/instructions/`:

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

`canonical/model-tiers.yaml` maps model tiers (0–3) to concrete model names per platform. The assembler resolves these during generation and stamps the correct model into each agent file. Tier assignment reflects cost/capability trade-offs:

- **Tier 0** — Cheapest (GPT-4o mini): simple, deterministic tasks like reading tickets
- **Tier 1** — Lightweight (Claude Haiku 3.5): formulaic tasks like committing and pushing
- **Tier 2** — Capable (Claude Sonnet): complex reasoning and implementation
- **Tier 3** — Most powerful (Claude Opus): thorough review and risk analysis
