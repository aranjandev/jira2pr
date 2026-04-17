---
name: update-pull-request
description: 'Updates an existing PR body by modifying MUTABLE blocks and appending to APPEND-ONLY blocks, following the canonical PR state schema and idempotency rules from pr-description.instructions.md. Use when transitioning between workflow phases (branching, implementation complete, review complete, finalization).'
argument-hint: 'PR number, target phase, actor, summary, and optional block content'
---

# Update Pull Request

Updates the body of an existing draft PR at workflow phase transitions. Operates on the canonical PR state document using boundary markers (`PR_BLOCK:*:BEGIN/END`) for safe, idempotent edits.

## When to Use

- After branch creation → update Status to `Implementing`, add Branch link
- After implementation complete → append Phase Log entry
- After self-review → update Status to `Reviewing`, populate Review Summary
- At finalization (submit) → update Status to `Ready`, undraft, sanitize sections
- After a scope change → append Decisions Log entry, update affected IMMUTABLE section

## Callers

| Phase | Caller |
|-------|--------|
| Branching through Review | **orchestrator** (direct skill invocation) |
| Finalization (Submit) | **pr-author** agent |

## Prerequisites

- Draft PR already exists with a known PR number
- `curl`, `git`, `jq` installed
- `GITHUB_TOKEN` or `BITBUCKET_TOKEN` set
- PR body contains all `PR_BLOCK:*:BEGIN/END` boundary markers

## Inputs

The caller must provide:

| Input | Required | Description |
|-------|----------|-------------|
| PR number | Always | The PR number returned by `create-pull-request` |
| Target phase | Always | One of: `Planning`, `Implementing`, `Reviewing`, `Ready` |
| Actor | Always | Agent name performing the update (e.g., `orchestrator`, `pr-author`) |
| Summary | Always | One-line description for the Phase Log entry |
| Branch name | If entering `Implementing` | Branch name to populate Links block |
| Review Summary content | If entering `Reviewing` | Risk level, findings, resolutions from reviewer |
| Decisions Log entry | If scope changed | Full decision entry (date, title, decision, rationale, alternatives, impact, trigger) |
| Title | Optional | Updated PR title (typically only at finalization) |
| Undraft | If entering `Ready` | Flag to mark PR as ready for review |

## Procedure

### Step 1: Fetch current PR body

```bash
./.github/skills/create-pull-request/scripts/pr_helper.sh fetch-body \
  --pr-number <PR_NUMBER> > /tmp/pr_current_body.md
```

### Step 2: Validate boundary markers

Scan `/tmp/pr_current_body.md` for all expected markers:
- `PR_BLOCK:STATUS:BEGIN` / `PR_BLOCK:STATUS:END`
- `PR_BLOCK:LINKS:BEGIN` / `PR_BLOCK:LINKS:END`
- `PR_BLOCK:INTENT:BEGIN` / `PR_BLOCK:INTENT:END`
- `PR_BLOCK:PLAN:BEGIN` / `PR_BLOCK:PLAN:END`
- `PR_BLOCK:PHASE_LOG:BEGIN` / `PR_BLOCK:PHASE_LOG:END`
- `PR_BLOCK:REVIEW_SUMMARY:BEGIN` / `PR_BLOCK:REVIEW_SUMMARY:END`
- `PR_BLOCK:DECISIONS_LOG:BEGIN` / `PR_BLOCK:DECISIONS_LOG:END`
- `PR_BLOCK:OPEN_QUESTIONS:BEGIN` / `PR_BLOCK:OPEN_QUESTIONS:END`
- `PR_BLOCK:AGENT_NOTES:BEGIN` / `PR_BLOCK:AGENT_NOTES:END`

**If any marker pair is missing or malformed: STOP and report the error.** Do not guess where to write.

### Step 3: Update MUTABLE blocks

Replace the **entire content** between `BEGIN` and `END` markers for each block being updated.

#### Status Block (always updated)
Replace content between `PR_BLOCK:STATUS:BEGIN` and `PR_BLOCK:STATUS:END` with:
```markdown
<!-- MUTABLE | owners: orchestrator, pr-author | updated-at: each phase transition -->

| Field | Value |
|-------|-------|
| Phase | `<target-phase>` |
| Draft | `<true or false>` |
| Last Updated | <current ISO 8601 timestamp> |
| Updated By | <actor> |
```

#### Links Block (when entering `Implementing`)
Replace content between `PR_BLOCK:LINKS:BEGIN` and `PR_BLOCK:LINKS:END` — update Branch from `_pending_` to the actual branch name:
```markdown
<!-- MUTABLE | owners: orchestrator | set-at: creation, updated-at: branch phase -->

| Resource | Value |
|----------|-------|
| JIRA | <existing-ticket-url> |
| Branch | `<branch-name>` |
| Design / Docs | <existing-value> |
```

#### Review Summary Block (when entering `Reviewing`)
Replace content between `PR_BLOCK:REVIEW_SUMMARY:BEGIN` and `PR_BLOCK:REVIEW_SUMMARY:END` with the reviewer's findings.

### Step 4: Append to APPEND-ONLY blocks

#### Phase Log

**Idempotency check:** Read the existing Phase Log table rows. If the **last row** has the same Phase value as the target phase, this is a duplicate — **do not append**.

If not a duplicate, append a new row:
```
| <ISO timestamp> | `<target-phase>` | <actor> | <summary> |
```

#### Decisions Log (only if scope changed)

**Idempotency check:** Scan existing entries. If an entry with the same **date + title** exists, **do not append**.

If not a duplicate, append a new entry:
```markdown
### <YYYY-MM-DD> — <Decision Title>
- **Decision:** <what was decided>
- **Rationale:** <why>
- **Alternatives Considered:** <what else was evaluated>
- **Impact:** <what this changes>
- **Triggered By:** <phase-name / finding / user-request>
```

### Step 5: Write updated body and push

```bash
# Write the modified body to a temp file
cat > /tmp/pr_updated_body.md << 'BODY'
<updated PR body>
BODY

# Update the PR
./.github/skills/create-pull-request/scripts/pr_helper.sh update \
  --pr-number <PR_NUMBER> \
  --body-file /tmp/pr_updated_body.md
```

If entering `Ready` phase (finalization):
```bash
./.github/skills/create-pull-request/scripts/pr_helper.sh update \
  --pr-number <PR_NUMBER> \
  --body-file /tmp/pr_updated_body.md \
  --undraft
```

If updating the title at finalization:
```bash
./.github/skills/create-pull-request/scripts/pr_helper.sh update \
  --pr-number <PR_NUMBER> \
  --body-file /tmp/pr_updated_body.md \
  --title "<final title>" \
  --undraft
```

### Step 6: Confirm

Report the PR URL back to the caller. If the update failed, report the error and the HTTP status code so the caller can decide whether to retry or escalate.

## Phase-Specific Quick Reference

| Target Phase | Status Update | Links Update | Phase Log Append | Review Summary | Undraft |
|--------------|---------------|-------------|------------------|----------------|---------|
| `Implementing` (branch) | Phase → `Implementing` | Branch → name | Yes | No | No |
| `Implementing` (impl done) | No change | No | Yes | No | No |
| `Reviewing` | Phase → `Reviewing` | No | Yes | Yes (populate) | No |
| `Ready` (finalize) | Phase → `Ready`, Draft → `false` | No | Yes | Sanitize | Yes |

## Idempotency Rules Summary

These rules are defined in detail in `pr-description.instructions.md`. The key points for this skill:

1. **Status block**: full overwrite — re-running produces identical output (timestamp may differ, acceptable).
2. **Phase Log**: dedupe by last row's Phase value — do not append if duplicate.
3. **Decisions Log**: dedupe by date + title — do not append if duplicate.
4. **Boundary markers**: never remove, reorder, or nest. If missing, stop and report.
5. **Content outside markers**: do not modify (owned by humans or pr-author finalizer).

## Important

- Always use `fetch-body` to get the latest PR body before editing — never edit from a stale copy
- The `pr_helper.sh` script lives at `.github/skills/create-pull-request/scripts/pr_helper.sh`
- Preserve all content outside boundary markers — human reviewers may have added comments
- At finalization, the pr-author may remove the `Agent Notes` section if empty
- Use `--dry-run` on `pr_helper.sh update` to preview changes before applying
