# Review Schema

## Output Format

Output ONLY the structured markdown document defined below.

Do NOT include:
- Preamble or introduction
- Reasoning or analysis
- Agent conversation or commentary
- Code blocks or examples unless specified in sections
- Any text before the first section header
- Any text after the last section

Each section must appear exactly as specified. Missing sections are acceptable (mark "N/A" or omit), but do not add extra sections.

---

A review document must contain the following sections.

## Summary

Briefly describe:

- What changed
- Why the change was made
- Whether the implementation appears to satisfy the requirements

Limit to 1–3 paragraphs.

---

## Requirements Coverage

Evaluate whether the implementation satisfies the stated requirements.

For each unmet, partially met, or ambiguous requirement:

- Requirement
- Issue
- Impact

If all requirements are addressed, explicitly state so.

---

## Positive Findings

Identify successful aspects of the implementation, including:

- Correct use of existing patterns
- Good test coverage
- Clear implementation choices
- Appropriate scope control

Limit to the most important observations.

---

## Risk Assessment

Evaluate the implementation for risks in the following categories:

### Logic Correctness

- Incorrect behavior
- Missing conditions
- Faulty assumptions

### Edge Cases

- Unhandled inputs
- Boundary conditions
- Failure scenarios

### Security

- Authorization
- Authentication
- Input validation
- Secret handling

### Data Integrity

- Data loss
- Corruption
- Consistency issues

### Reliability

- Error handling
- Recovery behavior
- Operational concerns

### Performance

Only include material regressions or concerns.

Do not include speculative issues.

For every finding provide:

- Severity: Critical | High | Medium | Low
- Location
- Explanation
- Recommendation

---

## Test Assessment

Evaluate:

- Test completeness
- Coverage of acceptance criteria
- Coverage of success cases
- Coverage of edge/failure cases

Identify missing tests if applicable.

---

## Findings

List actionable review findings.

For each finding provide:

- Severity
- File(s)
- Description
- Recommendation

Requirements:

- Merge duplicate findings.
- Prioritize high-signal issues.
- Limit findings to five unless additional findings are critical.

---

## Review Verdict

THE REVIEW MUST END WITH EXACTLY ONE FENCED `review-verdict` block.

Allowed verdicts:

- `approve`
- `changes_requested`
- `escalate`

Example:

```review-verdict
verdict: changes_requested
reason: "The implementation does not correctly preserve first-file-wins semantics."
```

For an approved implementation:

```review-verdict
verdict: approve
reason: "No blocking findings."
```

No content may appear after the `review-verdict` block.