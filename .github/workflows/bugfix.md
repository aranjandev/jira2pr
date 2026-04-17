# Bugfix Workflow

Fix a bug end-to-end from a JIRA ticket to a submitted Pull Request.

## Phase 1: Understand

1. **Delegate to `jira-reader`**: Pass the JIRA ticket key/URL. Receive a structured bug report with reproduction steps, expected vs. actual behavior, and affected components.
2. **Read project context**: Check `copilot-instructions.md` for coding standards, architecture, and build/test commands.
3. **Explore the codebase**: Locate the relevant code paths based on the bug report.

## Phase 2: Reproduce & Diagnose

4. **Attempt to reproduce the bug**:
   - Run relevant existing tests to see if any already fail
   - Trace the code path described in the reproduction steps
   - If the bug cannot be reproduced, report this to the user before proceeding

5. **Identify root cause**:
   - Analyze the code paths involved
   - Determine why the bug occurs (off-by-one, missing null check, race condition, wrong logic, etc.)
   - Document the root cause clearly — this will go into the PR description

## Phase 3: Plan

6. **Plan the fix**:
   - Describe the minimal, targeted change that addresses the root cause
   - Identify which files need to change
   - Plan the regression test: a test that fails before the fix and passes after
   - For complex fixes (touches > 3 files or risky areas like auth/payments), present the plan to the user and wait for confirmation
   - For simple fixes, present and proceed immediately

## Phase 4: Branch

7. **Create a bugfix branch** using the git-operations skill:
   ```bash
   ./.github/skills/git-operations/scripts/git_helper.sh create-branch <TICKET_KEY> fix
   ```

## Phase 5: Implement

8. **Write a regression test first**:
   - Add a test that reproduces the bug (should fail against current code logic)
   - This test must pass after the fix is applied

9. **Implement the fix**:
   - Make the minimal change needed to resolve the root cause
   - Follow project conventions from `copilot-instructions.md`
   - Avoid unrelated changes — keep the diff focused

10. **Run the full test suite**:
    ```bash
    # Use the test command from copilot-instructions.md
    ```
11. **Run linting** if configured:
    ```bash
    # Use the lint command from copilot-instructions.md
    ```

## Phase 6: Self-Review

12. **Delegate to `reviewer`**: Ask the reviewer agent to analyze all changes.
13. **Address findings**:
    - Fix any CRITICAL or HIGH findings immediately
    - Apply MEDIUM suggestions if they're quick wins
    - Note LOW/nit findings but don't block on them
14. **Re-run tests** after addressing review feedback.

## Phase 7: Submit

15. **Delegate to `pr-author`**: Pass the JIRA ticket key and ask it to commit, push, and create a PR.
16. **Report to the user**: Provide the PR URL and a brief summary including the root cause and the fix.
