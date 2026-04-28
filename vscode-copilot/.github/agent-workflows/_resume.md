# Resume from PR — Shared Procedure

Shared steps for resuming a workflow from an existing draft PR. Both the feature and bugfix workflows reference this procedure in their Phase 0b, then supply their own routing table for Step G.

## Steps A–F: Parse and Restore PR State

* **STEP-A: Fetch PR body:**
   ```bash
   python3 ./.github/skills/create-pull-request/scripts/pr_helper.py fetch-body \
     --pr-number <PR_NUMBER> > /tmp/pr_current_body.md
   ```
* **STEP-B: Validate boundary markers** — confirm all `PR_BLOCK:*:BEGIN/END` pairs exist. If any are missing, report "This PR does not use the canonical schema — cannot resume" and stop.
* **STEP-C: Parse PR state:**
   - Status block → extract current Phase
   - Links block → extract JIRA URL, Branch name
   - Intent block → extract problem description and overview
   - Plan block → extract task list, test strategy, risks
   - Phase Log → read audit trail
* **STEP-D: Store `PR_NUMBER`** for subsequent update calls.
* **STEP-E: Populate the task tracker** (use the `todo` tool to plan the tasks) with tasks from the Plan block so progress tracking continues.
* **STEP-F: Append Phase Log** entry using `update-pull-request` skill: current timestamp, current phase (not a new one), `orchestrator`, "Resumed by orchestrator".
   - Idempotency: if the last Phase Log row already has this phase value and summary starts with "Resumed", do not append.

## Step G: Route to Resume Point

After completing Steps A–F, consult the **routing table defined in the calling workflow file** to determine the resume point based on the current Phase value.

> **`Implementing` is the most nuanced resume point.** The orchestrator must compare planned tasks against actual file changes to identify remaining work. Checkout the PR branch, run `git diff --stat` against the base, and cross-reference with the task list. Report what appears complete vs. outstanding before proceeding.
