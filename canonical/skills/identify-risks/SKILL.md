# Identify Risks

Performs a systematic risk analysis of code changes to catch issues before they reach production.

## When to Use

- Reviewing changes before creating a PR
- A reviewer agent needs to assess risk
- Asked to "identify risks", "check for issues", "review for problems"

## Procedure

1. **Gather the changes** to analyze:
   ```bash
   git diff --stat
   git diff
   ```

2. **Run through each risk category** systematically:

### Breaking Changes
- [ ] Any public API signatures changed (parameters added/removed/reordered)?
- [ ] Any response/return type shapes changed?
- [ ] Any database schema changes without migrations?
- [ ] Any configuration format changes?
- [ ] Any removed or renamed exports/public methods?

### Error Handling
- [ ] New external calls (API, DB, file I/O) without try/catch or error handling?
- [ ] Error messages that might leak internal details (stack traces, paths, credentials)?
- [ ] Missing null/undefined checks on data from external sources?
- [ ] Catch blocks that silently swallow errors?

### Untested Code Paths
- [ ] New branches/conditions without corresponding test cases?
- [ ] Edge cases identified in the ticket but not tested?
- [ ] Error paths or fallback logic without tests?
- [ ] New functions or methods without any test coverage?

### Security (OWASP Top 10)
- [ ] User input used without validation or sanitization?
- [ ] SQL queries built with string concatenation?
- [ ] Hardcoded secrets, tokens, or credentials?
- [ ] New endpoints without authentication/authorization checks?
- [ ] Sensitive data logged or exposed in error messages?
- [ ] File paths constructed from user input without sanitization?

### Performance
- [ ] New database queries inside loops (N+1 problem)?
- [ ] Large data sets loaded into memory without pagination?
- [ ] Missing indexes for new query patterns?
- [ ] Synchronous operations that should be async?
- [ ] New regex patterns that could cause catastrophic backtracking?

### Data & Migrations
- [ ] Schema changes that need a migration script?
- [ ] Data backfill needed for new required fields?
- [ ] Backward compatibility with existing data?

3. **Produce a risk report:**
   ```
   ## Risk Assessment

   **Overall Risk Level:** LOW | MEDIUM | HIGH | CRITICAL

   ### Findings

   #### 🔴 Critical / 🟠 High / 🟡 Medium / 🟢 Low

   **<Finding title>**
   - File: `<path>`
   - Risk: <description of what could go wrong>
   - Recommendation: <how to fix or mitigate>

   ### Summary
   - Critical: N findings
   - High: N findings
   - Medium: N findings
   - Low: N findings

   ### Recommendation
   <Overall assessment: approve, approve with suggestions, or request changes>
   ```

## Important

- Be specific — cite file names and line ranges for each finding
- Don't flag theoretical risks that can't happen given the actual code paths
- Prioritize: critical/high findings first
- If no significant risks found, say so clearly — don't invent problems
- Consider the project context from the project instructions file when assessing conventions
