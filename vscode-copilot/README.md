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
│ JIRA   │    │  1. Read ticket → structured requirements
│ Reader │    │     (Tier-0: GPT-4o mini)
└────┬───┘    │
     │        │
     ▼        │
 [Plan &      │  2. Approve plan → draft PR created as live
  Draft PR]   │     state document (Status: Planning)
              │
    ┌─────────┘
    ▼
 [Branch &    │  3. Create branch → PR updated
  Implement]  │     (Status: Implementing)
              │
    ┌─────────┘
    ▼
┌────────┐
│Reviewer│       4. Analyze changes for risks & quality
│        │          (Tier-3: Claude Opus)
└────┬───┘           PR updated (Status: Reviewing)
     │
     ▼
┌────────┐
│  PR    │       5. Commit, push, mark PR ready for review
│ Author │          (Tier-1: Claude Haiku)
└────────┘           PR finalized (Status: Ready)
```

### PR as Live State Document

A key feature of this workflow is that the **PR body is a live state document**, not just a description. After the plan is approved, a draft PR is created immediately. The PR body is divided into machine-writable sections (bounded by `<!-- PR_BLOCK:*:BEGIN/END -->` markers) that the Orchestrator updates at each phase transition:

> **Key sections** — see `.github/instructions/pr-description.instructions.md` for the full schema.

| Section | Mutability | Purpose |
|---------|------------|--------|
| Status | Mutable | Current phase, draft flag, last updated timestamp |
| Links | Mutable | JIRA ticket URL, branch name |
| Intent | Immutable | Problem, desired outcome, non-goals, constraints |
| Plan | Mutable | Task list (with stable IDs T1, T2, ...), test strategy, risks |
| Phase Log | Append-only | Audit trail of every phase transition |
| Review Summary | Mutable | Risk level, findings, resolutions from self-review |

## Prerequisites

- **VS Code** with GitHub Copilot extension
- **GitHub CLI** (`gh`) — [Install](https://cli.github.com)
  ```bash
  gh auth login
  ```
- **curl** and **jq** — for JIRA API calls and JSON processing
  ```bash
  brew install jq  # macOS
  ```

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
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=you@yourcompany.com
JIRA_API_TOKEN=your-jira-api-token
GITHUB_TOKEN=your-github-token
```

Then add `.env` to your project's `.gitignore`:

```bash
echo '.env' >> .gitignore
```

> **Get a JIRA API token:** [Atlassian Account → Security → API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
>
> **Get a GitHub token:** Use a [fine-grained PAT](https://github.com/settings/tokens?type=beta) with *Pull requests: Read & Write* on your repo, or run `gh auth login` to use the GitHub CLI instead.

### 3. Customize project instructions

Edit `.github/copilot-instructions.md` — fill in all `<!-- CUSTOMIZE -->` sections with your project's:
- Language and framework
- Architecture overview
- Build, test, and lint commands
- Coding conventions

### 4. Customize coding standards

Edit `.github/instructions/coding-standards.instructions.md`:
- Adjust the `applyTo` glob to match your project's languages
- Fill in naming conventions, patterns, and anti-patterns

### 5. Adjust model tiers (optional)

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
The Orchestrator will:
1. Fetch the PR body and determine the current phase from the Status block
2. Restore the task list from the Plan block
3. Record a resume event in the Phase Log (idempotent — no duplicate entries)
4. Continue from exactly where work stopped

No work is lost — the PR body is the single source of truth for the workflow state.

## Directory Structure

```
.github/
├── copilot-instructions.md          # Project-wide AI instructions
├── model-tiers.json                 # Tier → model mapping
├── scripts/
│   └── apply_model_tiers.py         # Patches agent model fields
├── agent-workflows/
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
    ├── coding-standards.instructions.md
    ├── commit-conventions.instructions.md
    └── pr-description.instructions.md  # Canonical PR state document schema
```

## Model Tiers

Agents are assigned model tiers based on task complexity:

| Tier | Default Model | Used By | Rationale |
|------|--------------|---------|-----------|
| 0 | GPT-4o mini | JIRA Reader | Simple extraction & formatting |
| 1 | Claude Haiku 3.5 | PR Author | Templated, formulaic output |
| 2 | Claude Sonnet 4 | Orchestrator | Planning & code generation |
| 3 | Claude Opus 4 | Reviewer | Deep analysis & reasoning |

To change models, edit `model-tiers.json` and run `apply_model_tiers.py`. Agent files contain `<!-- tier: N -->` comments that the script uses to determine which model to assign.

## Customization Guide

| What | Where | When |
|------|-------|------|
| Project conventions | `copilot-instructions.md` | Always customize first |
| Language-specific rules | `coding-standards.instructions.md` | Adjust `applyTo` glob + rules |
| Commit format | `commit-conventions.instructions.md` | If you use a different convention |
| Model choices | `model-tiers.json` + `apply_model_tiers.py` | To swap models or save costs |
| JIRA field mapping | `skills/read-jira-ticket/scripts/fetch_jira.py` | If custom fields differ |
| Branch naming | `skills/git-operations/scripts/git_helper.py` | If you use different conventions |
| PR template | `skills/create-pull-request/SKILL.md` | To match your team's PR format |

## License

Apache License 2.0 — see [LICENSE](../LICENSE).
