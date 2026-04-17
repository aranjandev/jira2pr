---
description: "Canonical PR body schema for agent-maintained pull requests. Defines immutable, mutable, and append-only sections with workflow phase transition rules. Use when creating or updating a PR body during feature or bugfix workflows."
---

# PR State Document Schema

This file defines the canonical PR body structure maintained by coding agents throughout a workflow.
The PR body is a **live state document** — the orchestrator creates it as a draft after the Plan phase and updates it at each subsequent phase transition.

## Ownership Model

| Actor | Role | Allowed Operations |
|-------|------|--------------------|
| **orchestrator** | Primary owner during execution | Create draft PR; update MUTABLE sections; append to APPEND-ONLY sections |
| **pr-author** | Finalizer at submit phase | Sanitize, summarize, and polish all sections; set Phase → `Ready`, Draft → `false` |
| **reviewer** | Contributes review findings | Populate Review Summary via orchestrator delegation |

## Mutability Rules

Each section is tagged with one of three mutability levels:

| Tag | Meaning | Enforcement |
|-----|---------|-------------|
| `IMMUTABLE` | Locked after plan approval | Changes require a **Decisions Log** entry with scope-change reason before editing |
| `MUTABLE` | Machine-updated at phase transitions | Only designated owners may write; previous value is overwritten |
| `APPEND-ONLY` | New entries added chronologically | Existing entries must **never** be edited or removed |

## Phase State Model

```
Planning ──→ Implementing ──→ Reviewing ──→ Ready
```

Valid values: `Planning` · `Implementing` · `Reviewing` · `Ready`

## Phase Transition Map

Updates are **phase-level only** — no task-level churn in the PR body.

### Feature Workflow (`workflows/feature.md`)

| Workflow Phase | PR Phase | PR Action | Actor |
|----------------|----------|-----------|-------|
| Phase 2: Plan approved | `Planning` | **CREATE** draft PR. Populate: Status, Links, Intent, Plan. Append Phase Log. | orchestrator |
| Phase 3: Branch created | `Implementing` | **UPDATE** Status → `Implementing`. Add Branch link. Append Phase Log. | orchestrator |
| Phase 4: Implementation complete | `Implementing` | Append Phase Log entry (implementation done signal). No status change. | orchestrator |
| Phase 5: Self-review complete | `Reviewing` | **UPDATE** Status → `Reviewing`. Populate Review Summary. Append Phase Log. | orchestrator |
| Phase 6: Submit | `Ready` | **FINALIZE**: sanitize all sections, set Draft → `false`, Status → `Ready`. Append Phase Log. | pr-author |

### Bugfix Workflow (`workflows/bugfix.md`)

| Workflow Phase | PR Phase | PR Action | Actor |
|----------------|----------|-----------|-------|
| Phase 3: Plan approved | `Planning` | **CREATE** draft PR. Populate: Status, Links, Intent (include root cause), Plan. Append Phase Log. | orchestrator |
| Phase 4: Branch created | `Implementing` | **UPDATE** Status → `Implementing`. Add Branch link. Append Phase Log. | orchestrator |
| Phase 5: Implementation complete | `Implementing` | Append Phase Log entry (fix applied). No status change. | orchestrator |
| Phase 6: Self-review complete | `Reviewing` | **UPDATE** Status → `Reviewing`. Populate Review Summary. Append Phase Log. | orchestrator |
| Phase 7: Submit | `Ready` | **FINALIZE**: sanitize all sections, set Draft → `false`, Status → `Ready`. Append Phase Log. | pr-author |

### Resume Events

A **resume** is not a phase transition — it is a re-entry into the current phase after an interruption (crash, session timeout, manual retry). Resume events follow these rules:

- The orchestrator appends a Phase Log entry using the **current phase value** (not a new one) with summary starting with "Resumed by orchestrator".
- Because the phase value is the same as the last row, the standard dedupe rule applies: if the last Phase Log row already has the same phase and summary starts with "Resumed", **do not append a duplicate**.
- A resume never changes the Status block phase — it only records the re-entry in the Phase Log.
- After appending the resume entry, the orchestrator routes to the next workflow step for that phase (defined in each workflow's Phase 0 Bootstrap).

## Section Disambiguation

The PR body contains three chronological/tracking artifacts that serve distinct purposes:

| Artifact | Purpose | Contains | Must NOT Contain |
|----------|---------|----------|------------------|
| **Status** | Single snapshot of current state | Current phase, draft flag, timestamp, actor | History, past phases, rationale |
| **Phase Log** | Audit trail of phase transitions | One row per phase entry: timestamp, phase, actor, summary | Decisions, scope changes, findings detail |
| **Decisions Log** | Record of plan/scope mutations | One entry per scope change: what changed, why, alternatives, impact | Phase transitions, status snapshots, routine progress |

## Scope Change Protocol

If any `IMMUTABLE` section (Intent, Problem, Desired Outcome, Non-Goals, Constraints) must change after plan approval:

1. Add a **Decisions Log** entry with: reason for change, rationale, impact assessment.
2. Update the IMMUTABLE section content.
3. Append a **Phase Log** entry noting the scope change.

## Task Identity Rules

- Every task is assigned a stable ID with the prefix `T` followed by a sequential number (e.g., `T1`, `T2`, `T3`).
- **Task IDs are IMMUTABLE** — once assigned, a task ID must never be reused or renumbered, even if the task is removed.
- **Task text is MUTABLE** — wording may be updated, but any change to task text after plan approval requires a Decisions Log entry explaining the change.
- New tasks added after plan approval are appended with the next available ID and require a Decisions Log entry.
- Removed tasks are struck through (`~T4: ...~`), never deleted.

## Idempotency Rules

Agents may re-run phase transitions (e.g., after a crash or retry). The following rules ensure re-application is safe and produces no corruption:

### Status Block
- A phase transition **overwrites** the entire content between `<!-- PR_BLOCK:STATUS:BEGIN -->` and `<!-- PR_BLOCK:STATUS:END -->`.
- Re-running the same transition with the same phase value produces an identical block (timestamp may differ; this is acceptable).

### Phase Log
- Before appending, the agent **must scan** existing Phase Log rows.
- If a row already exists with the **same Phase value and no newer Phase row after it**, the transition is a duplicate — **do not append**.
- A re-run that enters a genuinely new phase (e.g., `Reviewing` after `Implementing`) always appends.

### Decisions Log
- Each entry is uniquely identified by the combination of **ISO date + Decision Title**.
- Before appending, the agent must check that no entry with the same date + title exists.
- If a duplicate is found, **do not append**.

### General
- Boundary markers (`PR_BLOCK:*:BEGIN` / `PR_BLOCK:*:END`) must never be removed, reordered, or nested.
- Content outside boundary markers must not be modified by machine updates (it is owned by human reviewers or the pr-author finalizer).
- If a boundary marker is missing or malformed, the agent must **stop and report** rather than guess where to write.

---
---

# PR Body Template

<!-- Everything below this line is the actual PR body that gets written to GitHub/Bitbucket. -->
<!-- Agents: copy from here down when creating the PR. -->
<!-- Boundary markers (PR_BLOCK:*:BEGIN/END) delimit machine-writable regions. -->
<!-- Agents MUST locate markers before writing. If a marker is missing, STOP and report. -->

# <TICKET_KEY>: <Short descriptive title>

## Status
<!-- PR_BLOCK:STATUS:BEGIN -->
<!-- MUTABLE | owners: orchestrator, pr-author | updated-at: each phase transition -->

| Field | Value |
|-------|-------|
| Phase | `Planning` |
| Draft | `true` |
| Last Updated | <YYYY-MM-DDTHH:MM:SSZ> |
| Updated By | <agent-name> |

<!-- PR_BLOCK:STATUS:END -->

## Links
<!-- PR_BLOCK:LINKS:BEGIN -->
<!-- MUTABLE | owners: orchestrator | set-at: creation, updated-at: branch phase -->

| Resource | Value |
|----------|-------|
| JIRA | <ticket-url> |
| Branch | _pending_ |
| Design / Docs | N/A |

<!-- PR_BLOCK:LINKS:END -->

---

## Intent
<!-- PR_BLOCK:INTENT:BEGIN -->
<!-- IMMUTABLE after: plan-approval | scope-change requires: Decisions Log entry -->

### Problem
<!-- One paragraph max. What user/system problem does this PR address? -->

### Desired Outcome
<!-- What behavior will exist after this PR is merged? -->

### Non-Goals
<!-- Explicitly list what is NOT being addressed -->
-

### Constraints
<!-- Hard constraints shaping the solution -->
- **Performance:**
- **Compatibility:**
- **Security:**
- **Timeline:**

<!-- PR_BLOCK:INTENT:END -->

---

## Plan
<!-- PR_BLOCK:PLAN:BEGIN -->
<!-- MUTABLE | owners: orchestrator | structural changes require: Decisions Log entry -->

### Tasks
<!-- Task IDs (T1, T2, ...) are IMMUTABLE. Task text is mutable via Decisions Log. -->
- [ ] T1: <task description>
- [ ] T2: <task description>
- [ ] T3: <task description>

### Test Strategy
- **Automated:**
- **Manual / user validation:**

### Risks & Mitigations

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| | `LOW` · `MEDIUM` · `HIGH` · `CRITICAL` | | `open` · `mitigated` |

<!-- PR_BLOCK:PLAN:END -->

---

## Phase Log
<!-- PR_BLOCK:PHASE_LOG:BEGIN -->
<!-- APPEND-ONLY | owners: orchestrator, pr-author | one entry per phase transition -->
<!-- Dedupe rule: do not append if the last row has the same Phase value -->

| Timestamp | Phase | Actor | Summary |
|-----------|-------|-------|---------|

<!-- PR_BLOCK:PHASE_LOG:END -->

---

## Review Summary
<!-- PR_BLOCK:REVIEW_SUMMARY:BEGIN -->
<!-- MUTABLE | owners: orchestrator (from reviewer), pr-author | populated-at: review phase, finalized-at: submit -->

**Risk Level:** `—`

### Findings
<!-- Key findings from self-review. CRITICAL/HIGH first. Omit if none. -->

### Resolutions
<!-- How findings were addressed. Omit if no findings. -->

<!-- PR_BLOCK:REVIEW_SUMMARY:END -->

---

## Decisions Log
<!-- PR_BLOCK:DECISIONS_LOG:BEGIN -->
<!-- APPEND-ONLY | required-when: scope change to IMMUTABLE sections, Plan restructure, task text change, review finding override -->
<!-- Dedupe rule: date + title combination must be unique; do not append if duplicate exists -->
<!-- Do NOT rewrite or remove past entries. -->

<!--
### <YYYY-MM-DD> — <Decision Title>
- **Decision:**
- **Rationale:**
- **Alternatives Considered:**
- **Impact:**
- **Triggered By:** <phase-name / finding / user-request>
-->

<!-- PR_BLOCK:DECISIONS_LOG:END -->

---

## Open Questions
<!-- PR_BLOCK:OPEN_QUESTIONS:BEGIN -->
<!-- MUTABLE | owners: orchestrator, pr-author -->
<!-- Unresolved items, intentionally deferred work -->

<!-- PR_BLOCK:OPEN_QUESTIONS:END -->

---

## Agent Notes
<!-- PR_BLOCK:AGENT_NOTES:BEGIN -->
<!-- MUTABLE | owners: orchestrator | breadcrumbs for downstream agents or human reviewers -->
<!-- Optional. pr-author removes this section if empty at finalization. -->

<!-- PR_BLOCK:AGENT_NOTES:END --> 