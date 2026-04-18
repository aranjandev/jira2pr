# jira2pr Templates

This repository provides copy-ready AI agent setup templates for multiple IDE and agent ecosystems.

The templates are designed for one end-to-end flow: start from a JIRA ticket, implement the work, and submit a Pull Request with a machine-maintained state document so interrupted sessions can resume safely.

## Repository Layout

- `vscode-copilot/`: VS Code + GitHub Copilot reference template (fully populated)
- `claude-code/`: Placeholder for a Claude Code variant
- `cursor/`: Placeholder for a Cursor variant

Each top-level folder is intended to be self-contained so teams can copy one folder into a project and customize it in place.

## What Is New In This Version

- The repository and docs now center on the jira2pr workflow.
- Pull Requests are treated as a live state document, not only a review artifact.
- Agents can resume from an existing PR by reading canonical `PR_BLOCK:*` sections and continuing from the recorded phase.

## How Resume Works

1. Start with `/feature <JIRA-KEY>` to run a fresh workflow.
2. The orchestrator creates a draft PR with structured sections (Status, Links, Intent, Plan, Phase Log), then populates review sections later in the flow.
3. At each phase transition, the agent updates only approved mutable blocks and appends log entries.
4. If a session is interrupted, run `/feature <PR-URL-or-number>`.
5. The orchestrator reads the PR state document, detects the latest phase, and resumes from the next step.

This makes progress durable even when terminals, editor sessions, or agent runs are interrupted.

## Quick Start

1. Choose your setup folder.
2. Copy its configuration into your target repository.
3. Fill all `<!-- CUSTOMIZE: ... -->` markers.
4. Configure credentials and environment variables (for example JIRA and GitHub auth).
5. Run the workflow prompts in your tool.

## Current Canonical Template

`vscode-copilot/.github/` is the canonical, fully implemented example of the workflow structure:

- `agents/` for orchestrator/specialist agent definitions
- `skills/` for reusable operational skills (JIRA, git, PR updates, review)
- `prompts/` for user entrypoints like `/feature`, `/bugfix`, `/review`
- `workflows/` for phase-by-phase orchestration logic
- `instructions/` for coding and process conventions
- `scripts/` for setup utilities such as model-tier application helpers

## Notes

- This repository is configuration-focused; it is not a runnable application.
- Validation is lightweight (shell syntax checks and JSON validation).
