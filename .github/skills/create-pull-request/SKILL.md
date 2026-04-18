---
name: create-pull-request
description: 'Creates a draft Pull Request using the canonical PR state schema from pr-description.instructions.md. Populates all initial blocks (Status, Links, Intent, Plan, Phase Log) and returns PR URL + PR number. Use when plan is approved and the orchestrator needs to create the initial draft PR.'
argument-hint: 'PR details (title, JIRA key, ticket data for Intent/Plan)'
---

# Create Pull Request

Creates an initial **draft** Pull Request using the canonical PR state document schema. The PR body is a live state document that will be updated at each workflow phase transition.

## When to Use

- Plan phase is complete and approved by the user
- Orchestrator is ready to record the plan as a draft PR
- **NOT** for final submission — use the `update-pull-request` skill with `--undraft` for that

## Primary Caller

**orchestrator** — this skill is called directly by the orchestrator during the Plan phase, not by the pr-author agent.

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

2. **Read the PR body template** from `.github/instructions/pr-description.instructions.md` — use the section below the `# PR Body Template` heading as the skeleton.

3. **Populate the template blocks:**

   | Block | Content |
   |-------|---------|
   | `PR_BLOCK:STATUS` | Phase: `Planning`, Draft: `true`, Last Updated: now (ISO 8601), Updated By: `orchestrator` |
   | `PR_BLOCK:LINKS` | JIRA: ticket URL, Branch: current branch name, Design/Docs: from ticket or `N/A` |
   | `PR_BLOCK:INTENT` | Problem, Desired Outcome, Non-Goals, Constraints — from JIRA ticket requirements |
   | `PR_BLOCK:PLAN` | Tasks (with stable IDs T1, T2, ...), Test Strategy, Risks & Mitigations — from approved plan |
   | `PR_BLOCK:PHASE_LOG` | First entry: current timestamp, `Planning`, `orchestrator`, "Draft PR created from approved plan" |
   | `PR_BLOCK:REVIEW_SUMMARY` | Leave default placeholder (`Risk Level: —`) |
   | `PR_BLOCK:DECISIONS_LOG` | Leave empty (commented template only) |
   | `PR_BLOCK:OPEN_QUESTIONS` | Populate from ticket if any, otherwise leave empty |
   | `PR_BLOCK:AGENT_NOTES` | Leave empty |

   Replace `<TICKET_KEY>` in the title heading with the actual ticket key and a short descriptive title.

4. **Generate the PR title:**
   - Format: `<type>(<scope>): <short description> [<TICKET_KEY>]`
   - Example: `feat(auth): add JWT token validation [PROJ-123]`
   - The type should match the branch prefix (`feat/` → `feat`, `fix/` → `fix`)

5. **Write body to a temp file and create the PR:**
   ```bash
   cat > /tmp/pr_body.md << 'BODY'
   <populated PR body>
   BODY

   python3 ./.github/skills/create-pull-request/scripts/pr_helper.py create \
     --title "<PR_TITLE>" \
     --body-file /tmp/pr_body.md \
     --draft \
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
- Use `--dry-run` first if uncertain about the PR content
- Never create a PR against main/master from main/master
- The PR body must contain all `PR_BLOCK:*:BEGIN/END` boundary markers — downstream updates depend on them
