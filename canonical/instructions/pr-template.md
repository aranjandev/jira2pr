# PR Body Template

> **Schema reference:** Block definitions, mutability rules, idempotency rules, and ownership model are defined in [pr-schema.instructions.md](pr-schema.instructions.md). Phase transitions are defined in each workflow file (`agent-workflows/feature.md`, `agent-workflows/bugfix.md`).

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
| Phase | `Implementing` |
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
| Branch | <branch-name> |
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