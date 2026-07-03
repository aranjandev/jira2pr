# Scope-Creep Workflow

Inject additional work into an active feature or bugfix workflow.

Delegate to the **orchestrator** agent and invoke its `scope-creep` state machine.

- A **description of additional work** MUST be provided. If not, ask the user what work they want to add.
- This command can ONLY be invoked during an active feature or bugfix workflow (a branch, PR, and state file must already exist).
- If no active workflow is detected (no PR state, no state file), report this to the user and stop.
