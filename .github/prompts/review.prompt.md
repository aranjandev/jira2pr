---
description: "Reviews current code changes for quality, risks, and correctness. Produces a structured review with findings categorized by severity and actionable recommendations."
agent: "reviewer"
argument-hint: "Optional: specific area or concern to focus the review on"
---

# Review Current Changes

Review all uncommitted or unpushed code changes in the current workspace.

## Steps

1. **Analyze the diff** — examine all changed files
2. **Summarize changes** — group by component, describe what changed and why
3. **Identify risks** — check for breaking changes, error handling gaps, security issues, untested paths, performance concerns
4. **Produce a structured review** — findings by severity, with recommendations
5. **Provide a verdict** — APPROVE, APPROVE WITH SUGGESTIONS, or REQUEST CHANGES

If a specific area is mentioned, focus the review there while still noting any critical issues elsewhere.
