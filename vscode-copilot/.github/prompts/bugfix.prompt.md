---
description: "Bugfix workflow — start fresh from a JIRA ticket, or resume an in-progress bugfix from a PR link. Reads the bug ticket (or PR state), reproduces the issue, identifies root cause, implements the fix with a regression test, and submits a Pull Request."
agent: "orchestrator"
argument-hint: "JIRA bug ticket URL/key (e.g., PROJ-456) or PR URL/number (e.g., #42) to resume"
---

# Bugfix Workflow

Fix a bug end-to-end, or resume a bugfix that was interrupted.

Follow the canonical workflow defined in `agent-workflows/bugfix.md`, starting from **Phase 0: Bootstrap**.

- If a **JIRA ticket** is provided: fresh start from Phase 1.
- If a **PR link or number** is provided: fetch the PR state document, determine the current phase, and resume from the next phase.
- If **neither** is provided: ask the user for a JIRA ticket key/URL or a PR link/number.
