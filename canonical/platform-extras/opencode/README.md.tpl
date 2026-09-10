# jira2pr — Agent Setup Guide

> This file lives at `{{AGENTS_DIR}}/README.md` and documents the agent framework
> installed in your project. Keep it here so any developer (or agent) can understand
> what's available and how to use it.

## What Was Installed

The `{{AGENTS_DIR}}/` directory contains a multi-agent workflow system for
end-to-end feature development: read a JIRA ticket → plan → implement →
self-review → submit a Pull Request. All agent files are generated from
[jira2pr](https://github.com/abhishekranjan/jira2pr) canonical definitions — do
not edit them by hand. Re-run the assembler to pick up upstream changes.

## Prerequisites

- **OpenCode CLI/TUI installed**
- **Python 3** (standard library only — no `pip install` required)
- **git** configured with push access to your repo
- **GitHub token** — a [fine-grained PAT](https://github.com/settings/tokens?type=beta)
  with *Pull requests: Read & Write* (place in `.env` as `GITHUB_TOKEN`), or
  authenticate via `gh auth login`
- **Bitbucket token** (optional) — set `BITBUCKET_TOKEN` and `BITBUCKET_USERNAME`
  in `.env` if your repo is on Bitbucket

## Setup

### 1. Set environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```bash
# JIRA
JIRA_BASE_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=you@yourcompany.com
JIRA_API_TOKEN=your-jira-api-token

# GitHub
GITHUB_TOKEN=your-github-token

# Bitbucket (if applicable — use instead of GitHub token)
# BITBUCKET_TOKEN=your-bitbucket-token
# BITBUCKET_USERNAME=your-bitbucket-username
```

Add `.env` to `.gitignore`:

```bash
echo '.env' >> .gitignore
```

> **Get a JIRA API token:** [Atlassian Account → Security → API Tokens](https://id.atlassian.com/manage-profile/security/api-tokens)

### 2. Customize project instructions

Edit `AGENTS.md` (at the project root) — fill in all `<!-- CUSTOMIZE -->` sections:

- Language and framework
- Architecture overview
- Build, test, and lint commands
- Coding conventions

### 3. Adjust model tiers (optional)

OpenCode bakes model assignments directly into generated agent frontmatter and
`opencode.json` at generation time — there is no runtime stamping script (unlike
the Copilot setup's `apply_model_tiers.py`). To change which models are assigned
to each tier, edit `canonical/model-tiers.yaml` upstream in the jira2pr repo and
re-run the assembler:

```bash
python3 scripts/assemble.py --target-dir <target-dir> --platform opencode
```

## JIRA Ticket Template

Before kicking off a workflow, create the JIRA ticket with a structured description.
The template below works well with the `read-jira-ticket` skill:

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
- **Summary:** concise outcome-oriented title (e.g. "Add retry handling for payment webhook timeouts")
- **Issue Type:** Story or Bug
- **Priority:** set explicitly
- **Labels:** include workflow labels your team uses (e.g. `plan-approval-required`)

## Usage

### Feature development

```
/feature PROJ-123
```
or pass the full ticket URL:
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

### Resume an interrupted session

If the Orchestrator was interrupted (crash, timeout, or manual stop), pass the
existing PR link or number instead of a JIRA key:

```
/feature https://github.com/yourorg/yourrepo/pull/42
```
or
```
/feature #42
```

The Orchestrator reads the PR body and state file, validates all block markers,
restores the task list, and continues from the last recorded phase. No work is lost.

## Agents

| Agent | Role | Model |
|-------|------|-------|
| **Orchestrator** | End-to-end workflow driver | Tier 2 |
| **JIRA Reader** | Fetches and parses a JIRA ticket | Tier 0 |
| **Researcher** | Research packages, APIs, algorithms | Tier 1 |
| **Reviewer** | Thorough code review and risk analysis | Tier 3 |
| **PR Author** | Commits, pushes, and finalizes the PR | Tier 1 |

See `opencode.json` (project root) for concrete model assignments.

## Known Limitations

Some generated skill instructions and the `state/SCHEMA.md` / `artifacts/SCHEMA.md`
reference files still contain literal `.github/...` path references inherited
from the shared canonical source (e.g. `python3 ./.github/skills/git-operations/scripts/git_helper.py push`
instead of `.opencode/skill/git-operations/scripts/git_helper.py push`). This is
a known, tracked limitation — not a bug introduced in this generation run — and
affects the bodies of `skill/*/SKILL.md`, `state/SCHEMA.md`, `artifacts/SCHEMA.md`,
and `agent/orchestrator.md`. A full fix requires templating those canonical
sources with a path placeholder, which is tracked separately and out of scope
for now. Until then, mentally substitute `.opencode/` for `.github/` when
following any file paths mentioned inside those generated skill/schema/agent
instruction bodies. This does **not** affect `AGENTS.md`, `opencode.json`, or
the generated `agent/`/`command/` files themselves — those are correctly
path-aware.

## Directory Structure

```
{{AGENTS_DIR}}/
├── README.md                        # This file
├── state/
│   ├── SCHEMA.md                    # State file schema reference
│   └── workflow-state.tpl.md        # Template used by manage-state skill
├── artifacts/
│   └── SCHEMA.md                    # Artifact registry schema reference
├── agent/
│   ├── orchestrator.md              # Tier 2 — end-to-end workflow driver
│   ├── jira-reader.md               # Tier 0 — ticket parsing
│   ├── researcher.md                # Tier 1 — research & exploration
│   ├── reviewer.md                  # Tier 3 — code review (read-only)
│   └── pr-author.md                 # Tier 1 — commit & PR finalization
├── skill/
│   ├── read-jira-ticket/            # JIRA API integration
│   ├── git-operations/              # Branch, commit, push
│   ├── create-pull-request/         # Draft PR creation
│   ├── update-pull-request/         # PR state transitions
│   ├── manage-state/                # Workflow state file management
│   ├── register-artifact/           # Artifact registry append
│   ├── summarize-changes/           # Diff analysis
│   └── identify-risks/              # Risk assessment
├── command/
│   ├── feature.md                   # /feature slash command
│   ├── bugfix.md                    # /bugfix slash command
│   └── review.md                    # /review slash command
└── instructions/
    ├── commit-conventions.md
    ├── pr-schema.md
    └── pr-template.md
```

Alongside `{{AGENTS_DIR}}/`, the assembler also generates:
- `AGENTS.md` (project root) — project-wide AI instructions (customize this)
- `opencode.json` (project root) — OpenCode config file (model, small_model, instructions, default_agent)

## Customization Guide

| What to change | Where | Notes |
|----------------|-------|-------|
| Project conventions | `AGENTS.md` | Always customize this first |
| Commit format | `instructions/commit-conventions.md` | If you use a different convention |
| PR body template | `instructions/pr-template.md` | To match your team's PR format |
| Model assignments | `canonical/model-tiers.yaml` (upstream) + re-run assembler | To swap models or optimize cost |
| JIRA field mapping | `skill/read-jira-ticket/scripts/fetch_jira.py` | If you use custom JIRA fields |
| Branch naming | `skill/git-operations/scripts/git_helper.py` | To match your branch conventions |
| PR creation logic | `skill/create-pull-request/scripts/pr_helper.py` | For Bitbucket or custom endpoints |
