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

## Phase 1: Understanding

* **STEP-1.1: Delegate to `jira-reader` agent**: Pass the JIRA ticket key/URL. Receive a structured requirements document.
* **STEP-1.2: Read project context**: Check `copilot-instructions.md` for coding standards, architecture, and build/test commands.
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

*  **STEP-2.2: Research**: 
   - Delegate to `researcher` agent with a query for package recommendations, algorithm comparisons, or API patterns. 
   - Pass results to next steps.

* **STEP-2.3: Create a task list** (use the `todo` tool to plan the tasks) breaking down the implementation:
   - List each file to create or modify
   - List each test to add
   - Order tasks by dependency
   - If research was done (STEP-2.2), incorporate findings and rationale (e.g., "Use library X because Y")

* **STEP-2.4: Format the plan** with these must-have items:
   - Summary of intended behavior after implementation
   - Tasks list from STEP-2.3
   - Test strategy, must include what tests will be added/modified and what user tests to run
   - Risks and mitigations (e.g., "This touches the auth flow, so I'll add extra tests and be careful to follow existing patterns")

* **STEP-2.5: Create a feature branch** using the git-operations skill:
   ```bash
   python3 ./.github/skills/git-operations/scripts/git_helper.py create-branch <TICKET_KEY> feat
   ```

* **STEP-2.6: Create draft PR** using the `create-pull-request` skill:
   - Populate the canonical PR body template with: 
      * Status → `Implementing` 
      * Populate all fields: Links, Intent, Plan 
      * First Phase Log entry → "Branch created, draft PR created with plan, entering implementation"
   - Create as `--draft`.
   - **Store the returned `PR_NUMBER`** — it is required for all subsequent updates.
   ```bash
   python3 ./.github/skills/create-pull-request/scripts/pr_helper.py create \
     --title "<type>(<scope>): <description> [<TICKET_KEY>]" \
     --body-file /tmp/pr_body.md \
     --draft --labels "<labels>"
   ```

* **STEP-2.6b: Create state file** using the `manage-state` skill:
   - Copy `.github/state/workflow-state.tpl.md` to `.github/state/<TICKET_KEY>.md`
   - Populate META block: workflow type (`feature`), ticket key, ticket URL, branch, PR number, PR URL, timestamps
   - Set PHASE to `Implementing`
   - Populate UNDERSTANDING with requirements and constraints from Phase 1
   - Populate RESEARCH block with researcher output (if STEP-2.2 was run; leave empty otherwise)
   - Populate PLAN block: task table (all tasks with `Status=pending`), test strategy, risks
   - Populate first PHASE_LOG row: same timestamp and summary as the PR body Phase Log entry
   - Commit the state file:
     ```bash
     python3 ./.github/skills/git-operations/scripts/git_helper.py commit "chore(state): initialize workflow state [<TICKET_KEY>]"
     ```

* **STEP-2.7: Present the plan in PR** to the user:
   - Show the user the PR link for the proposed plan.
   - If one of the following conditions are met, then ask for approval and do not proceed until approved:
      - If the plan is complex (touches > 5 files), or
      - If the JIRA ticket has "Plan approval required" set to Yes/True. 
   - For simpler changes, present the plan PR and proceed immediately.

## Phase 3: Implementing

* **STEP-3.1: Implement changes** file by file, following the plan:
    - Follow project conventions from `copilot-instructions.md`
    - Write clean, idiomatic code
    - Add/update tests alongside implementation
    - Mark each task as completed in the todo list immediately after finishing it
    - After completing each task, update the state file PLAN block task status (`pending` → `in-progress` → `done`) and IMPLEMENTATION block using the `manage-state` skill

* **STEP-3.2: Run tests** after implementation:
    ```bash
    # Use the test command from copilot-instructions.md
    ```
* **STEP-3.3: Run linting** if configured:
    ```bash
    # Use the lint command from copilot-instructions.md
    ```
* **STEP-3.4: Update PR** using the `update-pull-request` skill:
    - Status → `Reviewing`
    - Append Phase Log: "Implementation complete, tests passing"
    - Also update state file: set PHASE to `Reviewing`, append Phase Log row (same content)

## Phase 4: Reviewing

* **STEP-4.1: Delegate to `reviewer` agent**: 
   - Ask the reviewer agent to analyze all changes.

* **STEP-4.2: Address findings**:
    - Fix any CRITICAL or HIGH findings immediately
    - Apply MEDIUM suggestions if they're quick wins
    - Note LOW/nit findings but don't block on them

* **STEP-4.3: Re-run tests** after addressing review feedback.

* **STEP-4.4: Update PR** using the `update-pull-request` skill:
    - Status → `Submitting`
    - Populate Review Summary: risk level, findings, resolutions
    - Append Phase Log: "Self-review complete, findings addressed"

## Phase 5: Submitting

* **STEP-5.1: Delegate to `pr-author` agent**: 
    - Pass the JIRA ticket key **and the PR number**. 
    - Aside from the assigned tasks, PR author must submit PR with these specs:
      - Use the `update-pull-request` skill to finalize: Status → `Ready`, Draft → `false` (`--undraft`)
      - Append Phase Log: "PR finalized and marked ready for review"
      - Register the artifact using the `register-artifact` skill: append one row to `.github/artifacts/REGISTRY.md` with ticket, PR number, branch, URL, actor (`pr-author`), risk level from Review Summary, and a one-sentence summary
      - Archive the state file: `git mv .github/state/<TICKET_KEY>.md .github/state/archive/<TICKET_KEY>.md`
      - Include registry update and state archive in the final commit

* **STEP-5.2: Report to the user**: Provide the PR URL and a brief summary of what was done.
