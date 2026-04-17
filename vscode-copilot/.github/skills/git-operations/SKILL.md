---
name: git-operations
description: 'Performs git operations: creating branches from ticket keys, staging and committing changes with conventional commit messages, and pushing to origin. Use when branching, committing, or pushing code.'
argument-hint: 'command and arguments (e.g., create-branch PROJ-123 feat)'
---

# Git Operations

Handles git workflow operations: branch creation, committing, and pushing. Enforces naming conventions and commit message standards.

## When to Use

- Creating a new feature/bugfix branch from a ticket key
- Committing changes with a properly formatted message
- Pushing a branch to origin
- Checking current git status

## Procedure

### Creating a Branch

1. Run the git helper script:
   ```bash
   ./.github/skills/git-operations/scripts/git_helper.sh create-branch <TICKET_KEY> <TYPE>
   ```
   Reference: [git_helper.sh](./scripts/git_helper.sh)

2. **Branch naming convention:**
   - Format: `<type>/<ticket-key-lowercase>`
   - Examples: `feat/proj-123`, `fix/proj-456`, `chore/proj-789`
   - Valid types: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`

3. The script will:
   - Pull latest from the default branch (main/master)
   - Create and checkout the new branch
   - If the branch already exists, check it out instead

### Committing Changes

1. Run:
   ```bash
   ./.github/skills/git-operations/scripts/git_helper.sh commit "<MESSAGE>"
   ```

2. **Commit message format** (Conventional Commits):
   ```
   <type>(<scope>): <short description>

   <optional body — what and why, not how>

   <optional footer — e.g., Refs: PROJ-123>
   ```

3. **Commit strategy — atomic commits:**
   - One commit per logical change (not per file)
   - Each commit should be independently buildable
   - Group related changes: e.g., new function + its tests = one commit
   - Separate refactoring from feature work

4. **Type mapping:**
   | Type | When |
   |------|------|
   | `feat` | New feature or capability |
   | `fix` | Bug fix |
   | `refactor` | Code restructuring with no behavior change |
   | `test` | Adding or updating tests only |
   | `docs` | Documentation changes only |
   | `chore` | Build, CI, tooling changes |

### Pushing

1. Run:
   ```bash
   ./.github/skills/git-operations/scripts/git_helper.sh push
   ```

2. Sets upstream tracking automatically on first push.

### Checking Status

1. Run:
   ```bash
   ./.github/skills/git-operations/scripts/git_helper.sh status
   ```

2. Shows: current branch, upstream tracking, ahead/behind counts, changed files.

## Important

- Always create a branch before making changes — never commit to main/master directly
- Ensure the branch name includes the ticket key for traceability
- Write commit messages that explain **why**, not just **what**
- If committing on behalf of a workflow, include the ticket key in the commit footer
