---
description: "Report the current status of a workflow without executing anything."
agent: "supervisor"
argument-hint: "JIRA ticket key (e.g., PROJ-123)"
---

# /status

Read `.jira2pr/state/<TICKET-KEY>.yaml` (read-only) and report `workflow`, `current_state`, `status`, `retry_counts`, and `history`. Do not invoke any worker or modify state.
