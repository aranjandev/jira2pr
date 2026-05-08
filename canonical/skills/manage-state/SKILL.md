# Manage State

Creates, reads, and updates the per-workflow agent state file at `.github/state/<TICKET-KEY>.md`. The state file is a fast-access local mirror of workflow context that reduces GitHub API round-trips and enables richer workflow resumption.

> **Schema reference:** Block definitions and mutability rules are in [`.github/state/SCHEMA.md`](../../state/SCHEMA.md). The template is [`.github/state/workflow-state.tpl.md`](../../state/workflow-state.tpl.md).

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

2. Populate the file by overwriting the placeholder values in each block:
   - **META block**: Workflow type (`feature` or `bugfix`), ticket key, ticket URL, branch name, PR number, PR URL, `Created At` and `Updated At` (current UTC timestamp)
   - **PHASE block**: Set to `Implementing`
   - **UNDERSTANDING block**: Requirements summary from Phase 1 (jira-reader output), key constraints, any open questions
   - **RESEARCH block**: Research findings if researcher agent was invoked; leave empty otherwise
   - **PLAN block**: Task table (ID, Description, Status=`pending`), test strategy, and risks mirrored from the PR body Plan block
   - **PHASE_LOG block**: First row — same timestamp and summary as the PR body Phase Log entry at creation

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
- **META block** → ticket, branch, PR number for API calls
- **PHASE block** → current phase for routing
- **PLAN block** → task table for progress assessment
- **PHASE_LOG block** → audit trail for context

If the state file does not exist (older workflow or first resume), fall back to fetching the PR body:
```bash
python3 ./.github/skills/create-pull-request/scripts/pr_helper.py fetch-body --pr-number <PR_NUMBER>
```

### Update — Phase Transition

At each phase transition (after calling `update-pull-request`):

1. Update the **PHASE block**: replace the phase value
2. Update the **META block**: advance `Updated At` to current UTC timestamp
3. Update phase-specific MUTABLE blocks (e.g., REVIEW block at review phase)
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
2. In the **IMPLEMENTATION block**, add the file path to "Files Modified" or "Tests Added"
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
