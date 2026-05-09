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
   python3 ./.github/skills/git-operations/scripts/git_helper.py create-branch <TICKET_KEY> <TYPE>
   ```
   Reference: [git_helper.py](./scripts/git_helper.py)

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
   python3 ./.github/skills/git-operations/scripts/git_helper.py commit "<MESSAGE>"
   ```

2. **Commit message format:** Follow the rules in [`commit-conventions.instructions.md`](../../instructions/commit-conventions.instructions.md).

3. **Commit strategy — atomic commits:**
   - One commit per logical change (not per file)
   - Each commit should be independently buildable
   - Group related changes: e.g., new function + its tests = one commit
   - Separate refactoring from feature work

### Pushing

1. Run:
   ```bash
   python3 ./.github/skills/git-operations/scripts/git_helper.py push
   ```

2. Sets upstream tracking automatically on first push.

3. **Token-based authentication (HTTPS remotes):** The script automatically injects credentials from the environment via `GIT_ASKPASS` — no interactive prompt, no hanging. Ensure the relevant token is in `.env` or already exported:
   - GitHub: `GITHUB_TOKEN=<pat>`
   - Bitbucket: `BITBUCKET_TOKEN=<app-password>` and `BITBUCKET_USERNAME=<username>`

   If the token is missing and push stalls, verify that `.env` at the repo root contains the correct variable and that `load_env()` ran (it runs automatically when you invoke the script). **Do not fall back to `gh auth` or `gh` CLI for pushing** — the script handles credentials directly.

### Checking Status

1. Run:
   ```bash
   python3 ./.github/skills/git-operations/scripts/git_helper.py status
   ```

2. Shows: current branch, upstream tracking, ahead/behind counts, changed files.

## Important

- Always create a branch before making changes — never commit to main/master directly
- Ensure the branch name includes the ticket key for traceability
- Write commit messages that explain **why**, not just **what**
- If committing on behalf of a workflow, include the ticket key in the commit footer
