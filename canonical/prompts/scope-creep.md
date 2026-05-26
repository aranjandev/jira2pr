# Scope-Creep Workflow

Inject additional work into an active feature or bugfix workflow.

Follow the canonical workflow defined in `agent-workflows/scope-creep.md`, starting from **Phase 1: Understand Current State**.

- A **description of additional work** MUST be provided. If not, ask the user what work they want to add.
- This command can ONLY be invoked during an active feature or bugfix workflow (a branch, PR, and state file must already exist).
- If no active workflow is detected (no PR state, no state file), report this to the user and stop.
