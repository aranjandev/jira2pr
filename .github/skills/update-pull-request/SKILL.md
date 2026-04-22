---
name: update-pull-request
description: 'Updates an existing PR body by modifying MUTABLE blocks and appending to APPEND-ONLY blocks. Use when transitioning between workflow phases.'
argument-hint: 'PR number, target phase, actor, summary, and optional block content'
---

# Update Pull Request

Updates the body of an existing draft PR at workflow phase transitions. Operates on the canonical PR state document using boundary markers (`PR_BLOCK:*:BEGIN/END`) for safe, idempotent edits.

> **Schema reference:** Block definitions, mutability rules, and idempotency rules are defined in [`pr-schema.instructions.md`](../../instructions/pr-schema.instructions.md). The PR body template is in [`pr-template.instructions.md`](../../instructions/pr-template.instructions.md).

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
- Python 3.9+ available (`python3 --version`)
- `git` installed
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
python3 ./.github/skills/create-pull-request/scripts/pr_helper.py fetch-body \
  --pr-number <PR_NUMBER> > /tmp/pr_current_body.md
```

### Step 2: Validate boundary markers

Scan `/tmp/pr_current_body.md` and confirm all `PR_BLOCK:*:BEGIN/END` pairs from the template exist. **If any marker pair is missing or malformed: STOP and report the error.** Do not guess where to write.

### Step 3: Update MUTABLE blocks

Replace the **entire content** between `BEGIN` and `END` markers for each block being updated. Use the structure from the PR template in `pr-template.instructions.md`.

- **Status Block** (always updated): Set Phase, Draft, Last Updated (ISO 8601), Updated By.
- **Links Block** (when entering `Implementing`): Update Branch to actual branch name.
- **Review Summary Block** (when entering `Reviewing`): Populate with reviewer's findings.

### Step 4: Append to APPEND-ONLY blocks

Apply idempotency rules from `pr-schema.instructions.md` before appending.

- **Phase Log:** Dedupe by last row's Phase value — do not append if duplicate. Append: `| <ISO timestamp> | \`<target-phase>\` | <actor> | <summary> |`
- **Decisions Log** (only if scope changed): Dedupe by date + title. Use the entry template from the PR body template.

### Step 5: Write updated body and push

```bash
# Write the modified body to a temp file, then update the PR
python3 ./.github/skills/create-pull-request/scripts/pr_helper.py update \
  --pr-number <PR_NUMBER> \
  --body-file /tmp/pr_updated_body.md
```

If entering `Ready` phase (finalization):
```bash
python3 ./.github/skills/create-pull-request/scripts/pr_helper.py update \
  --pr-number <PR_NUMBER> \
  --body-file /tmp/pr_updated_body.md \
  --undraft
```

If updating the title at finalization:
```bash
python3 ./.github/skills/create-pull-request/scripts/pr_helper.py update \
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

## Important

- Always use `fetch-body` to get the latest PR body before editing — never edit from a stale copy
- The `pr_helper.py` script lives at `.github/skills/create-pull-request/scripts/pr_helper.py`
- Preserve all content outside boundary markers — human reviewers may have added comments
- At finalization, the pr-author may remove the `Agent Notes` section if empty
- Use `--dry-run` on `pr_helper.py update` to preview changes before applying
