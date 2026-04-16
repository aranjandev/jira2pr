---
name: create-pull-request
description: 'Creates a GitHub Pull Request with a structured description linking back to the JIRA ticket. Handles title formatting, body generation, labels, and draft mode. Use when ready to submit changes as a PR.'
argument-hint: 'PR details (title, JIRA key, draft flag)'
---

# Create Pull Request

Creates a well-structured GitHub PR that links to the JIRA ticket and clearly communicates what changed, why, and how.

## When to Use

- Changes are committed and pushed to a feature/bugfix branch
- Ready to submit work for review
- Asked to "create PR", "open pull request", "submit changes"

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth login`)
- Changes already committed and pushed to a remote branch
- On the feature/bugfix branch (not main/master)

## Procedure

1. **Verify readiness:**
   ```bash
   # Ensure all changes are committed
   git status
   # Ensure branch is pushed
   git log --oneline origin/<branch>..<branch> 2>/dev/null
   ```

2. **Generate the PR title:**
   - Format: `<type>(<scope>): <short description> [<TICKET_KEY>]`
   - Example: `feat(auth): add JWT token validation [PROJ-123]`
   - The title should match the primary commit's conventional commit prefix

3. **Generate the PR body** using this template:
   ```markdown
   ## What
   <!-- One-paragraph summary of the changes -->

   ## Why
   <!-- Link to JIRA ticket and explain the motivation -->
   JIRA: <JIRA_URL>

   ## How
   <!-- Technical approach — key decisions, patterns used, tradeoffs -->

   ## Testing
   <!-- How the changes were tested — commands run, scenarios covered -->

   ## Checklist
   - [ ] Tests pass locally
   - [ ] No new warnings or lint errors
   - [ ] Self-reviewed the diff
   - [ ] Acceptance criteria from ticket addressed
   ```

4. **Create the PR** using the script:
   ```bash
   ./.github/skills/create-pull-request/scripts/create_pr.sh \
     --title "<PR_TITLE>" \
     --body "<PR_BODY>" \
     --labels "<label1,label2>" \
     --draft
   ```
   Reference: [create_pr.sh](./scripts/create_pr.sh)

   Or write the body to a temp file for complex content:
   ```bash
   cat > /tmp/pr_body.md << 'BODY'
   <PR body content>
   BODY
   ./.github/skills/create-pull-request/scripts/create_pr.sh \
     --title "<PR_TITLE>" \
     --body-file /tmp/pr_body.md \
     --labels "<labels>"
   ```

5. **Label conventions:**
   | Label | When |
   |-------|------|
   | `feature` | New feature |
   | `bugfix` | Bug fix |
   | `refactor` | Code restructuring |
   | `dependencies` | Dependency updates |

6. **Use `--draft`** when:
   - Changes are not fully complete
   - Seeking early feedback
   - CI needs to pass first

7. **Output:** The script prints the PR URL. Report this URL back to the user.

## Important

- Always link the JIRA ticket in the PR body
- The PR body should be readable by someone who hasn't seen the ticket
- Include the ticket key in the PR title for automatic JIRA linking
- Use `--dry-run` first if uncertain about the PR content
- Never create a PR against main/master from main/master
