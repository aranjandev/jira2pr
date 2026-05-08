# Agent Workflow State — Schema and Usage

State files are agent-maintained per-workflow documents stored at `.github/state/<TICKET-KEY>.md`. They serve as a fast-access local mirror of workflow context — reducing the need to round-trip to the GitHub API on every state read and enabling richer workflow resumption than the PR body alone.

## Purpose

| Layer | File | Audience | Updated When |
|-------|------|----------|--------------|
| PR body | GitHub PR | Human reviewers | Each phase transition (via `update-pull-request`) |
| **State file** | `.github/state/<TICKET-KEY>.md` | Agents only | Each phase transition + major task steps |

The PR body is the canonical **human-visible** state. The state file is the canonical **agent-local** state. Both are always in sync at phase boundaries.

## File Naming and Lifecycle

- One state file per workflow: `.github/state/<TICKET-KEY>.md`
  - Example: `.github/state/KAN-12.md`
- **Created** by the orchestrator at Phase 2 (after branch + draft PR creation) using the `manage-state` skill
- **Updated** at each phase transition and after completing significant tasks
- **Committed to git** alongside code changes so context survives session restarts
- **Archived** by the pr-author when the PR reaches `Ready` — moved to `.github/state/archive/<TICKET-KEY>.md` (see Archive section below)

## Archive

Completed workflow state files are preserved in `.github/state/archive/` rather than deleted, providing a historical record of past workflows.

| Property | Value |
|----------|-------|
| Location | `.github/state/archive/<TICKET-KEY>.md` |
| Created by | `pr-author`, at the `Ready` phase transition |
| Operation | `git mv .github/state/<TICKET-KEY>.md .github/state/archive/<TICKET-KEY>.md` |
| Mutability | **Read-only after archival** — archived files must never be updated |
| Included in commit | Yes — the `git mv` is included in the finalization commit alongside the artifact registry update |

**Rules:**
- Archive only when the PR has reached `Ready` — never archive an in-progress state file
- If the PR is closed without merging (abandoned), delete the state file rather than archiving it (`git rm`)
- Archived files are for historical reference only; a resuming agent must never read from archive to continue work

## Block Definitions

All machine-writable sections use XML-style boundary markers consistent with the PR body schema:

```
<!-- STATE_BLOCK:<SECTION>:BEGIN -->
<content>
<!-- STATE_BLOCK:<SECTION>:END -->
```

| Block | Mutability | Owner | Purpose |
|-------|-----------|-------|---------|
| **META** | MUTABLE | orchestrator, pr-author | Workflow identity: ticket, branch, PR number, timestamps |
| **PHASE** | MUTABLE | orchestrator, pr-author | Current workflow phase value |
| **UNDERSTANDING** | MUTABLE | orchestrator | Requirements summary, constraints, open questions |
| **RESEARCH** | MUTABLE | orchestrator | Research results from researcher agent (if invoked) |
| **PLAN** | MUTABLE | orchestrator | Task list with statuses, test strategy, risks |
| **IMPLEMENTATION** | MUTABLE | orchestrator | Files modified, tests added, command outputs |
| **REVIEW** | MUTABLE | orchestrator | Review risk level, findings, resolutions |
| **PHASE_LOG** | APPEND-ONLY | orchestrator, pr-author | Phase transition audit trail (mirrors PR body phase log) |

## Mutability Rules

- **MUTABLE blocks**: Entire block content is overwritten at each update. Keep only current state.
- **APPEND-ONLY block** (`PHASE_LOG`): New entries added chronologically. Existing entries must never be edited or removed.
- Boundary markers (`STATE_BLOCK:*:BEGIN/END`) must never be removed, reordered, or nested.
- If a boundary marker is missing or malformed, the agent must **stop and report** rather than guess where to write.

## Idempotency

- Phase transitions **overwrite** MUTABLE block content (timestamp may differ; acceptable).
- `PHASE_LOG`: Apply the same dedupe rule as the PR body — scan existing rows; do not append if the last row already has the same Phase value.

## Security

- Never store credentials, API tokens, or secrets in the state file.
- State files are git-tracked and visible to anyone with repo access.

## Use the `manage-state` skill

All state file operations (create, read, update) are handled via the `manage-state` skill.
