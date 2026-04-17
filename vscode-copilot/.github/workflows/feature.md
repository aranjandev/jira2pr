# Feature Workflow

Implement a feature end-to-end from a JIRA ticket to a submitted Pull Request.

## Phase 1: Understand

1. **Delegate to `jira-reader`**: Pass the JIRA ticket key/URL. Receive a structured requirements document.
2. **Read project context**: Check `copilot-instructions.md` for coding standards, architecture, and build/test commands.
3. **Explore the codebase**: Search for relevant files, understand the existing patterns and architecture.

## Phase 2: Plan

4. **Assess if research is needed**:
   - After reading the ticket, identify if implementation requires:
     - External library/package evaluation (e.g., "use the best algorithm for X")
     - API or framework research (e.g., "integrate with OAuth provider")
     - Best practices lookup for unfamiliar domains
     - Comparison of approach options
   - If research is needed: Delegate to `Explore` agent with a query for package recommendations, algorithm comparisons, or API patterns. Return results into the plan phase.
   - If no research needed (e.g., "fix typo in error message"), skip to step 5.

5. **Create a task list** (use the `todo` tool) breaking down the implementation:
   - List each file to create or modify
   - List each test to add
   - Order tasks by dependency
   - If research was done (step 4), incorporate findings and rationale (e.g., "Use library X because Y")

6. **Format the plan** with these must-have items:
   - Summary of intended behavior after implementation
   - Tasks list from Step 5
   - Test strategy, must include what tests will be added/modified and what user tests to run
   - Risks and mitigations (e.g., "This touches the auth flow, so I'll add extra tests and be careful to follow existing patterns")

7. **Present the plan** to the user:
   - If the plan is complex (touches > 5 files), explicitly ask for confirmation and do not proceed until approval is received.
   - For simpler changes, present the plan and proceed immediately unless the user objects.

## Phase 3: Branch

8. **Create a feature branch** using the git-operations skill:
   ```bash
   ./.github/skills/git-operations/scripts/git_helper.sh create-branch <TICKET_KEY> feat
   ```

## Phase 4: Implement

9. **Implement changes** file by file, following the plan:
   - Follow project conventions from `copilot-instructions.md`
   - Write clean, idiomatic code
   - Add/update tests alongside implementation
   - Mark each task as completed in the todo list
10. **Run tests** after implementation:
    ```bash
    # Use the test command from copilot-instructions.md
    ```
11. **Run linting** if configured:
    ```bash
    # Use the lint command from copilot-instructions.md
    ```

## Phase 5: Self-Review

12. **Delegate to `reviewer`**: Ask the reviewer agent to analyze all changes.
13. **Address findings**:
    - Fix any CRITICAL or HIGH findings immediately
    - Apply MEDIUM suggestions if they're quick wins
    - Note LOW/nit findings but don't block on them
14. **Re-run tests** after addressing review feedback.

## Phase 6: Submit

15. **Delegate to `pr-author`**: Pass the JIRA ticket key and ask it to commit, push, and create a PR.
16. **Report to the user**: Provide the PR URL and a brief summary of what was done.
