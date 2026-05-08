# Resume from PR — Shared Procedure

Shared steps for resuming a workflow from an existing draft PR. Both the feature and bugfix workflows reference this procedure in their Phase 0b, then supply their own routing table for Step G.

## Steps A–F: Parse and Restore PR State

* **STEP-A: Fetch PR body** using `pr_helper.py fetch-body --pr-number <PR_NUMBER>` (see `update-pull-request` skill).
* **STEP-B: Validate boundary markers** — confirm all `PR_BLOCK:*:BEGIN/END` pairs exist. If any are missing, report "This PR does not use the canonical schema — cannot resume" and stop.
* **STEP-C: Parse PR state:**
   - Status block → extract current Phase
   - Links block → extract JIRA URL, Branch name
   - Intent block → extract problem description and overview
   - Plan block → extract task list, test strategy, risks
   - Phase Log → read audit trail

* **STEP-C2: Load state file if present** using the `manage-state` skill:
   - Check for `.github/state/<TICKET_KEY>.md` (ticket key comes from the Links block)
   - If found: read UNDERSTANDING, PLAN (with task statuses), IMPLEMENTATION, and RESEARCH blocks to enrich restored context beyond what the PR body contains
   - If not found: continue \u2014 the PR body blocks parsed in STEP-C are sufficient for resumption
   - **Do not create** a new state file here; that happens only at Phase 2 during a fresh start

* **STEP-D: Store `PR_NUMBER`** for subsequent update calls.
* **STEP-E: Populate the task tracker** ({{TASK_TRACKING_INSTRUCTION}}) with tasks from the Plan block so progress tracking continues.
* **STEP-F: Append Phase Log** entry using `update-pull-request` skill: current timestamp, current phase (not a new one), `orchestrator`, "Resumed by orchestrator".
   - Idempotency: if the last Phase Log row already has this phase value and summary starts with "Resumed", do not append.

## Step G: Route to Resume Point

After completing Steps A–F, consult the **routing table defined in the calling workflow file** to determine the resume point based on the current Phase value.

> **`Implementing` is the most nuanced resume point.** The orchestrator must compare planned tasks against actual file changes to identify remaining work. Checkout the PR branch, run `git diff --stat` against the base, and cross-reference with the task list. Report what appears complete vs. outstanding before proceeding.
