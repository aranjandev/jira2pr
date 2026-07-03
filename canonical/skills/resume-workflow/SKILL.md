# Resume Workflow

Restores full workflow context from an existing draft PR and its state file, then routes to the correct resume point within the calling workflow.

## When to Use

Invoke at the start of any workflow when the input is a **PR URL or number** rather than a JIRA ticket key. This skill replaces the need to manually fetch, parse, and validate PR state — it returns a fully restored context object that the orchestrator can act on immediately.

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| PR number or URL | Always | The draft PR to resume from |

## Procedure

### Step A: Fetch PR body

```bash
python3 ./.github/skills/create-pull-request/scripts/pr_helper.py fetch-body \
  --pr-number <PR_NUMBER> > /tmp/pr_current_body.md
```

### Step B: Validate boundary markers

Scan `/tmp/pr_current_body.md` and confirm all `PR_BLOCK:*:BEGIN/END` pairs exist.

> If any marker pair is missing or malformed: **STOP** and report "This PR does not use the canonical schema — cannot resume."

### Step C: Parse PR state

Extract from the PR body:
- **Status block** → current `Phase` value
- **Links block** → `JIRA URL`, `Branch` name, `PR Number`
- **Intent block** → problem description and overview
- **Plan block** → task list, test strategy, risks
- **Phase Log** → audit trail

Derive the `TICKET_KEY` from the JIRA URL (e.g., `https://…/browse/PROJ-123` → `PROJ-123`).

### Step D: Load state file (if present)

```bash
cat .github/state/<TICKET_KEY>.md
```

- If found: parse `STATE_BLOCK:*:BEGIN/END` markers and extract `UNDERSTANDING`, `PLAN` (with task statuses), `IMPLEMENTATION`, `RESEARCH`, and `META` blocks to enrich context beyond what the PR body contains.
- If not found: continue — the PR body blocks from Step C are sufficient.

> **Do not create** a new state file here. State file creation happens only at Plan phase during a fresh start.

### Step E: Store PR_NUMBER

Record the `PR_NUMBER` for all subsequent `update-pull-request` and `manage-state` calls.

### Step F: Restore task tracker

Populate the `{{TASK_TRACKING_INSTRUCTION}}` with tasks from the Plan block so progress tracking continues from where it left off.

### Step G: Append resume entry to Phase Log

Invoke `update-pull-request` to append a Phase Log entry:
- Timestamp: current UTC
- Phase: **current phase** (not a new one)
- Actor: `orchestrator`
- Summary: `Resumed by orchestrator`

**Idempotency:** If the last Phase Log row already has the same phase value and summary starts with "Resumed", do not append a duplicate.

## Output

Returns the restored context:

| Field | Source |
|-------|--------|
| `phase` | Status block |
| `ticket_key` | Parsed from JIRA URL in Links block |
| `branch` | Links block |
| `pr_number` | Links block |
| `plan` | Plan block + state file PLAN block (if richer) |
| `understanding` | State file UNDERSTANDING block (if available) |
| `research` | State file RESEARCH block (if available) |
| `implementation_log` | State file IMPLEMENTATION block (if available) |

## Resume Routing

After this skill completes, the **calling workflow** uses the returned `phase` value to route to the correct resume point. Each workflow defines its own routing table — this skill does not make routing decisions.

> **`Implementing` is the most nuanced resume point.** The orchestrator must compare planned tasks against actual file changes: check out the PR branch, run `git diff --stat` against the base, and cross-reference with the task list. Report what appears complete vs. outstanding before continuing.
