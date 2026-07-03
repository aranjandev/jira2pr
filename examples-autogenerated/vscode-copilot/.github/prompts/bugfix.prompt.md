---
description: "Bugfix workflow — start fresh from a JIRA ticket, or resume an in-progress bugfix from a PR link. Reads the bug ticket (or PR state), reproduces the issue, identifies root cause, implements the fix with a regression test, and submits a Pull Request."
agent: "orchestrator"
argument-hint: "JIRA bug ticket URL/key (e.g., PROJ-456) or PR URL/number (e.g., #42) to resume"
---
# Bugfix Workflow

Fix a bug end-to-end, or resume a bugfix that was interrupted.

Delegate to the **orchestrator** agent and invoke its `bugfix` state machine.

- If a **JIRA ticket** is provided: fresh start — orchestrator runs the bugfix state machine from Understand.
- If a **PR link or number** is provided: orchestrator invokes the `resume-workflow` skill, determines the current phase, and continues from there.
- If **neither** is provided: ask the user for a JIRA ticket key/URL or a PR link/number.
