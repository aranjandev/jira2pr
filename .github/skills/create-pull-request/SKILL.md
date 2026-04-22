---
name: create-pull-request
description: 'Creates a draft Pull Request using the canonical PR body template. Populates all initial blocks and returns PR URL + PR number. Use after the branch has been created and pushed.'
argument-hint: 'PR details (title, JIRA key, ticket data for Intent/Plan)'
---

# Create Pull Request

Creates an initial **draft** Pull Request using the canonical PR body template. The PR body is a live state document that will be updated at each workflow phase transition.

> **Schema reference:** Block definitions and mutability rules are in [`pr-schema.instructions.md`](../../instructions/pr-schema.instructions.md). The body template is in [`pr-template.instructions.md`](../../instructions/pr-template.instructions.md).

## When to Use

- Branch has been created and pushed to origin
- Orchestrator is ready to open a draft PR to track the implementation
- **NOT** for final submission — use the `update-pull-request` skill with `--undraft` for that

## Primary Caller

**orchestrator** — this skill is called directly by the orchestrator during the Branch phase (after `git-operations`), not by the pr-author agent.

## Prerequisites

- Python 3.9+ available (`python3 --version`)
- `git` installed
- `GITHUB_TOKEN` or `BITBUCKET_TOKEN` set
- On a feature/bugfix branch (not main/master)
- Branch pushed to origin
- Plan data available: ticket key, summary, intent, tasks, test strategy, risks

## Procedure

1. **Verify readiness:**
   ```bash
   git status
   git log --oneline origin/$(git branch --show-current)..$(git branch --show-current) 2>/dev/null
   ```
   Confirm on a feature/bugfix branch and branch is pushed.

2. **Read the PR body template** from `.github/instructions/pr-template.instructions.md` — use the section below the `# PR Body Template` heading as the skeleton.

3. **Populate the template blocks** using plan data from the orchestrator:
   - **STATUS**: Phase `Implementing`, Draft `true`, timestamp, `orchestrator`
   - **LINKS**: JIRA ticket URL, branch name, design docs (or `N/A`)
   - **INTENT**: Problem, Desired Outcome, Non-Goals, Constraints — from JIRA ticket
   - **PLAN**: Tasks (stable IDs T1, T2, ...), Test Strategy, Risks — from approved plan
   - **PHASE_LOG**: First entry: `"Branch created, draft PR created, entering implementation"`
   - All other blocks: leave at template defaults (empty or placeholder)

   Replace `<TICKET_KEY>` in the title heading with the actual ticket key and a short descriptive title.

4. **Generate the PR title:**
   - Format: `<type>(<scope>): <short description> [<TICKET_KEY>]`
   - Example: `feat(auth): add JWT token validation [PROJ-123]`
   - The type should match the branch prefix (`feat/` → `feat`, `fix/` → `fix`)

5. **Write body to a temp file and create the PR:**

   > **File writing rule — strictly enforced:** Never use heredocs (`<< 'EOF'`) or `python3 -c "..."` with double outer quotes — both corrupt output in agent shell sessions. **Always** use `python3 -c '...'` with single outer quotes and `\n` for newlines:
   >
   > ```bash
   > # Static content
   > python3 -c 'open("/tmp/pr_body.md","w").write("# TICKET: Title\n\nContent\n")'
   > # With dynamic values — concatenate inside the expression
   > python3 -c 'import datetime; ts=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"); open("/tmp/pr_body.md","w").write("# Title\n\nTimestamp: "+ts+"\n")'
   > ```

   Then create the PR (`--base` is required — use `main` unless the repo default branch differs):
   ```bash
   python3 ./.github/skills/create-pull-request/scripts/pr_helper.py create \
     --title "<PR_TITLE>" \
     --body-file /tmp/pr_body.md \
     --draft \
     --base main \
     --labels "<label1,label2>"
   ```
   Reference: [pr_helper.py](./scripts/pr_helper.py)

6. **Capture output:** The script prints two lines:
   ```
   PR_URL=https://github.com/owner/repo/pull/42
   PR_NUMBER=42
   ```
   **Both values must be returned** to the orchestrator — the PR number is required for all subsequent `update-pull-request` calls.

7. **Label conventions:**
   | Label | When |
   |-------|------|
   | `feature` | New feature |
   | `bugfix` | Bug fix |
   | `refactor` | Code restructuring |
   | `dependencies` | Dependency updates |

## Output Contract

The skill **must** return to the caller:
- `PR_URL` — for user-facing reporting
- `PR_NUMBER` — for subsequent update calls throughout the workflow

## Important

- Always create as `--draft` — the PR is not ready for review at this point
- Always link the JIRA ticket in the Links block
- Include the ticket key in the PR title for automatic JIRA linking
- Always write temp files with `python3 -c '...'` using single outer quotes — never heredocs (`<<EOF`), never `python3 -c "..."` with double outer quotes (shell expands `$` and backticks inside both)
- Use `--dry-run` first if uncertain about the PR content
- Never create a PR against main/master from main/master
- The PR body must contain all `PR_BLOCK:*:BEGIN/END` boundary markers — downstream updates depend on them
