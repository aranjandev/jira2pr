---
name: summarize-changes
description: 'Analyzes git diff output and produces a human-readable summary of all changes, grouped by component or module. Use when preparing PR descriptions, commit messages, or change reviews.'
argument-hint: 'optional: commit range or branch comparison'
---

# Summarize Changes

Analyzes the current git diff and produces a structured, human-readable summary of all changes grouped by component.

## When to Use

- Preparing a PR description and need a "What changed" section
- Reviewing what was implemented before committing
- Asked to "summarize changes", "what changed", "describe the diff"

## Procedure

1. **Get the diff statistics:**
   ```bash
   git diff --stat
   ```
   For comparing against a branch:
   ```bash
   git diff --stat main...HEAD
   ```

2. **Get the full diff** for analysis:
   ```bash
   git diff
   ```
   For committed changes not yet pushed:
   ```bash
   git diff origin/main...HEAD
   ```

3. **Analyze and group changes** by component/module:
   - Group files by their top-level directory or module
   - For each group, summarize what changed and why
   - Highlight new files vs. modified files vs. deleted files

4. **Produce a structured summary:**
   ```
   ## Changes Summary

   **Stats:** X files changed, Y insertions(+), Z deletions(-)

   ### <Component/Module 1>
   - `path/to/file.ts` — <what changed and why>
   - `path/to/other.ts` — <what changed and why>

   ### <Component/Module 2>
   - `path/to/file.py` — <what changed and why>

   ### New Files
   - `path/to/new.ts` — <purpose of this new file>

   ### Deleted Files
   - `path/to/old.ts` — <why removed>
   ```

5. **For each file change, describe:**
   - What was added/modified/removed
   - The intent behind the change (not just "added line 42")
   - Any behavioral impact

## Important

- Describe changes at a semantic level ("added retry logic to API client"), not line level ("added lines 42-58")
- Highlight breaking changes prominently
- Note any changes to public APIs, interfaces, or contracts
- If a change touches tests, mention what scenario is being tested
- Keep descriptions concise — one line per file unless the change is complex
