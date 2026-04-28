# PR State Document Schema

This file is the **single source of truth** for the PR body schema used by coding agents. The actual PR body template that implements this schema is in [pr-template.instructions.md](pr-template.instructions.md).

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
Planning ──→ Implementing ──→ Reviewing ──→ Submitting ──→ Ready
```

Valid values: `Planning` · `Implementing` · `Reviewing` · `Submitting` · `Ready`

> **Phase transitions** are defined in each workflow file (`agent-workflows/feature.md`, `agent-workflows/bugfix.md`). This schema only defines the valid phase values and the rules for updating PR blocks.

### Resume Events

A **resume** is not a phase transition — it is a re-entry into the current phase after an interruption (crash, session timeout, manual retry). Resume events follow these rules:

- The orchestrator appends a Phase Log entry using the **current phase value** (not a new one) with summary starting with "Resumed by orchestrator".
- Because the phase value is the same as the last row, the standard dedupe rule applies: if the last Phase Log row already has the same phase and summary starts with "Resumed", **do not append a duplicate**.
- A resume never changes the Status block phase — it only records the re-entry in the Phase Log.
- After appending the resume entry, the orchestrator routes to the next workflow step for that phase (defined in each workflow's Phase 0 Bootstrap).

## Section Disambiguation

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
