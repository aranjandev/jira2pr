---
description: "Full feature workflow — start fresh from a JIRA ticket, or resume an in-progress feature from a PR link. Reads the ticket (or PR state), plans implementation, writes code, self-reviews, and submits a Pull Request."
agent: "orchestrator"
argument-hint: "JIRA ticket URL/key (e.g., PROJ-123) or PR URL/number (e.g., #42) to resume"
---

# Feature Workflow

Implement a feature end-to-end, or resume one that was interrupted.

Follow the canonical workflow defined in `agent-workflows/feature.md`, starting from **Phase 0: Bootstrap**.

- If a **JIRA ticket** is provided: fresh start from Phase 1.
- If a **PR link or number** is provided: fetch the PR state document, determine the current phase, and resume from the next phase.
- If **neither** is provided: ask the user for a JIRA ticket key/URL or a PR link/number.
