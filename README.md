# jira2pr

A collection of copy-ready AI agent setup templates that enable end-to-end automated development workflows — from reading a JIRA ticket to submitting a Pull Request.

Teams copy a setup folder into their project, customize the templates, and immediately gain AI agents that can plan, implement, review, and ship code with minimal human intervention.

## What Is In This Repo

- `vscode-copilot/`: VS Code + GitHub Copilot setup (reference implementation)
- `claude-code/`: Claude Code setup template
- `cursor/`: Cursor setup template

Each top-level folder is self-contained and customizable.

## How To Use

1. Pick the setup folder that matches your tool.
2. Copy that folder's configuration into your target project.
3. Update all `<!-- CUSTOMIZE: ... -->` sections with your project details.
4. Configure required credentials and environment variables (for example JIRA and GitHub CLI auth, if your workflow uses them).
5. Start using the prompts/agents in your tool.

## Key Features

### End-to-End Workflow
Agents chain together to cover the full development cycle:
1. **Read** — parse a JIRA ticket into structured requirements
2. **Plan** — break the ticket into tasks and produce a test strategy
3. **Implement** — write code and tests following project conventions
4. **Review** — self-review changes for risks and quality
5. **Submit** — commit, push, and open a Pull Request

### PR as Live State Document
Every workflow creates a **draft PR immediately after plan approval** and uses the PR body as a live state document throughout development. The PR body is divided into machine-writable sections (bounded by `PR_BLOCK:*:BEGIN/END` markers) that agents update at each phase transition:

- **Status** — current phase (`Planning` → `Implementing` → `Reviewing` → `Ready`), draft flag, last updated timestamp
- **Intent** — problem, desired outcome, non-goals, constraints (immutable after plan approval)
- **Plan** — task list with stable IDs, test strategy, risks and mitigations
- **Phase Log** — append-only audit trail of every phase transition
- **Review Summary** — findings and resolutions from self-review

This means the PR is always an accurate snapshot of where the work stands, not just a final artifact.

### Resume an Interrupted Session
Because the PR body captures full workflow state, agents can **resume from any interruption** without losing context. Pass a PR link or number to the Orchestrator agent and it will:
1. Fetch the PR body and parse the current phase from the Status block
2. Re-populate the task list from the Plan block
3. Append a "Resumed" entry to the Phase Log
4. Continue from the exact point where work stopped

This makes AI-driven development resilient to crashes, session timeouts, and manual interruptions — the PR is the single source of truth.

## Notes

- This repository is configuration-focused, not a runnable application.
- `vscode-copilot/.github/` is the canonical example structure for organizing agents, skills, prompts, workflows, and scripts.
