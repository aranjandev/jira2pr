# Bugfix Workflow

Fix a bug end-to-end, or resume a bugfix that was interrupted.

Follow the canonical workflow defined in `agent-workflows/bugfix.md`, starting from **Phase 0: Bootstrap**.

- If a **JIRA ticket** is provided: fresh start from Phase 1.
- If a **PR link or number** is provided: fetch the PR state document, determine the current phase, and resume from the next phase.
- If **neither** is provided: ask the user for a JIRA ticket key/URL or a PR link/number.
