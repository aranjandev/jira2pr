# jira2pr

`jira2pr` is a **multi-agent framework** for AI-assisted feature development: read a JIRA ticket, plan, implement, review, and submit a PR. It's lightweight, transparent, and designed for developer supervision at every step. Architecture details are in [`docs/platform-strategy.md`](docs/platform-strategy.md).

## Motivation

This framework is for two use cases:

1. **Start a new project:** You have a feature idea and want AI agents to help build it, organized with JIRA tracking and standard git workflows.
2. **Enhance an existing repo:** You've inherited a codebase and want to equip it so agents can add features while maintaining the same discipline.

## What It Is and Is Not

**It is:**
- A simple, transparent workflow framework for AI-assisted development
- Designed for human supervision and intervention at every step
- Platform-agnostic and built for any codebase: the same canonical workflow runs on GitHub Copilot or on the Python runtime (LiteLLM + [Aider](https://aider.chat))

**It is not:**
- A substitute for heavy orchestration frameworks (like [LangChain/LangGraph](https://www.langchain.com/blog/deep-agents-vs-langchain-vs-langgraph) or [CrewAI](https://docs.crewai.com/v1.15.20/en/introduction))
- A replacement for cloud-based agents (like [Copilot Cloud](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent))
- A standalone prompt bundle: the runtime platform needs the installed `jira2pr` package to execute workflows

## How jira2pr Works

`jira2pr` uses a **canonical definitions** model: agents, workflows, artifact schemas, and capabilities are defined once in `canonical/` in a platform-agnostic format. The **compiler** (`jira2pr init`) reads these definitions, validates every cross-reference (worker slugs, transition targets, success-criteria keys, capability bindings, model tiers), and projects them into two layers:

1. A **platform-neutral core** (`.jira2pr/`) — workflow state machines, artifact schemas, capability bindings, and resolved model config. Identical regardless of which platform is running it.
2. A **platform-specific UX shell** — `.github/` for Copilot (agent files, slash-command prompts, instructions), or `AGENTS.md` and Aider config files for the runtime platform.

For Copilot, an `orchestrator` agent interprets the workflow definition and invokes worker and `supervisor` sub-agents. For the runtime platform, the installed `jira2pr` package supplies a Python workflow engine (`engine/runtime/workflow/`). LiteLLM runs artifact and supervisor workers, and `aider` performs only repository edits and test/lint repair. See [`docs/platform-strategy.md`](docs/platform-strategy.md) for the full design.

Re-running `jira2pr init` after a canonical change regenerates everything and automatically prunes files from a previous generation that are no longer emitted — it never touches runtime data (workflow state, artifacts) since the compiler never wrote those in the first place. See [`engine/compiler/ASSEMBLER_SAFEGUARDS.md`](engine/compiler/ASSEMBLER_SAFEGUARDS.md).

## Repository Layout

| Folder | Contents | You run commands from here for... |
|--------|----------|-------------------------------------|
| `canonical/` | Platform-agnostic source of truth (agents, workflows, artifacts, capabilities) | Nothing — it's data, edited directly, read by the compiler |
| `engine/` | The `jira2pr` Python package: compiler (`engine/compiler/`), runtime engine (`engine/runtime/`), CLI source (`engine/jira2pr/`), tests (`engine/tests/`), and `engine/pyproject.toml` | `pip install`/`uv tool install` (from source), `pytest` |
| `docs/` | Architecture strategy ([`platform-strategy.md`](docs/platform-strategy.md)) and design notes | Nothing — reference reading only |

Once `jira2pr` is installed, its own commands (`init`, `check`, `run`, `resume`, `status`, `list`) can be run from **any directory** — they don't care about your current working directory, only `--target-dir`.

## Available Platforms

| Platform | Status |
|----------|--------|
| **Copilot** (VS Code + GitHub Copilot) | Supported — `jira2pr init --platform copilot` |
| **Runtime** (LiteLLM + [Aider](https://aider.chat) for repo edits) | Supported — `jira2pr init --platform runtime`, driven by the built-in `jira2pr run`/`resume` workflow engine |
| OpenCode | Not currently supported — predates the current canonical DSL. Source kept at `engine/compiler/assembler/platforms/_opencode_quarantined.py` for reference. |

Platform details (execution flow, capabilities, and the Copilot and runtime shells) are in [Platform Support](docs/platform-strategy.md#platform-support).

## Getting Started

### Install jira2pr

From a published release — run from **anywhere**:

```bash
uv tool install jira2pr   # or: pip install jira2pr
```

From a source checkout of this repo — run from **`engine/`** (that's where `pyproject.toml` lives):

```bash
cd engine
pip install -e .
# or: uv pip install -e .
```

This installs the `jira2pr` console script plus the `assembler` and `runtime`
packages into your active environment (a virtualenv is recommended, e.g.
`python3 -m venv engine/.venv && source engine/.venv/bin/activate` before the
`pip install -e .` above).

For common source-checkout commands without installing the package, use the
root `Makefile`:

```bash
make help
make init PLATFORM=copilot TARGET_DIR=./my-project
make check PLATFORM=copilot TARGET_DIR=./my-project
make status TICKET=PROJ-123 TARGET_DIR=./my-project
```

The complete CLI can also be invoked directly. The `PYTHONPATH` entries expose
the source packages that would otherwise be installed:

```bash
PYTHONPATH="$PWD/engine/compiler:$PWD/engine" \
python3 engine/jira2pr/cli.py --help
```

### Generate the setup for your platform

Run from **any directory** (this uses the installed `jira2pr` console script, not the source checkout):

```bash
jira2pr init --platform copilot --target-dir <your-project-root>
# or
jira2pr init --platform runtime --target-dir <your-project-root>
```

This writes `.jira2pr/` (platform-neutral core) plus either `.github/` (Copilot) or `AGENTS.md`, `.aider.conf.yml`, and `.aiderignore` (runtime) into your project.

Verify an existing setup is up to date (useful in CI), again from **any directory**:

```bash
jira2pr check --platform copilot --target-dir <your-project-root>
```

Then:
1. Follow the README written into your project (`.github/README.md` or `.jira2pr/README.md`) to set environment variables and customize your project.
2. Fill in all `<!-- CUSTOMIZE: ... -->` markers with your project-specific details.
3. For Copilot, use the slash commands (`/feature`, `/resume`, `/status`) in your AI chat. For the runtime platform, use `jira2pr run feature <TICKET>` / `jira2pr resume <TICKET>` / `jira2pr status <TICKET>` (also from any directory — `--target-dir` defaults to `.`, so run them from inside `<your-project-root>`).

### Set required credentials in .env

The agents read JIRA tickets and create PRs through the JIRA and Bitbucket/GitHub APIs. Copy `.env.example` to `<project-root>/.env` and set:

- `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`
- `GITHUB_TOKEN` (or `BITBUCKET_TOKEN` + `BITBUCKET_USERNAME`)
- Model-provider credentials for the models in `platform-extras` (runtime platform)

### Update repo specific agentic instructions

Agentic frameworks need a markdown file with the instructions AI agents follow on this repo. The file location depends on the platform:
- GitHub Copilot: `<project-root>/.github/copilot-instructions.md`
- Runtime platform (Aider): `<project-root>/AGENTS.md`

After you assembled the setup, a template instruction file is generated in the appropriate location. You need to update that file with repo specific details. The recommended way to populate this is to:
1. Use your existing agent (e.g., GitHub Copilot) to populate the template. Ask the agent to populate the repo specific details (for repos with existing contents) or populate it with best practices for the type of project you are starting.
1. Review and refine the agent generated instructions file.

### Creating a JIRA Ticket

Before starting a workflow, create a structured JIRA ticket. Use this template to ensure agents can extract requirements effectively:

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
- Plan approval required: <Yes/No> # Yes -> agent asks for permission to proceed after presenting the plan. No -> Agent proceeds to implementation after planning.
```

## How It Works

**Workflow states (feature):** `jira-ingest` → `plan` → `implement` ⇄ `run-tests` → `review` ⇄ `implement` → `submit` → `done` (or `human-review` on escalation). Execution flow and the judging rules for each state are in [`docs/platform-strategy.md`](docs/platform-strategy.md#execution-flow-runtime-platform).

**State tracking:** Workflow context is stored in a git-trackable state file (`.jira2pr/state/<TICKET-KEY>.yaml`). Only the runtime/orchestrator writes it; workers read it. Resume at any time with `/resume` (Copilot) or `jira2pr resume <TICKET>` (runtime); no work is lost.

**Bounded retries:** Each state has a `max_attempts` budget, and the implement ⇄ run-tests ⇄ review loop shares an `implement-cycle` budget. Exhausting a budget escalates to `human-review` instead of looping forever.

**Built-in QA:** `run-tests` judges the code with deterministic test and lint evidence. `review` judges it with the reviewer's `review-verdict` block: `approve`, `changes_requested` (sent back to `implement`), or `escalate`.

## Development

Working on `jira2pr` itself (not generating output for a target project)? Everything below runs from **`engine/`**:

```bash
cd engine
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pytest tests/ -q
```

`tests/` loads `canonical/` from the repo root automatically (see `engine/tests/conftest.py`). Common targets run from the repo root: `make test` and `make lint`.

## Important Notes

- **Runtime dependencies:** `jira2pr` depends on PyYAML, `aider`, `litellm`, `mcp`, and tree-sitter (see `engine/pyproject.toml`). The runtime platform uses all of them.
- **Generated output is disposable.** All canonical definitions live in `canonical/`; generated output (`.github/`, `.jira2pr/`, `AGENTS.md`) can be deleted and regenerated anytime with `jira2pr init`.
- **Edit only in `canonical/`.** Never edit generated output directly — always edit source files and re-run `jira2pr init`.
- **Built for transparency.** All workflow state is human-readable, git-trackable, and interruptible. You can inspect or modify any file at any time.
