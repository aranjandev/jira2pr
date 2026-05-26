# Scope-Creep Workflow

Inject additional work into an active feature or bugfix workflow. This workflow is invoked mid-execution via `/scope-creep <description>` and operates within the context of an existing branch, PR, and state file.

> **Context:** This workflow never runs standalone. It is always invoked while a feature or bugfix workflow is already in progress. The PR, branch, and state file already exist.

## Prerequisites

Before this workflow begins, the following MUST already be present:
- An active feature or bugfix workflow (branch exists, PR exists, state file exists)
- The PR number and ticket key are known (from the active workflow's state)
- The user has provided a plain-text description of the additional work

## Phase 1: Understand Current State

* **STEP-1.1: Read the state file** using the `manage-state` skill:
   - Load `.github/state/<TICKET-KEY>.md`
   - Extract current PLAN block (task table with statuses)
   - Extract UNDERSTANDING block (requirements, constraints)
   - Identify current phase of the outer workflow

* **STEP-1.2: Read the PR body** to confirm task list and current progress:
   - Fetch PR body using `pr_helper.py fetch-body --pr-number <PR_NUMBER>`
   - Parse the Plan block for the current task list
   - Parse Phase Log for context on what's been done

* **STEP-1.3: Formulate the scope-creep as requirements**:
   - Treat the user's `/scope-creep <description>` input as a mini requirements document
   - Identify what new functionality or fix is being requested
   - Determine how it relates to (or extends) the existing plan

## Phase 2: Plan the Delta

* **STEP-2.1: Delegate to `planner-lite` agent** to produce a delta plan:
   - Pass the user's scope-creep description as the requirement
   - Pass the existing plan from STEP-1.1 (so planner can build on top of it)
   - Pass project conventions from `copilot-instructions.md`
   - Pass relevant codebase context
   - Instruct planner to produce ONLY the additional tasks (delta), not repeat existing tasks
   - The delta plan must include: new task IDs (continuing from existing sequence), file changes, and test updates if needed

* **STEP-2.2: Merge the delta into the existing plan**:
   - Assign new task IDs continuing the existing sequence (e.g., if last task is T5, new tasks start at T6)
   - Validate the delta tasks don't conflict with existing tasks
   - Update the use the `todo` tool to plan the tasks with the new tasks

* **STEP-2.3: Update PR with expanded scope** using the `update-pull-request` skill:
   - Append new tasks to the Plan block (do NOT rewrite existing tasks)
   - Append a Decisions Log entry documenting the scope expansion:
     - Decision: "Scope expanded via /scope-creep"
     - Rationale: the user's description
     - Impact: list of new tasks added
     - Triggered By: "user /scope-creep invocation"
   - Append Phase Log entry: "Scope expanded: <brief summary of what was added>"

* **STEP-2.4: Update state file** using the `manage-state` skill:
   - Add new tasks to the PLAN block task table (status: `pending`)
   - Update UNDERSTANDING block if the scope-creep changes constraints or requirements
   - Append PHASE_LOG entry matching the PR Phase Log

## Phase 3: Implement the Delta

* **STEP-3.1: Delegate to `coder` agent** for implementation of the delta tasks ONLY:
   - Pass the delta plan from STEP-2.1 (only the new tasks)
   - Pass project conventions from `copilot-instructions.md`
   - Pass relevant file context
   - The `coder` implements ONLY the new delta tasks — existing code is not re-implemented
   - The `coder` runs tests and lint, self-fixes failures (up to 2 retries)

* **STEP-3.2: Verify completion** after `coder` returns:
   - Check completion report: tests pass, lint clean
   - If `coder` reports failure after retries → report to user and stop
   - Confirm all files from the delta plan were created/modified
   - Mark each task as completed in the todo list immediately after finishing it

## Phase 4: Update State

* **STEP-4.1: Update PR** using the `update-pull-request` skill:
   - Mark new tasks as complete in the Plan block
   - Append Phase Log entry: "Scope-creep implementation complete, tests passing"

* **STEP-4.2: Update state file** using the `manage-state` skill:
   - Mark new tasks as `done` in the PLAN block
   - Update IMPLEMENTATION block with files modified and tests added
   - Append PHASE_LOG entry: "Scope-creep implementation complete"

* **STEP-4.3: Resume outer workflow**: Return control to the outer workflow at the point where `/scope-creep` was invoked. The outer workflow continues from its current step.
