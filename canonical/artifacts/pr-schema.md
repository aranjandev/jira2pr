# Pull Request Schema

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

A pull request description must contain the following sections.

## Summary

Describe:

- what changed
- why the change was made
- expected impact

Limit to 1–3 paragraphs.

---

## Requirements Addressed

Summarize the requirements implemented.

Reference:

- requirements.md
- plan.md

Group related requirements where appropriate.

---

## Implementation Overview

Summarize the implementation at a high level.

Include:

- major components affected
- important design decisions
- new behaviors introduced

Do not repeat file-by-file implementation details.

---

## Tests

List relevant validation performed.

Include:

- automated tests
- manual verification
- linting
- build validation

If something was not executed, explicitly state so.

---

## Review Summary

Summarize significant review findings.

Include:

- notable risks identified
- important fixes made during review
- unresolved concerns

If no significant findings exist, state so.

---

## Risks and Limitations

Document:

- known limitations
- follow-up work
- operational considerations

Do not invent risks.

---

## Related Work

Include references to:

- JIRA tickets
- linked issues
- related pull requests

---

## Recommended Reviewer Focus

Highlight areas reviewers should pay particular attention to.

Keep concise and actionable.