# Bugfix Workflow

Fix a bug end-to-end from a JIRA ticket to a submitted Pull Request, or resume an in-progress bugfix from an existing draft PR.

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
   - Plan block → extract task list (including root cause from Intent), test strategy, risks
   - Phase Log → read audit trail
* **STEP-D: Store `PR_NUMBER`** for subsequent update calls.
* **STEP-E: Populate the `todo` tool** with tasks from the Plan block so progress tracking continues.
* **STEP-F: Append Phase Log** entry using `update-pull-request` skill: current timestamp, current phase (not a new one), `orchestrator`, "Resumed by orchestrator".
   - Idempotency: if the last Phase Log row already has this phase value and summary starts with "Resumed", do not append.
* **STEP-G: Route to the resume point:**

| Phase Found | Resume Point | Pre-resume Check |
|-------------|--------------|------------------|
| `Implementing` | **Phase 5: Implement** | Check `git diff --stat` and `git status` to assess regression test + fix progress. Report assessment to user. |
| `Reviewing` | **Phase 7: Submit** | Verify Review Summary block is populated |
| `Ready` | **STOP** | Report "PR #N is already finalized and marked Ready" |

> **`Implementing` is the most nuanced resume point.** The orchestrator must compare planned tasks against actual file changes to identify remaining work. Checkout the PR branch, run `git diff --stat` against the base, and cross-reference with the task list. Report what appears complete vs. outstanding before proceeding.

## Phase 1: Understand

* **STEP-1: Delegate to `jira-reader`**: Pass the JIRA ticket key/URL. Receive a structured bug report with reproduction steps, expected vs. actual behavior, and affected components.
* **STEP-2: Read project context**: Check `copilot-instructions.md` for coding standards, architecture, and build/test commands.
* **STEP-3: Explore the codebase**: Locate the relevant code paths based on the bug report.

## Phase 2: Reproduce & Diagnose

* **STEP-4: Attempt to reproduce the bug**:
   - Run relevant existing tests to see if any already fail
   - Trace the code path described in the reproduction steps
   - If the bug cannot be reproduced, report this to the user before proceeding

* **STEP-5: Identify root cause**:
   - Analyze the code paths involved
   - Determine why the bug occurs (off-by-one, missing null check, race condition, wrong logic, etc.)
   - Document the root cause clearly — this will go into the PR description

## Phase 3: Plan & Propose

* **STEP-6: Plan the fix**:
   - Describe the minimal, targeted change that addresses the root cause
   - Identify which files need to change
   - Plan the regression test: a test that fails before the fix and passes after
   - For complex fixes (touches > 3 files or risky areas like auth/payments), present the plan to the user and wait for confirmation
   - For simple fixes, present and proceed immediately

* **STEP-7: Create a bugfix branch** using the git-operations skill:
   ```bash
   python3 ./.github/skills/git-operations/scripts/git_helper.py create-branch <TICKET_KEY> fix
   ```

* **STEP-8: Create draft PR** using the `create-pull-request` skill:
   - Populate the canonical PR body template with: Status (`Implementing`), Links (include Branch name), Intent (include root cause in Problem), Plan, first Phase Log entry ("Branch created, draft PR created, entering implementation").
   - Create as `--draft`.
   - **Store the returned `PR_NUMBER`** — it is required for all subsequent updates.
   ```bash
   python3 ./.github/skills/create-pull-request/scripts/pr_helper.py create \
     --title "<type>(<scope>): <description> [<TICKET_KEY>]" \
     --body-file /tmp/pr_body.md \
     --draft --labels "bugfix"
   ```

## Phase 4: Implement

* **STEP-9: Write a regression test first**:
    - Add a test that reproduces the bug (should fail against current code logic)
    - This test must pass after the fix is applied

* **STEP-10: Implement the fix**:
    - Make the minimal change needed to resolve the root cause
    - Follow project conventions from `copilot-instructions.md`
    - Avoid unrelated changes — keep the diff focused

* **STEP-11: Run the full test suite**:
    ```bash
    # Use the test command from copilot-instructions.md
    ```
* **STEP-12: Run linting** if configured:
    ```bash
    # Use the lint command from copilot-instructions.md
    ```
* **STEP-13: Update PR** using the `update-pull-request` skill:
    - No status change (still `Implementing`)
    - Append Phase Log: "Fix applied, regression test passing"

## Phase 5: Self-Review

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

## Phase 6: Submit

* **STEP-18: Delegate to `pr-author`**: Pass the JIRA ticket key **and the PR number**. The pr-author will:
    - Commit and push changes
    - Use the `update-pull-request` skill to finalize: Status → `Ready`, Draft → `false`, sanitize sections, `--undraft`
    - Append Phase Log: "PR finalized and marked ready for review"
* **STEP-19: Report to the user**: Provide the PR URL and a brief summary including the root cause and the fix.
