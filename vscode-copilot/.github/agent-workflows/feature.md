# Feature Workflow

Implement a feature end-to-end from a JIRA ticket to a submitted Pull Request, or resume an in-progress feature from an existing draft PR.

> **PR as live state document**: This workflow creates a draft PR after branch creation and updates it at each phase transition. The PR body follows the canonical schema from `instructions/pr-description.instructions.md`. The PR number is threaded through all phases.

## Phase 0: Bootstrap

Determine whether this is a fresh start or a resume, then route accordingly.

### 0a. Detect mode

- **FRESH** (input is a JIRA key/URL): proceed to **Phase 1: Understand**.
- **RESUME** (input is a PR URL/number): proceed to step 0b.

### 0b. Resume from PR

* **STEP-A: Fetch PR body:**
   ```bash
   python3 ./.github/skills/create-pull-request/scripts/pr_helper.py fetch-body \
     --pr-number <PR_NUMBER> > /tmp/pr_current_body.md
   ```
* **STEP-B: Validate boundary markers** — confirm all `PR_BLOCK:*:BEGIN/END` pairs exist. If any are missing, report "This PR does not use the canonical schema — cannot resume" and stop.
* **STEP-C: Parse PR state:**
   - Status block → extract current Phase
   - Links block → extract JIRA URL, Branch name
   - Plan block → extract task list, test strategy, risks
   - Phase Log → read audit trail
* **STEP-D: Store `PR_NUMBER`** for subsequent update calls.
* **STEP-E: Populate the `todo` tool** with tasks from the Plan block so progress tracking continues.
* **STEP-F: Append Phase Log** entry using `update-pull-request` skill: current timestamp, current phase (not a new one), `orchestrator`, "Resumed by orchestrator".
   - Idempotency: if the last Phase Log row already has this phase value and summary starts with "Resumed", do not append.
* **STEP-G: Route to the resume point:**

| Phase Found | Resume Point | Pre-resume Check |
|-------------|--------------|------------------|
| `Implementing` | **Phase 4: Implement** | Check `git diff --stat` and `git status` against Plan tasks to assess what is done vs. remaining. Report assessment to user before continuing. |
| `Reviewing` | **Phase 6: Submit** | Verify Review Summary block is populated |
| `Ready` | **STOP** | Report "PR #N is already finalized and marked Ready" |

> **`Implementing` is the most nuanced resume point.** The orchestrator must compare planned tasks against actual file changes to identify remaining work. Checkout the PR branch, run `git diff --stat` against the base, and cross-reference with the task list. Report what appears complete vs. outstanding before proceeding.

## Phase 1: Understand

* **STEP-1: Delegate to `jira-reader`**: Pass the JIRA ticket key/URL. Receive a structured requirements document.
* **STEP-2: Read project context**: Check `copilot-instructions.md` for coding standards, architecture, and build/test commands.
* **STEP-3: Explore the codebase**: Search for relevant files, understand the existing patterns and architecture.

## Phase 2: Plan & Propose

* **STEP-4: Assess if research is needed**:
   - After reading the ticket, identify if implementation requires:
     - External library/package evaluation (e.g., "use the best algorithm for X")
     - API or framework research (e.g., "integrate with OAuth provider")
     - Best practices lookup for unfamiliar domains
     - Comparison of approach options
   - If research is needed: Delegate to `Explore` agent with a query for package recommendations, algorithm comparisons, or API patterns. Return results into the plan phase.
   - If no research needed (e.g., "fix typo in error message"), skip to STEP-5.

* **STEP-5: Create a task list** (use the `todo` tool) breaking down the implementation:
   - List each file to create or modify
   - List each test to add
   - Order tasks by dependency
   - If research was done (STEP-4), incorporate findings and rationale (e.g., "Use library X because Y")

* **STEP-6: Format the plan** with these must-have items:
   - Summary of intended behavior after implementation
   - Tasks list from STEP-5
   - Test strategy, must include what tests will be added/modified and what user tests to run
   - Risks and mitigations (e.g., "This touches the auth flow, so I'll add extra tests and be careful to follow existing patterns")

* **STEP-7: Create a feature branch** using the git-operations skill:
   ```bash
   python3 ./.github/skills/git-operations/scripts/git_helper.py create-branch <TICKET_KEY> feat
   ```

* **STEP-8: Create draft PR** using the `create-pull-request` skill:
   - Populate the canonical PR body template with: Status (`Implementing`), Links (include Branch name), Intent, Plan, first Phase Log entry ("Branch created, draft PR created, entering implementation").
   - Create as `--draft`.
   - **Store the returned `PR_NUMBER`** — it is required for all subsequent updates.
   ```bash
   python3 ./.github/skills/create-pull-request/scripts/pr_helper.py create \
     --title "<type>(<scope>): <description> [<TICKET_KEY>]" \
     --body-file /tmp/pr_body.md \
     --draft --labels "<labels>"
   ```

* **STEP-9: Present the plan in PR** to the user:
   - Show the user the PR link for the proposed plan.
   - If the plan is complex (touches > 5 files), explicitly ask for confirmation and do not proceed until approval is received.
   - For simpler changes, present the plan PR and proceed immediately unless the user objects.

## Phase 3: Implement

* **STEP-10: Implement changes** file by file, following the plan:
    - Follow project conventions from `copilot-instructions.md`
    - Write clean, idiomatic code
    - Add/update tests alongside implementation
    - Mark each task as completed in the todo list
* **STEP-11: Run tests** after implementation:
    ```bash
    # Use the test command from copilot-instructions.md
    ```
* **STEP-12: Run linting** if configured:
    ```bash
    # Use the lint command from copilot-instructions.md
    ```
* **STEP-13: Update PR** using the `update-pull-request` skill:
    - No status change (still `Implementing`)
    - Append Phase Log: "Implementation complete, tests passing"

## Phase 4: Self-Review

* **STEP-14: Delegate to `reviewer`**: Ask the reviewer agent to analyze all changes.
* **STEP-15: Address findings**:
    - Fix any CRITICAL or HIGH findings immediately
    - Apply MEDIUM suggestions if they're quick wins
    - Note LOW/nit findings but don't block on them
* **STEP-16: Re-run tests** after addressing review feedback.
* **STEP-17: Update PR** using the `update-pull-request` skill:
    - Status → `Reviewing`
    - Populate Review Summary: risk level, findings, resolutions
    - Append Phase Log: "Self-review complete, findings addressed"

## Phase 5: Submit

* **STEP-18: Delegate to `pr-author`**: Pass the JIRA ticket key **and the PR number**. The pr-author will:
    - Commit and push changes
    - Use the `update-pull-request` skill to finalize: Status → `Ready`, Draft → `false`, sanitize sections, `--undraft`
    - Append Phase Log: "PR finalized and marked ready for review"
* **STEP-19: Report to the user**: Provide the PR URL and a brief summary of what was done.
