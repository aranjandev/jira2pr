---
name: manage-state
description: 'Creates, reads, and updates the per-workflow agent state file at .github/state/<TICKET-KEY>.md — a fast-access local mirror of workflow context that reduces GitHub API round-trips and enables richer resumption. Use when creating a new workflow, at phase transitions, or when resuming.'
argument-hint: 'operation and ticket key (e.g., create KAN-12, update KAN-12)'
---
# Manage State

Creates, reads, and updates the per-workflow agent state file at `.github/state/<TICKET-KEY>.md`. The state file is a fast-access local mirror of workflow context that reduces GitHub API round-trips and enables richer workflow resumption.

> **Schema reference:** Block definitions and mutability rules are in [`.github/state/SCHEMA.md`](../../state/SCHEMA.md). The template is [`.github/state/workflow-state.tpl.md`](../../state/workflow-state.tpl.md).

## Content Depth Principle

The state file is the agent's **working memory**. Write each block with enough detail that an agent resuming work in a new session can fully reconstruct context and continue from the current step **without re-reading the JIRA ticket, re-running research, re-exploring the codebase, or re-deriving decisions**.

The PR body is human-facing and deliberately summarized. The state file is agent-facing and should be **comprehensive** — include the raw reasoning, not just the conclusions.

### Per-Block Depth Guide

| Block | Depth | What to include | What to omit |
|-------|-------|-----------------|--------------|
| **UNDERSTANDING** | Full reproduction of ticket requirements in the agent's own words | Every requirement and acceptance criterion from the ticket; edge cases and ambiguities identified during codebase exploration; key file paths and patterns discovered; existing conventions relevant to the task; build/test/lint commands confirmed | Verbatim copy-paste of the entire JIRA description (summarize in your own words instead) |
| **RESEARCH** | Full findings with rationale | Each option evaluated and why it was accepted or rejected; library versions, API patterns, algorithm trade-offs; links to docs or references consulted; final recommendation with explicit reasoning | Raw web-page dumps or full API reference pages |
| **PLAN** | Mirror the PR body task list, **plus** implementation notes per task | Task table with status; for each task: which files to create/modify, what pattern to follow, what tests to add, any gotchas discovered during planning; test strategy with exact commands; risk details with concrete mitigation steps | Vague tasks like "implement feature" — be specific enough that the task could be done without re-reading the ticket |
| **IMPLEMENTATION** | Running log of what was done and why | Every file created or modified (with brief note on what changed); every test added (with what it covers); any decisions made during implementation that deviated from the plan; command outputs if relevant (e.g., test results) | Full file contents or large diffs (reference the file path instead) |
| **REVIEW** | Structured findings and their resolution status | Risk level; each finding with severity, description, and resolution; what was fixed vs. deferred vs. accepted | Full code snippets from the review (summarize the issue and point to the file/line) |

### Rule of Thumb

After writing a block, ask: *"If I lost my entire conversation history and only had this state file, could I continue from the current phase without re-doing any prior phase's work?"* If the answer is no, add more detail.

## When to Use

- **Create**: After creating the draft PR in Phase 2 (branch + PR are both known)
- **Read**: At workflow resume (Phase 0b) to restore context without a GitHub API call
- **Update (phase transition)**: At each phase transition, after calling `update-pull-request`
- **Update (task progress)**: After completing each task in Phase 3/4 to keep PLAN block current

## Procedure

### Create a New State File

1. Copy the template:
   ```bash
   cp .github/state/workflow-state.tpl.md .github/state/<TICKET-KEY>.md
   ```

2. Populate each block per the **Per-Block Depth Guide** above. The data source for each block at creation:
   - **META**: workflow type, ticket key/URL, branch, PR number/URL, timestamps
   - **PHASE**: `Implementing`
   - **UNDERSTANDING**: Phase 1 output (jira-reader + codebase exploration)
   - **RESEARCH**: Phase 2 researcher output (leave empty if no research was needed)
   - **PLAN**: mirror the PR body task list + per-task implementation notes
   - **PHASE_LOG**: first row — same timestamp and summary as the PR body Phase Log entry

3. Write the populated content using single-quoted Python (never heredocs):
   ```bash
   python3 -c 'content = open(".github/state/workflow-state.tpl.md").read(); # ... populate content ...; open(".github/state/<TICKET-KEY>.md","w").write(content)'
   ```

4. Commit the state file alongside any other Phase 2 work:
   ```bash
   python3 ./.github/skills/git-operations/scripts/git_helper.py commit "chore(state): initialize workflow state [<TICKET-KEY>]"
   ```

### Read / Parse State File

```bash
cat .github/state/<TICKET-KEY>.md
```

Parse `STATE_BLOCK:*:BEGIN/END` boundary markers to extract specific sections:
- **UNDERSTANDING block** → requirements, discovered file paths, conventions, build commands (primary context for resuming Phase 1 work)
- **RESEARCH block** → options evaluated, recommendation, references (prevents re-running research)
- **META block** → ticket, branch, PR number for API calls
- **PHASE block** → current phase for routing
- **PLAN block** → task table with statuses for progress assessment
- **PHASE_LOG block** → audit trail for context

If the state file does not exist (older workflow or first resume), fall back to fetching the PR body:
```bash
python3 ./.github/skills/create-pull-request/scripts/pr_helper.py fetch-body --pr-number <PR_NUMBER>
```

### Update — Phase Transition

At each phase transition (after calling `update-pull-request`):

1. Update the **PHASE block**: replace the phase value
2. Update the **META block**: advance `Updated At` to current UTC timestamp
3. Update phase-specific MUTABLE blocks per the **Per-Block Depth Guide**:
   - Entering `Reviewing`: populate **REVIEW** block
   - Entering `Submitting`: update **REVIEW** block with final resolutions
   - Entering `Ready`: ensure **IMPLEMENTATION** block is complete
4. Append a row to the **PHASE_LOG block** — apply the same dedupe rule as the PR body:
   - Do not append if the last row already has the same Phase value

5. Commit the updated state file:
   ```bash
   git add .github/state/<TICKET-KEY>.md
   # Include in the phase-transition commit
   ```

### Update — Task Progress

During Phase 3/4, after completing each task:

1. In the **PLAN block**, update the task's `Status` column: `pending` → `in-progress` → `done`
2. Update the **IMPLEMENTATION block** per the depth guide (files modified, tests added, any plan deviations)
3. Stage the state file:
   ```bash
   git add .github/state/<TICKET-KEY>.md
   # Include in the same commit as the code change
   ```

### Archive at Completion

When the pr-author finalizes the PR (moves to `Ready`):
```bash
mkdir -p .github/state/archive
git mv .github/state/<TICKET-KEY>.md .github/state/archive/<TICKET-KEY>.md
```

## Important

- The state file lives in the working tree and **must be committed to git** — it is not a temp file
- Never store secrets or credentials in the state file
- If `STATE_BLOCK` boundary markers are missing or malformed, **stop and report** — do not proceed
- The state file supplements the PR body; it does not replace it. The PR body remains the canonical human-visible state
