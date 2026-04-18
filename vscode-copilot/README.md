# jira2pr Template for VS Code + GitHub Copilot

This folder contains a complete, copy-ready configuration for running an end-to-end JIRA-to-PR workflow in VS Code with Copilot agents.

The key design goal is durability: Pull Requests are used as a live workflow state document so work can resume after interruptions.

## Workflow Overview

```
/feature KAN-123
   -> Orchestrator
   -> JIRA Reader (requirements)
   -> Plan + draft PR state document
   -> Branch + implementation
   -> Reviewer (risk analysis)
   -> PR Author (commit/push/finalize)
```

### Resume Behavior (Core Capability)

The `/feature` prompt supports two entry modes:

- Fresh start: `/feature PROJ-123` or `/feature https://.../browse/PROJ-123`
- Resume run: `/feature <PR-URL-or-number>`

When resuming, the orchestrator:

1. Fetches PR body content.
2. Validates canonical `PR_BLOCK:*:BEGIN/END` markers.
3. Reads the current `Status` phase (`Planning`, `Implementing`, `Reviewing`, `Ready`).
4. Continues from the next workflow step.
5. Appends a resume event to `Phase Log` when appropriate.

This prevents lost progress across terminal crashes, model timeouts, or interrupted sessions.

## Prerequisites

- VS Code with GitHub Copilot Chat
- GitHub CLI (`gh`) authenticated for your repository
- `curl` and `jq`

```bash
gh auth login
brew install jq
```

## Setup

### 1. Copy Template Files

```bash
cp -r vscode-copilot/.github /path/to/your/project/
cp vscode-copilot/.env.example /path/to/your/project/.env
```

### 2. Configure Environment Variables

```bash
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=you@yourcompany.com
JIRA_API_TOKEN=your-jira-api-token
GITHUB_TOKEN=your-github-token
```

Add `.env` to `.gitignore`:

```bash
echo '.env' >> .gitignore
```

### 3. Customize Instructions

Update `.github/copilot-instructions.md` and replace all `<!-- CUSTOMIZE -->` sections with project-specific details:

- architecture
- coding conventions
- build, test, lint commands
- environment constraints

### 4. Customize Coding Standards

Update `.github/instructions/coding-standards.instructions.md`:

- adjust `applyTo` globs to match your languages
- define naming, testing, and error-handling conventions

### 5. Optional: Adjust Model Tiers

Edit `.github/model-tiers.json` and re-apply:

```bash
./.github/scripts/apply_model_tiers.sh
```

## Usage

### Feature Workflow

```text
/feature PROJ-123
```

or

```text
/feature https://yourcompany.atlassian.net/browse/PROJ-123
```

Resume an interrupted feature by PR:

```text
/feature https://github.com/owner/repo/pull/42
```

or

```text
/feature 42
```

### Bugfix Workflow

```text
/bugfix PROJ-456
```

### Review Current Changes

```text
/review
```

## Canonical Structure

```
.github/
├── copilot-instructions.md
├── model-tiers.json
├── scripts/
│   └── apply_model_tiers.sh
├── agents/
│   ├── orchestrator.agent.md
│   ├── jira-reader.agent.md
│   ├── reviewer.agent.md
│   ├── pr-author.agent.md
│   └── explorer.agent.md
├── skills/
│   ├── read-jira-ticket/
│   ├── git-operations/
│   ├── create-pull-request/
│   ├── update-pull-request/
│   ├── summarize-changes/
│   └── identify-risks/
├── prompts/
│   ├── feature.prompt.md
│   ├── bugfix.prompt.md
│   └── review.prompt.md
├── instructions/
│   ├── coding-standards.instructions.md
│   ├── commit-conventions.instructions.md
│   └── pr-description.instructions.md
└── workflows/
    ├── feature.md
    └── bugfix.md
```

## PR State Document Summary

The canonical PR body uses bounded blocks that support safe machine updates:

- `Status` and `Links`: mutable blocks replaced per phase
- `Intent`: immutable after plan approval (scope changes require a Decisions Log entry)
- `Phase Log` and `Decisions Log`: append-only history
- `Review Summary`: populated after self-review

Because updates are block-scoped and idempotent, retries and resume operations remain safe.

## Model Tiers (Default)

| Tier | Typical Agent | Purpose |
|------|---------------|---------|
| 0 | JIRA Reader | extraction and structuring |
| 1 | PR Author | commit/push/finalization |
| 2 | Orchestrator | planning and implementation |
| 3 | Reviewer | deep quality/risk analysis |

## License

Apache License 2.0. See [LICENSE](../LICENSE).
