# jira2pr

Copy-ready AI agent setup templates for end-to-end automated development — from reading a JIRA ticket to submitting a Pull Request.

## Motivation

AI coding agents are powerful, but left unconstrained they drift: jumping straight to code without a plan, skipping tests, writing commit messages that say nothing, and handing off context-free PRs that no one can review. The usual result is faster movement in the wrong direction.

This project takes a different approach: encode the software engineering practices that senior developers already trust — structured planning, conventional commits, self-review before submission, and explicit handoff artifacts — into reusable agent templates. Agents are not given open-ended freedom; they follow a defined workflow with checkpoints, produce artifacts other agents (and humans) can read, and leave a written record of every decision.

The concrete goals are:

- **Enforce process, not just speed.** A ticket flows through Read → Plan → Implement → Review → Submit. No phase is skipped. Senior developers approve the plan before any code is written.
- **Make agent work reviewable.** Every PR is a live state document. The plan, task list, risk assessment, phase transitions, and scope changes are all recorded in the PR body in a machine-readable schema. Humans can inspect, override, or resume at any point.
- **Enable collaboration between humans and agents.** Agents write to well-defined sections; humans retain ownership of approval gates. The shared PR body is the coordination surface — not Slack messages or tribal knowledge.
- **Reduce context loss from interruptions.** Sessions crash. Agents time out. Because the PR body is the single source of truth, any agent (or human) can resume from exactly where work stopped without losing history.

## Available Setups

| Folder | Tool | Status |
|--------|------|--------|
| [`vscode-copilot/`](vscode-copilot/README.md) | VS Code + GitHub Copilot | Reference implementation |
| [`claude-code/`](claude-code/) | Claude Code | Template (in progress) |
| [`cursor/`](cursor/) | Cursor | Template (in progress) |

Each folder is self-contained and customizable.

## How To Use

1. Pick the setup folder for your tool from the table above.
2. Follow the setup instructions in that folder's README — it covers copying files, setting environment variables, and customizing project-specific instructions.
3. Start using the slash commands or agents in your tool.

All `<!-- CUSTOMIZE: ... -->` markers in the copied files flag the sections you must fill in for your project.

## Key Features

### End-to-End Workflow
Agents chain together to cover the full development cycle:

1. **Read** — parse a JIRA ticket into structured requirements  
2. **Plan** — break the ticket into tasks, produce a test strategy, await approval  
3. **Implement** — write code and tests following project conventions  
4. **Review** — self-review changes for risks, security, and quality  
5. **Submit** — commit with conventional messages, push, and open a Pull Request

Each phase is handled by a purpose-built agent assigned the right model tier for the task (lightweight models for extraction, stronger models for planning and review). See the setup README for the full agent roster and tier assignments.

### PR as Live State Document
A draft PR is created at the end of planning — before any code is written. The PR body is divided into machine-writable sections bounded by `<!-- PR_BLOCK:*:BEGIN/END -->` markers that agents update at each phase transition:

| Block | Mutability | Purpose |
|-------|------------|---------|
| Status | Mutable | Current phase, draft flag, last-updated timestamp |
| Links | Mutable | JIRA ticket URL, branch name |
| Intent | Immutable | Problem, desired outcome, non-goals, constraints |
| Plan | Mutable | Task list (stable IDs T1, T2, …), test strategy, risks |
| Phase Log | Append-only | Audit trail of every phase transition |
| Review Summary | Mutable | Risk level, findings, resolutions from self-review |
| Decisions Log | Append-only | Scope changes, plan mutations, review overrides |
| Open Questions | Mutable | Unresolved items and deferred work |
| Agent Notes | Mutable | Breadcrumbs for downstream agents or human reviewers |

The PR is always an accurate snapshot of where work stands — not just a final artifact.

### Resume an Interrupted Session
Because the PR body captures full workflow state, any agent can resume from any interruption. Pass a PR link or number to the Orchestrator instead of a JIRA key and it will:

1. Fetch the PR body and validate all block markers
2. Parse current phase, branch name, and task list
3. Append a resume entry to the Phase Log (idempotent — no duplicate entries)
4. Route to the correct workflow step and continue

No work is lost regardless of how the session ended.

### Model Tiers
Agents are assigned model tiers based on task complexity, balancing cost against capability:

| Tier | Default Model | Used By |
|------|--------------|---------|
| 0 | GPT-4o mini | JIRA Reader |
| 1 | Claude Haiku 3.5 | Researcher, PR Author |
| 2 | Claude Sonnet 4 | Orchestrator |
| 3 | Claude Opus 4 | Reviewer |

Tiers are defined in `model-tiers.json`. Run `apply_model_tiers.py` to propagate changes to all agent files.

## Notes

- This repository is configuration only — no build step, no runtime dependencies.
- `vscode-copilot/.github/` is the canonical structure for agents, skills, prompts, workflows, and scripts.
