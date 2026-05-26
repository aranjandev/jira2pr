# Feature Workflow

Implement a feature end-to-end from a JIRA ticket to a submitted Pull Request, or resume an in-progress feature from an existing draft PR. The workflow as the following phases:

## Phase 0: Bootstrap

Determine whether this is a fresh start or a resume, then route accordingly.

### 0a. Detect mode

* If mode is **FRESH**: proceed to **Phase 1: Understand**.
* If mode is **RESUME**: proceed to **0b: Resume from PR**. 

### 0b. Resume from PR

Follow **Steps A–F** from [`_resume.md`](_resume.md) to fetch, validate, and restore PR state.

Then use this routing table for **Step G**:

| Current Phase | Resume Step | Pre-resume Check |
|---------------|-------------|------------------|
| `Implementing`| **STEP-2.7** | Verify all the outputs of Steps A–F are present |
| `Reviewing`   | **STEP-4.1** | Verify based on Phase Logs "Implementation complete, tests passing" |
| `Submitting`  | **STEP-5.1** | Verify Review Summary block is populated |
| `Ready`       | **STOP**     | Report "PR #N is already finalized and marked Ready" |

---

> ⚠️ **Two-layer state invariant:** At EVERY phase transition, you MUST update BOTH the PR body (via `update-pull-request`) AND the state file (via `manage-state`). Updating one without the other leaves the workflow in an unresumable state. These are equal-priority operations — neither is optional.

---

## Phase 1: Understanding

* **STEP-1.1: Delegate to `jira-reader` agent**: Pass the JIRA ticket key/URL. Receive a structured requirements document.
* **STEP-1.2: Read project context**: Check `{{PROJECT_INSTRUCTIONS_FILE}}` for coding standards, architecture, and build/test commands.
* **STEP-1.3: Explore the codebase**: Search for relevant files, understand the existing patterns and architecture.

## Phase 2: Planning

* **STEP-2.1: Assess if research is needed**:
   - After reading the ticket, identify if implementation requires:
     - External library/package evaluation (e.g., "use the best algorithm for X")
     - API or framework research (e.g., "integrate with OAuth provider")
     - Best practices lookup for unfamiliar domains
     - Comparison of approach options
   - Based on above, decide if research is needed 
   - If research needed: then go to STEP-2.2, else go to STEP-2.3

*  **STEP-2.2: Research: Delegate to `researcher` agent:** 
   - Pass a query for package recommendations, algorithm comparisons, or API patterns. 
   - Pass the research results to next steps.

* **STEP-2.3: Delegate to `planner-lite` agent** to produce a file-level implementation plan:
   - Pass the structured requirements from STEP-1.1, project conventions from STEP-1.2, codebase context from STEP-1.3, and research output from STEP-2.2 (if any)
   - Receive back a validated plan containing: Summary, File Changes, ordered Task List, Tests, and Constraints
   - The plan is the **single source of truth** for implementation — no implementation detail is left ambiguous

* **STEP-2.4: Review the plan** output from `planner-lite`:
   - Verify it covers all requirements from the JIRA ticket
   - Verify test strategy includes success and edge/failure cases
   - If the plan is incomplete or misses requirements, re-invoke `planner-lite` with clarifying context
   - Use the {{TASK_TRACKING_INSTRUCTION}} to track the task list from the plan

* **STEP-2.5: Create a feature branch** using the `git-operations` skill with ticket key `<TICKET_KEY>` and type `feat`.

* **STEP-2.6: Create draft PR** using the `create-pull-request` skill:
   - Populate the canonical PR body template with: 
      * Status → `Implementing` 
      * Populate all fields: Links, Intent, Plan 
      * First Phase Log entry → "Branch created, draft PR created with plan, entering implementation"
   - **Store the returned `PR_NUMBER`** — it is required for all subsequent updates.

* **STEP-2.6b: Create state file** using the `manage-state` skill:
   - Workflow type: `feature`
   - Phase: `Implementing`
   - Populate UNDERSTANDING from Phase 1 output, RESEARCH from STEP-2.2 (if run), PLAN from STEP-2.3/2.4
   - Commit with message: `chore(state): initialize workflow state [<TICKET_KEY>]`

* **STEP-2.7: Present the plan in PR** to the user:
   - Show the user the PR link for the proposed plan.
   - If one of the following conditions are met, then ask for approval and do not proceed until approved:
      - If the plan is complex (touches > 5 files), or
      - If the JIRA ticket has "Plan approval required" set to Yes/True. 
   - For simpler changes, present the plan PR and proceed immediately.

## Phase 3: Implementing

* **STEP-3.1: Delegate to `coder` agent** for implementation:
    - Pass the complete plan from STEP-2.3 (planner-lite output) as the execution spec
    - Pass project conventions from `{{PROJECT_INSTRUCTIONS_FILE}}`
    - Pass relevant file context identified in the plan
    - The `coder` will implement ALL code changes and tests specified in the plan
    - The `coder` will run tests and lint, and self-fix failures (up to 2 retries)
    - Do NOT implement any code yourself — all implementation is delegated to `coder`

* **STEP-3.2: Verify completion** after `coder` returns:
    - Check the completion report: confirm tests pass and lint is clean
    - If `coder` reports failure after retries → report to user and stop
    - Confirm all files from the plan were created/modified
    - {{TASK_COMPLETION_INSTRUCTION}}

* **STEP-3.3: Update PR** using the `update-pull-request` skill:
    - Status → `Reviewing`
    - Append Phase Log: "Implementation complete, tests passing"

* **STEP-3.4: Update state file** using the `manage-state` skill:
    - Phase → `Reviewing`
    - IMPLEMENTATION block: list all files created/modified (with brief note on each), tests added, any plan deviations
    - PLAN block: mark all completed tasks as `done`
    - PHASE_LOG: append entry matching STEP-3.3 ("Implementation complete, tests passing")
    - ⚠️ **MANDATORY** — skipping this breaks workflow resumption

    > Checkpoint: ☐ PR body updated (STEP-3.3)  ☐ State file updated (STEP-3.4)  ☐ Both committed

## Phase 4: Reviewing

* **STEP-4.1: Delegate to `reviewer` agent**: 
   - Ask the reviewer agent to analyze all changes.

* **STEP-4.2: Address findings** by delegating to `coder`:
    - Pass CRITICAL and HIGH findings to `coder` for immediate fix
    - Pass MEDIUM suggestions to `coder` if they're quick wins
    - Note LOW/nit findings but don't block on them
    - Do NOT fix code yourself — delegate all code changes to `coder`
    - `coder` will run tests after fixes and self-verify

* **STEP-4.3: Verify** `coder` completion report confirms tests pass.

* **STEP-4.4: Update PR** using the `update-pull-request` skill:
    - Status → `Submitting`
    - Populate Review Summary: risk level, findings, resolutions
    - Append Phase Log: "Self-review complete, findings addressed"

* **STEP-4.5: Update state file** using the `manage-state` skill:
    - Phase → `Submitting`
    - REVIEW block: populate risk level, each finding (severity + description + resolution), overall verdict
    - IMPLEMENTATION block: update with any files modified during review fixes
    - PHASE_LOG: append entry matching STEP-4.4 ("Self-review complete, findings addressed")
    - ⚠️ **MANDATORY** — skipping this breaks workflow resumption

    > Checkpoint: ☐ PR body updated (STEP-4.4)  ☐ State file updated (STEP-4.5)  ☐ Both committed

## Phase 5: Submitting

* **STEP-5.1: Delegate to `pr-author` agent**: 
    - Pass the JIRA ticket key **and the PR number**. 
    - PR author must:
      - Finalize the PR via `update-pull-request` skill: Status → `Ready`, undraft
      - Register the artifact via `register-artifact` skill
      - Archive the state file via `manage-state` skill
      - Include registry update and state archive in the final commit

* **STEP-5.2: Report to the user**: Provide the PR URL and a brief summary of what was done.
