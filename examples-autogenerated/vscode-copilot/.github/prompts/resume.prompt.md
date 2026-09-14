---
description: "Resume an in-progress workflow from its persisted state file."
agent: "supervisor"
argument-hint: "JIRA ticket key (e.g., PROJ-123)"
---

# /resume

Load `.jira2pr/state/<TICKET-KEY>.yaml`, determine `workflow` and `current_state`, and continue executing from there. Supported workflows: `feature`.
