---
description: "Bugfix workflow from a JIRA ticket to a submitted PR. Reads the bug ticket, reproduces the issue, identifies root cause, implements the fix with a regression test, and creates a Pull Request."
agent: "orchestrator"
argument-hint: "JIRA bug ticket URL or key (e.g., PROJ-456)"
---

# Bugfix Workflow

Fix a bug end-to-end from a JIRA ticket.

Follow the canonical workflow defined in `workflows/bugfix.md`.

Begin by asking for the JIRA ticket if not provided in the prompt.
