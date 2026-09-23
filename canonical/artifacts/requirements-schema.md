# Requirements Schema

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

A requirements document must contain the following sections.

## Ticket Metadata

Include:

- Key
- Summary
- Type
- Priority
- Status
- Labels

## Description

Original ticket description.

Preserve code snippets, links, and technical details verbatim.

## Requirements

List the explicit requirements stated in the ticket.

Use clear, atomic statements.

## Acceptance Criteria

Include:

- Explicit acceptance criteria from the ticket
- Inferred acceptance criteria when necessary

Clearly label inferred items.

## Subtasks and Linked Issues

Include:

- Subtasks
- Related tickets
- Dependencies

## Implementation Hints

Potential implementation considerations directly derived from the ticket.

Clearly distinguish:

- Explicit information
- Inferred information

## Missing Information

Identify important information that is absent or ambiguous.

## Assumptions

List assumptions made while interpreting the ticket.

Mark all assumptions explicitly.