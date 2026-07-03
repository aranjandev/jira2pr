# Feature Workflow

Implement a feature end-to-end, or resume one that was interrupted.

Delegate to the **orchestrator** agent and invoke its `feature` state machine.

- If a **JIRA ticket** is provided: fresh start — orchestrator runs the feature state machine from Understand.
- If a **PR link or number** is provided: orchestrator invokes the `resume-workflow` skill, determines the current phase, and continues from there.
- If **neither** is provided: ask the user for a JIRA ticket key/URL or a PR link/number.
