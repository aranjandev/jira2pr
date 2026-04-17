# AI Coder Helpers — VSCode + Copilot Setup

A template for setting up VS Code Copilot agents that can perform end-to-end feature development: read a JIRA ticket, plan, implement, review, and submit a Pull Request.

## How It Works

```
User runs /feature PROJ-123
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
 [Plan &      │  2. Create branch, plan implementation,
  Implement]  │     write code, run tests
              │
    ┌─────────┘
    ▼
┌────────┐
│Reviewer│       3. Analyze changes for risks & quality
│        │          (Tier-3: Claude Opus)
└────┬───┘
     │
     ▼
┌────────┐
│  PR    │       4. Commit, push, create Pull Request
│ Author │          (Tier-1: Claude Haiku)
└────────┘
```

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
./.github/scripts/apply_model_tiers.sh
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
- **PR Author** — just commit, push, and create a PR

## Directory Structure

```
.github/
├── copilot-instructions.md          # Project-wide AI instructions
├── model-tiers.json                 # Tier → model mapping
├── scripts/
│   └── apply_model_tiers.sh         # Patches agent model fields
├── agents/
│   ├── orchestrator.agent.md        # Tier-2 — end-to-end workflow
│   ├── jira-reader.agent.md         # Tier-0 — ticket parsing
│   ├── reviewer.agent.md            # Tier-3 — code review (read-only)
│   └── pr-author.agent.md          # Tier-1 — commit & PR creation
├── skills/
│   ├── read-jira-ticket/            # JIRA API integration
│   ├── git-operations/              # Branch, commit, push
│   ├── create-pull-request/         # GitHub PR creation
│   ├── summarize-changes/           # Diff analysis
│   └── identify-risks/              # Risk assessment
├── prompts/
│   ├── feature.prompt.md            # /feature slash command
│   ├── bugfix.prompt.md             # /bugfix slash command
│   └── review.prompt.md             # /review slash command
└── instructions/
    ├── coding-standards.instructions.md
    └── commit-conventions.instructions.md
```

## Model Tiers

Agents are assigned model tiers based on task complexity:

| Tier | Default Model | Used By | Rationale |
|------|--------------|---------|-----------|
| 0 | GPT-4o mini | JIRA Reader | Simple extraction & formatting |
| 1 | Claude Haiku 3.5 | PR Author | Templated, formulaic output |
| 2 | Claude Sonnet 4 | Orchestrator | Planning & code generation |
| 3 | Claude Opus 4 | Reviewer | Deep analysis & reasoning |

To change models, edit `model-tiers.json` and run `apply_model_tiers.sh`. Agent files contain `<!-- tier: N -->` comments that the script uses to determine which model to assign.

## Customization Guide

| What | Where | When |
|------|-------|------|
| Project conventions | `copilot-instructions.md` | Always customize first |
| Language-specific rules | `coding-standards.instructions.md` | Adjust `applyTo` glob + rules |
| Commit format | `commit-conventions.instructions.md` | If you use a different convention |
| Model choices | `model-tiers.json` + `apply_model_tiers.sh` | To swap models or save costs |
| JIRA field mapping | `skills/read-jira-ticket/scripts/fetch_jira.sh` | If custom fields differ |
| Branch naming | `skills/git-operations/scripts/git_helper.sh` | If you use different conventions |
| PR template | `skills/create-pull-request/SKILL.md` | To match your team's PR format |

## License

Apache License 2.0 — see [LICENSE](../LICENSE).
