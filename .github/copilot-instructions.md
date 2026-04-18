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
  - `vscode-copilot/.github/` contains `agents/`, `skills/`, `prompts/`, `workflows/`, `instructions/`, `scripts/`, `model-tiers.json`, and `copilot-instructions.md`
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
