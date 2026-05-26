# Bugfix Workflow

Fix a bug end-to-end from a JIRA ticket to a submitted Pull Request, or resume an in-progress bugfix from an existing draft PR.

> **PR as live state document**: This workflow creates a draft PR after branch creation and updates it at each phase transition. The PR body follows the schema in `instructions/pr-schema.instructions.md` and the template in `instructions/pr-template.instructions.md`. The PR number is threaded through all phases.

> ⚠️ **Two-layer state invariant:** At EVERY phase transition, you MUST update BOTH the PR body (via `update-pull-request`) AND the state file (via `manage-state`). Updating one without the other leaves the workflow in an unresumable state. These are equal-priority operations — neither is optional.

## Phase 0: Bootstrap

Determine whether this is a fresh start or a resume, then route accordingly.

### 0a. Detect mode

- **FRESH** (input is a JIRA key/URL): proceed to **Phase 1: Understand**.
- **RESUME** (input is a PR URL/number): proceed to step 0b.

### 0b. Resume from PR

Follow **Steps A–F** from [`_resume.md`](_resume.md) to fetch, validate, and restore PR state.

Then use this routing table for **Step G**:

| Phase Found | Resume Point | Pre-resume Check |
|-------------|--------------|------------------|
| `Implementing` | **STEP-4.1** | Check `git diff --stat` and `git status` to assess regression test + fix progress. Report assessment to user. |
| `Submitting` | **STEP-6.1** | Verify Review Summary block is populated |
| `Ready` | **STOP** | Report "PR #N is already finalized and marked Ready" |

## Phase 1: Understand

* **STEP-1.1: Delegate to `jira-reader`**: Pass the JIRA ticket key/URL. Receive a structured bug report with reproduction steps, expected vs. actual behavior, and affected components.
* **STEP-1.2: Read project context**: Check `{{PROJECT_INSTRUCTIONS_FILE}}` for coding standards, architecture, and build/test commands.
* **STEP-1.3: Explore the codebase**: Locate the relevant code paths based on the bug report.

## Phase 2: Reproduce & Diagnose

* **STEP-2.1: Attempt to reproduce the bug**:
   - Run relevant existing tests to see if any already fail
   - Trace the code path described in the reproduction steps
   - If the bug cannot be reproduced, report this to the user before proceeding

* **STEP-2.2: Identify root cause**:
   - Analyze the code paths involved
   - Determine why the bug occurs (off-by-one, missing null check, race condition, wrong logic, etc.)
   - Document the root cause clearly — this will go into the PR description

## Phase 3: Plan & Propose

* **STEP-3.1: Delegate to `planner-lite` agent** to produce a fix plan:
   - Pass the root cause from STEP-2.2, affected code paths from STEP-1.3, and project conventions
   - The plan must include:
     - The regression test (a test that fails before the fix and passes after)
     - The minimal, targeted code change that addresses the root cause
     - Ordered task list: regression test first, then fix
   - Receive back a validated plan containing: Summary, File Changes, ordered Task List, Tests, and Constraints
   - For complex fixes (touches > 3 files or risky areas like auth/payments), present the plan to the user and wait for confirmation
   - For simple fixes, present and proceed immediately

* **STEP-3.2: Create a bugfix branch** using the `git-operations` skill with ticket key `<TICKET_KEY>` and type `fix`.

* **STEP-3.3: Create draft PR** using the `create-pull-request` skill:
   - Populate the canonical PR body template with: Status (`Implementing`), Links (include Branch name), Intent (include root cause in Problem), Plan, first Phase Log entry ("Branch created, draft PR created, entering implementation").
   - **Store the returned `PR_NUMBER`** — it is required for all subsequent updates.

* **STEP-3.3b: Create state file** using the `manage-state` skill:
   - Workflow type: `bugfix`
   - Phase: `Implementing`
   - Populate UNDERSTANDING from Phases 1–2 (bug description, root cause, constraints), PLAN from STEP-3.1
   - Commit with message: `chore(state): initialize workflow state [<TICKET_KEY>]`

## Phase 4: Implement

* **STEP-4.1: Delegate to `coder` agent** for implementation:
    - Pass the complete plan from STEP-3.1 (planner-lite output) as the execution spec
    - Pass project conventions from `{{PROJECT_INSTRUCTIONS_FILE}}`
    - Pass relevant file context identified in the plan
    - The `coder` will implement ALL changes: regression test AND fix code
    - The regression test must be written first (as specified in the plan's task order)
    - The `coder` will run tests and lint, and self-fix failures (up to 2 retries)
    - Do NOT implement any code yourself — all implementation is delegated to `coder`

* **STEP-4.2: Verify completion** after `coder` returns:
    - Check the completion report: confirm tests pass and lint is clean
    - If `coder` reports failure after retries → report to user and stop
    - Confirm the regression test was added
    - Confirm the fix addresses the root cause identified in STEP-2.2
    - Confirm no unrelated changes were introduced

* **STEP-4.3: Update PR** using the `update-pull-request` skill:
    - No status change (still `Implementing`)
    - Append Phase Log: "Fix applied, regression test passing"

* **STEP-4.4: Update state file** using the `manage-state` skill:
    - IMPLEMENTATION block: list all files created/modified (with brief note on each), tests added, any plan deviations
    - PLAN block: mark completed tasks as `done`
    - PHASE_LOG: append entry matching STEP-4.3 ("Fix applied, regression test passing")
    - ⚠️ **MANDATORY** — skipping this breaks workflow resumption

    > Checkpoint: ☐ PR body updated (STEP-4.3)  ☐ State file updated (STEP-4.4)  ☐ Both committed

## Phase 5: Self-Review

* **STEP-5.1: Delegate to `reviewer`**: Ask the reviewer agent to analyze all changes.
* **STEP-5.2: Address findings** by delegating to `coder`:
    - Pass CRITICAL and HIGH findings to `coder` for immediate fix
    - Pass MEDIUM suggestions to `coder` if they're quick wins
    - Note LOW/nit findings but don't block on them
    - Do NOT fix code yourself — delegate all code changes to `coder`
    - `coder` will run tests after fixes and self-verify
* **STEP-5.3: Verify** `coder` completion report confirms tests pass.
* **STEP-5.4: Update PR** using the `update-pull-request` skill:
    - Status → `Submitting`
    - Populate Review Summary: risk level, findings, resolutions
    - Append Phase Log: "Self-review complete, findings addressed"

* **STEP-5.5: Update state file** using the `manage-state` skill:
    - Phase → `Submitting`
    - REVIEW block: populate risk level, each finding (severity + description + resolution), overall verdict
    - IMPLEMENTATION block: update with any files modified during review fixes
    - PHASE_LOG: append entry matching STEP-5.4 ("Self-review complete, findings addressed")
    - ⚠️ **MANDATORY** — skipping this breaks workflow resumption

    > Checkpoint: ☐ PR body updated (STEP-5.4)  ☐ State file updated (STEP-5.5)  ☐ Both committed

## Phase 6: Submit

* **STEP-6.1: Delegate to `pr-author`**: Pass the JIRA ticket key **and the PR number**. The pr-author must:
    - Commit and push changes
    - Finalize the PR via `update-pull-request` skill: Status → `Ready`, undraft
    - Register the artifact via `register-artifact` skill
    - Archive the state file via `manage-state` skill
    - Include registry update and state archive in the final commit
* **STEP-6.2: Report to the user**: Provide the PR URL and a brief summary including the root cause and the fix.
