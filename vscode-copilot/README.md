# jira2pr — VS Code + Copilot Setup

A template for setting up VS Code Copilot agents that can perform end-to-end feature development: read a JIRA ticket, plan, implement, self-review, and submit a Pull Request.

## How It Works

```
User runs /feature PROJ-123  (or /feature <PR-URL> to resume)
        │
        ▼
┌─────────────────┐
│  Orchestrator    │ (Tier-2: Claude Sonnet)
│  agent           │
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         │
┌────────┐    │
│ JIRA   │    │  Phase 1: Read ticket → structured requirements
│ Reader │    │           (Tier-0: GPT-4o mini)
└────┬───┘    │
     │        │
     ▼        │
┌────────┐    │  Phase 2: (optional) Research packages/APIs
│Research│    │           (Tier-1: Claude Haiku)
│  er    │    │
└────┬───┘    │
     │        │
     ▼        │
 [Plan +      │           Create branch + draft PR as live
  Branch +    │           state document (Status: Implementing)
  Draft PR]   │           Present plan; await approval if complex
              │
    ┌─────────┘
    ▼
 [Implement]  │  Phase 3: Implement changes, run tests & lint
              │           PR updated (Status: Reviewing)
              │
    ┌─────────┘
    ▼
┌────────┐
│Reviewer│       Phase 4: Analyze changes for risks & quality
│        │               (Tier-3: Claude Opus)
└────┬───┘               PR updated (Status: Submitting)
     │
     ▼
┌────────┐
│  PR    │       Phase 5: Commit, push, mark PR ready for review
│ Author │               (Tier-1: Claude Haiku)
└────────┘               PR finalized (Status: Ready)
```

> **Resume support:** Pass an existing PR URL or number (`/feature #42`) to resume an interrupted workflow. The Orchestrator reads the PR body, restores the task list, and continues from the last recorded phase using the shared resume procedure in `_resume.md`.

### PR as Live State Document

A key feature of this workflow is that the **PR body is a live state document**, not just a description. A draft PR is created at the end of Phase 2 (Planning), before any code is written. The PR body is divided into machine-writable sections bounded by `<!-- PR_BLOCK:*:BEGIN/END -->` markers that the Orchestrator updates at each phase transition.

> **Schema & template** — see `.github/instructions/pr-schema.instructions.md` for block definitions, mutability rules, and idempotency rules; `.github/instructions/pr-template.instructions.md` for the canonical PR body template.

| Section | Mutability | Purpose |
|---------|------------|--------|
| Status | Mutable | Current phase, draft flag, last updated timestamp |
| Links | Mutable | JIRA ticket URL, branch name |
| Intent | Immutable | Problem, desired outcome, non-goals, constraints |
| Plan | Mutable | Task list (with stable IDs T1, T2, ...), test strategy, risks |
| Phase Log | Append-only | Audit trail of every phase transition |
| Review Summary | Mutable | Risk level, findings, resolutions from self-review |
| Decisions Log | Append-only | Record of scope changes, plan mutations, review overrides |
| Open Questions | Mutable | Unresolved items and intentionally deferred work |
| Agent Notes | Mutable | Breadcrumbs for downstream agents or human reviewers |

The valid phase values are: `Planning` · `Implementing` · `Reviewing` · `Submitting` · `Ready`

## Prerequisites

- **VS Code** with GitHub Copilot extension
- **Python 3** — all scripts use the standard library only (no `pip install` required)
- **git** — for branch, commit, and push operations
- **GitHub token** — a [fine-grained PAT](https://github.com/settings/tokens?type=beta) with *Pull requests: Read & Write* on your repo (place in `.env` as `GITHUB_TOKEN`)
  - Alternatively, authenticate via `gh auth login` if you have the GitHub CLI installed
- **Bitbucket token** (optional) — if your repo is on Bitbucket, set `BITBUCKET_TOKEN` and `BITBUCKET_USERNAME` in `.env` instead

## Setup

### 1. Copy into your project

Copy the `.github/` directory and `.env.example` from `vscode-copilot/` into your project root:

```bash
cp -r vscode-copilot/.github /path/to/your/project/
cp vscode-copilot/.env.example /path/to/your/project/.env
```

### 2. Set environment variables

Edit the `.env` file you just copied and fill in your values:

```bash
# JIRA
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=you@yourcompany.com
JIRA_API_TOKEN=your-jira-api-token

# GitHub (primary)
GITHUB_TOKEN=your-github-token

# Bitbucket (if applicable — use instead of GitHub token)
# BITBUCKET_TOKEN=your-bitbucket-token
# BITBUCKET_USERNAME=your-bitbucket-username
```

Then add `.env` to your project's `.gitignore`:

```bash
echo '.env' >> .gitignore
```

> **Get a JIRA API token:** [Atlassian Account → Security → API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
>
> **Get a GitHub token:** Use a [fine-grained PAT](https://github.com/settings/tokens?type=beta) with *Pull requests: Read & Write* on your repo, or run `gh auth login` to use the GitHub CLI as an alternative.

### 3. Customize project instructions

Edit `.github/copilot-instructions.md` — fill in all `<!-- CUSTOMIZE -->` sections with your project's:
- Language and framework
- Architecture overview
- Build, test, and lint commands
- Coding conventions

### 4. Adjust model tiers (optional)

Edit `.github/model-tiers.json` to change which models are assigned to each tier:

```json
{
  "tiers": {
    "0": { "model": "GPT-4o mini (copilot)", "description": "Cheapest" },
    "1": { "model": "Claude Haiku 3.5 (copilot)", "description": "Light" },
    "2": { "model": "Claude Sonnet 4 (copilot)", "description": "Strong" },
    "3": { "model": "Claude Opus 4 (copilot)", "description": "Highest" }
  }
}
```

Then apply:
```bash
python3 ./.github/scripts/apply_model_tiers.py
```

## Usage

### JIRA ticket creation

Before running `/feature <TICKET_KEY>`, create the JIRA ticket with a clear, structured description. The following template works well with the `read-jira-ticket` skill and improves requirement extraction quality.

Use this as your JIRA issue description template:

```markdown
## Description
<What problem are we solving? Include user/business context and current pain point.>

## Requirements
- <Functional requirement 1>
- <Functional requirement 2>
- <Any important non-functional requirement: performance, security, compatibility>

## Acceptance Criteria
- Given <context>, when <action>, then <expected result>
- Given <context>, when <action>, then <expected result>

## Subtasks
- <Subtask 1>
- <Subtask 2>

## Related Issues
- <Blocks/Depends on/Relates to>: <PROJ-456>

## Implementation Hints
- <Known technical constraints>
- <Relevant service/component/file paths>
- <API contracts, payload examples, or links>

## Additional Notes
- Plan approval required: <Yes/No>
```

Recommended issue fields:
- **Summary:** concise outcome-oriented title (for example: "Add retry handling for payment webhook timeouts")
- **Issue Type:** Story or Bug
- **Priority:** set explicitly
- **Labels:** include workflow labels your team uses (for example, `plan-approval-required` when applicable)


### Feature development
In VS Code Copilot Chat, type:
```
/feature PROJ-123
```
or
```
/feature https://yourcompany.atlassian.net/browse/PROJ-123
```

### Bug fix
```
/bugfix PROJ-456
```

### Code review (current changes)
```
/review
```

### Use agents directly
Select an agent from the Copilot agent picker:
- **Orchestrator** — full end-to-end workflow
- **JIRA Reader** — just read and interpret a ticket
- **Reviewer** — just review current changes
- **PR Author** — just commit, push, and finalize a PR

### Resume an interrupted session
If the Orchestrator was interrupted (crash, session timeout, or manual stop), pass the existing PR link or number instead of a JIRA key:
```
/feature https://github.com/yourorg/yourrepo/pull/42
```
or
```
/feature #42
```
The Orchestrator follows the shared resume procedure in `_resume.md`:
1. Fetch the PR body and validate all `PR_BLOCK:*:BEGIN/END` boundary markers
2. Parse current phase, branch name, and task list from the PR body
3. Append a resume entry to the Phase Log (idempotent — no duplicate entries)
4. Route to the correct workflow step for the current phase and continue

No work is lost — the PR body is the single source of truth for the workflow state.

## Directory Structure

```
.github/
├── copilot-instructions.md          # Project-wide AI instructions
├── model-tiers.json                 # Tier → model mapping
├── scripts/
│   └── apply_model_tiers.py         # Patches agent model fields
├── agent-workflows/
│   ├── _resume.md                   # Shared resume-from-PR procedure
│   ├── feature.md                   # End-to-end feature workflow definition
│   └── bugfix.md                    # End-to-end bugfix workflow definition
├── agents/
│   ├── orchestrator.agent.md        # Tier-2 — end-to-end workflow
│   ├── jira-reader.agent.md         # Tier-0 — ticket parsing
│   ├── researcher.agent.md          # Tier-1 — research & codebase exploration
│   ├── reviewer.agent.md            # Tier-3 — code review (read-only)
│   └── pr-author.agent.md           # Tier-1 — commit & PR finalization
├── skills/
│   ├── read-jira-ticket/            # JIRA API integration
│   ├── git-operations/              # Branch, commit, push
│   ├── create-pull-request/         # Draft PR creation
│   ├── update-pull-request/         # PR state transitions
│   ├── summarize-changes/           # Diff analysis
│   └── identify-risks/              # Risk assessment
├── prompts/
│   ├── feature.prompt.md            # /feature slash command
│   ├── bugfix.prompt.md             # /bugfix slash command
│   └── review.prompt.md             # /review slash command
└── instructions/
    ├── commit-conventions.instructions.md
    ├── pr-schema.instructions.md        # PR block definitions, mutability & idempotency rules
    └── pr-template.instructions.md      # Canonical PR body template (copy-paste for PR creation)
```

## Model Tiers

Agents are assigned model tiers based on task complexity:

| Tier | Default Model | Used By | Rationale |
|------|--------------|---------|-----------|
| 0 | GPT-4o mini | JIRA Reader | Simple extraction & formatting |
| 1 | Claude Haiku 3.5 | Researcher, PR Author | Light reasoning, templated output |
| 2 | Claude Sonnet 4 | Orchestrator | Planning & code generation |
| 3 | Claude Opus 4 | Reviewer | Deep analysis & reasoning |

To change models, edit `model-tiers.json` and run `apply_model_tiers.py`. Agent files contain `<!-- tier: N -->` comments that the script uses to determine which model to assign.

## Customization Guide

| What | Where | When |
|------|-------|------|
| Project conventions | `copilot-instructions.md` | Always customize first |
| Commit format | `commit-conventions.instructions.md` | If you use a different convention |
| PR body template | `pr-template.instructions.md` | To match your team's PR format |
| Model choices | `model-tiers.json` + `apply_model_tiers.py` | To swap models or save costs |
| JIRA field mapping | `skills/read-jira-ticket/scripts/fetch_jira.py` | If custom fields differ |
| Branch naming | `skills/git-operations/scripts/git_helper.py` | If you use different conventions |
| PR creation logic | `skills/create-pull-request/scripts/pr_helper.py` | For Bitbucket or custom API endpoints |

## License

Apache License 2.0 — see [LICENSE](../LICENSE).
