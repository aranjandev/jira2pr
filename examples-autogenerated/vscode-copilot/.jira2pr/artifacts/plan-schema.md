# Plan Schema

A plan defines the minimal implementation required to satisfy the requirements.

The plan must be deterministic, executable, and limited to the smallest reasonable scope.

---

# Summary

Describe the behavior being implemented.

Requirements:

- 3-10 bullet points
- Focus on observable behavior
- Do not discuss implementation details

---

# Files

List every file that must change.

For each file:

- Path
- Action: CREATE | MODIFY | DELETE
- Purpose

Example:

- path: src/auth/token_service.py
  action: MODIFY
  purpose: Add token expiration validation

---

# Tasks

Tasks are the primary execution units.

Requirements:

- Every task has a stable ID.
- Every task references exactly one file.
- Tasks must be dependency ordered.
- Tasks must contain a concrete implementation action.

Format:

## T1

File:
`src/auth/token_service.py`

Action:
Add expiration validation before token acceptance.

Dependencies:
None

---

## T2

File:
`tests/auth/test_token_service.py`

Action:
Add success and expiration test cases.

Dependencies:
T1

---

# Tests

For each affected test file:

- File path
- Success scenarios
- Edge or failure scenarios

Example:

## tests/auth/test_token_service.py

Success Cases

- Valid token is accepted

Failure Cases

- Expired token is rejected
- Missing expiration claim is rejected

---

# Constraints

Repository-specific implementation constraints.

Examples:

- Follow existing repository patterns.
- Do not introduce new dependencies.
- Do not perform unrelated refactoring.
- Keep modifications localized.

---

# Out of Scope

Explicitly list work that is not part of this implementation.

If there are no identified exclusions, state:

"None."