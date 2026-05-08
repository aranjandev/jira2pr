# State: <TICKET-KEY>

<!-- STATE_BLOCK:META:BEGIN -->
<!-- MUTABLE | owner: orchestrator, pr-author | updated-at: every phase transition -->

| Field | Value |
|-------|-------|
| Workflow Type | `<feature\|bugfix>` |
| Ticket Key | `<TICKET-KEY>` |
| Ticket URL | <ticket-url> |
| Branch | <branch-name> |
| PR Number | `<pr-number-or-pending>` |
| PR URL | <pr-url-or-pending> |
| Created At | <YYYY-MM-DDTHH:MM:SSZ> |
| Updated At | <YYYY-MM-DDTHH:MM:SSZ> |

<!-- STATE_BLOCK:META:END -->

---

## Current Phase

<!-- STATE_BLOCK:PHASE:BEGIN -->
<!-- MUTABLE | owner: orchestrator, pr-author | updated-at: every phase transition -->

`Planning`

<!-- STATE_BLOCK:PHASE:END -->

---

## Understanding

<!-- STATE_BLOCK:UNDERSTANDING:BEGIN -->
<!-- MUTABLE | owner: orchestrator | populated-at: Phase 1 -->

### Requirements Summary
<!-- One paragraph: what the ticket requires -->

### Key Constraints
<!-- Hard constraints shaping the solution -->
-

### Open Questions
<!-- Unresolved items that may affect implementation -->
-

<!-- STATE_BLOCK:UNDERSTANDING:END -->

---

## Research Results

<!-- STATE_BLOCK:RESEARCH:BEGIN -->
<!-- MUTABLE | owner: orchestrator | populated-at: Phase 2 if researcher agent was invoked -->
<!-- Leave empty if no research was needed -->

<!-- STATE_BLOCK:RESEARCH:END -->

---

## Plan

<!-- STATE_BLOCK:PLAN:BEGIN -->
<!-- MUTABLE | owner: orchestrator | populated-at: Phase 2 after plan approval -->

### Tasks
<!-- Mirrors PR body plan tasks. Status: pending | in-progress | done | skipped -->

| ID | Description | Status |
|----|-------------|--------|

### Test Strategy

### Risks

<!-- STATE_BLOCK:PLAN:END -->

---

## Implementation Progress

<!-- STATE_BLOCK:IMPLEMENTATION:BEGIN -->
<!-- MUTABLE | owner: orchestrator | updated progressively during Phase 3/4 -->

### Files Modified
<!-- Updated as each file is changed -->
-

### Tests Added
<!-- Updated as each test is added -->
-

<!-- STATE_BLOCK:IMPLEMENTATION:END -->

---

## Review

<!-- STATE_BLOCK:REVIEW:BEGIN -->
<!-- MUTABLE | owner: orchestrator | populated-at: review phase -->

**Risk Level:** `—`

### Findings
-

### Resolutions
-

<!-- STATE_BLOCK:REVIEW:END -->

---

## Phase Log

<!-- STATE_BLOCK:PHASE_LOG:BEGIN -->
<!-- APPEND-ONLY | owner: orchestrator, pr-author | one entry per phase transition -->
<!-- Mirrors PR body phase log. Dedupe: do not append if last row has same Phase value. -->

| Timestamp | Phase | Actor | Summary |
|-----------|-------|-------|---------|

<!-- STATE_BLOCK:PHASE_LOG:END -->
