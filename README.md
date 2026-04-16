# AI Coder Helpers

This repository is a collection of copy-ready AI agent setup templates for different tools and IDEs.

Its goal is to help teams bootstrap an end-to-end agent workflow quickly, from reading a JIRA ticket to preparing code changes and opening a pull request.

## What Is In This Repo

- `vscode-copilot/`: VS Code + GitHub Copilot setup (reference implementation)
- `claude-code/`: Claude Code setup template
- `cursor/`: Cursor setup template

Each top-level folder is intended to be self-contained and customizable.

## How To Use

1. Pick the setup folder that matches your tool.
2. Copy that folder's configuration into your target project.
3. Update all `<!-- CUSTOMIZE: ... -->` sections with your project details.
4. Configure required credentials and environment variables (for example JIRA and GitHub CLI auth, if your workflow uses them).
5. Start using the prompts/agents in your tool.

## Notes

- This repository is configuration-focused, not a runnable application.
- `vscode-copilot/.github/` is the canonical example structure for organizing agents, skills, prompts, workflows, and scripts.
