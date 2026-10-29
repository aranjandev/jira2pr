# Jira2PR Platform Architecture Strategy

## Overview

Jira2PR defines platform-independent software-development workflows and projects them into different agent execution environments.

**Purpose:** take a JIRA ticket through `jira-ingest → plan → implement ⇄ run-tests → review ⇄ implement → submit` and end with a
pull request, using AI agents under human supervision. Workflows, agents, artifact schemas, and capabilities are
written once in `canonical/`; the `jira2pr` CLI compiles them into a generated package for a target
repository and, on runtime-driven platforms, executes them. Two execution platforms are supported:
**GitHub Copilot** (agent-driven, `--platform copilot`) and **Aider** (runtime-driven, as the
repository-editing backend of `--platform runtime`). See [Platform Support](#platform-support) and
[Current Implementation Status and Known Gaps](#current-implementation-status-and-known-gaps).

**Contents:** [Architectural Layers](#architectural-layers) ·
[Agent Roles](#agent-roles) · [Compiler Layer](#compiler-layer) ·
[Generated Core Package](#generated-core-package) ·
[Platform-Specific Configuration](#platform-specific-configuration) ·
[Capabilities](#capabilities) · [Runtime Layer](#runtime-layer) ·
[Context Strategy](#context-strategy) · [Artifact Architecture](#artifact-architecture) ·
[Artifact Normalization and Validation](#artifact-normalization-and-validation) ·
[Execution Flow](#execution-flow-runtime-platform) · [Platform Support](#platform-support) ·
[Workflow DSL Reference](#workflow-dsl-reference) ·
[Runtime Files](#runtime-files-written-per-ticket) · [Safety Boundaries](#safety-boundaries) ·
[Testing](#testing) · [Troubleshooting](#troubleshooting) ·
[Command Reference](#command-reference) ·
[Rules for Coding Agents](#rules-for-coding-agents-working-in-this-repo)

The architecture separates four concerns:

```text
Canonical Definitions
        ↓
Compiler / Platform Adapters
        ↓
Generated Repository Package
        ↓
Platform Execution
```

The same canonical workflow can therefore execute through different platforms without redefining its semantics.

The key architectural principle is:

```text
Canonical layer     → defines WHAT the workflow means
Compiler            → determines HOW it is packaged
Platform execution  → determines HOW agents are invoked
Runtime             → provides deterministic execution where the platform does not
```

---

# Architectural Layers

```text
canonical/          # WHAT: platform-agnostic source of truth (data only)
engine/             # HOW: the installable `jira2pr` Python package
├── compiler/       #   canonical → generated repository package
├── jira2pr/        #   CLI entry point (`jira2pr init|check|run|resume|...`)
├── runtime/        #   workflow engine, backends, integrations
├── tests/          #   pytest suite (loads canonical/ from the repo root)
└── tools/          #   developer-only helper scripts
docs/               # design notes (this file)
```

## 1. Canonical Layer

The canonical tree defines Jira2PR workflow semantics.

```text
canonical/
├── agents/                     # Agent behavior (one .md per agent + _registry.yaml)
├── artifacts/                  # Artifact contracts / schemas
├── capabilities.yaml           # Logical external capabilities
├── workflows/                  # Workflow state machines
│   ├── feature.workflow.yaml
│   ├── bugfix.workflow.yaml        # currently an empty placeholder
│   ├── scope-creep.workflow.yaml   # currently an empty placeholder
│   └── shared/
│       ├── workers.yaml            # worker → capabilities / actions / delegation
│       ├── success-criteria.yaml   # state criteria labels
│       ├── supervisor.yaml         # supervisor output contract + evaluation rules
│       └── execution-policy.yaml   # retry / escalation / terminal policy
├── state/                      # Workflow state template
├── platform-extras/            # Per-platform inputs (models.yaml, README templates)
├── project-instructions.md     # Template for the target repo's agent instructions
└── .env.example                # Credential template copied to the target repo
```

The canonical layer answers:

```text
Who performs work?        → agents/
What gets produced?       → artifacts/
When does work happen?    → workflows/*.workflow.yaml
What can workers access?  → capabilities.yaml + workflows/shared/workers.yaml
How is work judged?       → workflows/shared/success-criteria.yaml + supervisor.yaml
How is retry/escalation?  → workflows/shared/execution-policy.yaml
How is execution tracked? → state/
```

Workflow semantics must remain independent of Copilot, Aider, OpenCode, or future platforms.

For example:

```text
canonical/agents/planner.md
```

defines planner behavior.

```text
canonical/artifacts/plan.schema.yaml
```

defines the machine-readable planning contract.

```text
canonical/workflows/feature.workflow.yaml
```

determines when the planner runs and what happens after it succeeds, fails, or escalates.

---

# Agent Roles

Jira2PR deliberately separates doing work, evaluating work, and driving workflow state.

## Workers

Workers perform domain-specific work.

Examples:

```text
jira-reader
researcher
planner
coder
reviewer
pr-author
```

Workers never control workflow transitions.

Workers never directly modify workflow state.

## Supervisor

The supervisor is an evaluator.

It evaluates the output of the current state against that state's resolved success criteria and returns:

```json
{
  "outcome": "success|failure|escalate",
  "reason": "...",
  "feedback": "...",
  "violations": []
}
```

The supervisor does not choose the next state.

For example:

```text
Supervisor
    ↓
outcome = failure

Workflow definition
    ↓
failure → plan
```

## Orchestrator

The orchestrator exists only on agent-driven platforms that need an agent to interpret workflow state.

Examples:

```text
GitHub Copilot
OpenCode (not currently supported)
```

The orchestrator:

```text
loads current state
    ↓
invokes worker
    ↓
invokes supervisor
    ↓
receives outcome
    ↓
applies workflow-defined transition
    ↓
persists state
```

It does not perform worker responsibilities and does not make evaluation judgments.

Runtime-driven platforms (the `runtime` platform, which uses Aider for repository editing) do not
require an orchestrator agent: `WorkflowExecutor` in Python performs the same loop deterministically.
The assembler therefore does not emit `orchestrator.md` for the runtime platform.

---

# Compiler Layer

The compiler lives under:

```text
engine/compiler/
└── assembler/
    ├── base.py
    ├── core_package.py
    ├── dsl_parser.py
    ├── model.py
    ├── registry.py
    ├── templates.py
    ├── validator.py
    ├── writer.py
    └── platforms/
        ├── __init__.py                 # PLATFORMS registry (copilot, runtime)
        ├── copilot.py                  # GitHub Copilot adapter
        ├── runtime.py                  # runtime-driven adapter (LiteLLM + Aider)
        ├── aider.py                    # legacy Aider adapter (not registered)
        └── _opencode_quarantined.py    # pre-DSL OpenCode adapter (not imported)
```

The compiler pipeline is conceptually:

```text
canonical
    ↓
parse
    ↓
typed DSL model
    ↓
cross-reference validation
    ↓
platform projection
    ↓
generated repository assets
```

`CanonicalRegistry` loads canonical definitions but does not contain platform execution logic.

Platform adapters own platform-specific packaging decisions.

---

# Generated Core Package

Both the Aider-backed runtime platform and Copilot receive a shared Jira2PR payload under:

```text
.jira2pr/
```

Typical contents include:

```text
.jira2pr/
├── agents/              # agent prompts (runtime platform; Copilot uses .github/agents/)
├── artifacts/           # schemas (copied) + per-ticket artifacts <TICKET>/ (written at runtime)
├── capabilities.yaml
├── config/
│   └── runtime.yaml     # runtime platform only: models, backends, map_tokens, verification
├── config.yaml          # generated_by, generator_version, platform, agents
├── context/             # per-ticket evidence/context files (written at runtime)
├── logs/                # runtime logs (written at runtime)
├── runtime/
│   ├── integrations/    # jira.py, git.py, github.py (copied from engine/runtime/integrations)
│   └── backends/prompts/  # runtime platform only: Aider/LiteLLM prompt files
├── state/               # workflow-state.template.yaml + <TICKET>.yaml (written at runtime)
├── workflows/           # copied verbatim from canonical/workflows
└── .manifest.json       # list of generated files, used for pruning
```

The exact contents depend on the platform. Only the compiler-written files are tracked in
`.manifest.json`; per-ticket data under `artifacts/<TICKET>/`, `context/`, `state/<TICKET>.yaml`
and `logs/` is runtime data and is never touched by `jira2pr init`.

The important rule is:

> Workflow state and workflow artifacts live under `.jira2pr/`, not under a platform-specific directory.

This allows execution state to survive platform changes.

---

# Platform-Specific Configuration

Model selection is not canonical.

Different models have different strengths across:

```text
reasoning
coding
instruction following
structured output
Aider edit-protocol compliance
context tolerance
cost
latency
```

Therefore models map directly to agents per platform.

Example:

```text
canonical/platform-extras/
├── copilot/    # models.yaml, README.md.tpl
├── runtime/    # models.yaml, README.md.tpl   (the live "Aider-backed" platform)
├── aider/      # models.yaml, README.md.tpl   (legacy; adapter no longer registered)
└── opencode/   # models.yaml, README.md.tpl   (quarantined)
```

Example runtime (LiteLLM/Aider) mapping — LiteLLM-style `provider/model` identifiers:

```yaml
models:
  jira-reader: github_copilot/gpt-5.6-luna
  planner: github_copilot/claude-haiku-4.5
  coder: ollama_chat/qwen3-coder:30b
  reviewer: github_copilot/claude-haiku-4.5
  pr-author: github_copilot/gpt-5.6-luna
  researcher: github_copilot/gpt-5.6-luna
  supervisor: ollama_chat/qwen3-coder:30b
```

Example Copilot mapping (note `orchestrator` is required here and not for runtime):

```yaml
models:
  orchestrator: github-copilot/gpt-5-mini
  planner: github-copilot/claude-sonnet-4.6
  coder: github-copilot/claude-sonnet-4.6
  reviewer: github-copilot/gpt-5
  supervisor: github-copilot/gpt-5
  # jira-reader, researcher, pr-author ...
```

The validator (`_check_platform_models`) requires a non-empty model for every agent in the registry
(excluding `orchestrator` for the `runtime` platform). This replaces the previous scalar model-tier
system (`model_tier`, `model-tiers.yaml`, `apply_model_tiers.py`).

The same agent may use completely different models on different platforms.

---

# Capabilities

Canonical capabilities describe logical operations, not implementation paths.

Example:

```yaml
jira.read:
  description: Fetch and parse a JIRA issue
  type: context
  binding:
    kind: script
    handler: jira
```

The canonical layer knows:

```text
jira.read → jira handler
```

but does not hardcode:

```text
.jira2pr/runtime/integrations/jira.py
```

Platform/runtime layers resolve logical handlers to concrete implementations.

Examples:

```text
jira.read
    ↓
runtime platform (Aider-backed)
    ↓
runtime.capabilities.resolve() → python3 .jira2pr/runtime/integrations/jira.py ...

jira.read
    ↓
Copilot
    ↓
generated instructions telling the agent to execute the same script
(.github/instructions/capabilities.instructions.md)
```

Two binding kinds exist:

| Kind | Meaning | Examples |
|------|---------|----------|
| `script` | Resolved to a named handler (`jira`, `git`, `github`) → a script under `.jira2pr/runtime/integrations/` | `jira.read`, `git.status`, `git.commit`, `git.push`, `pr.create`, `pr.update` |
| `native` | Fulfilled by a platform-native tool (web search, diff view, test results) | `web.search`, `diff.read`, `test.results` |

Capability `type` is `context` (read-only, resolved before a worker runs) or `action` (mutating,
executed after a worker's output is validated). `workflows/shared/workers.yaml` declares which
capabilities each worker may use (`runtime_context`, `actions`) and which workers it may delegate
to (`can_delegate`).

---

# Runtime Layer

The runtime lives under:

```text
engine/runtime/
├── artifacts/
├── backends/
├── capabilities.py
├── integrations/
└── workflow/
```

Current responsibilities are separated into several areas.

## Backends

```text
runtime/backends/
├── aider.py
├── base.py
├── mock.py
└── prompts/
```

Backends translate Jira2PR execution semantics into model/platform invocation. They implement the
abstract `LLMBackend` interface in `base.py`, which defines these execution modes:

```text
produce_artifact()     # write a document/YAML artifact to a file
produce_structured()   # write machine-readable output (supervisor JSON)
edit_repository()      # edit exactly the files the caller marks editable
repair_repository()    # fix test/lint failures using Aider's lint/test loop
fix_repository()       # test-repair attempt for verification feedback (default: edit_repository)
```

`fix_repository()` is the hook for verification feedback in the implement ⇄ run-tests loop. The runtime calls it when
`implement` is re-entered with failing tests or lint, instead of the per-task
`edit_repository()` path. The runtime re-verifies after every call and owns the attempt budget, so a
backend performs one attempt per call. A backend can use its own in-session test loop inside that call.
`remediate_review()` no longer exists: review findings go back to `implement`, and the coder applies them.

Implementations:

| Backend | Role |
|---------|------|
| `jira2pr.py` (`Jira2PRBackend`) | Composite and default. Routes `produce_*` to LiteLLM and `edit/repair/fix` to Aider |
| `litellm_backend.py` | Direct `litellm.completion()` calls; writes the response to the artifact file |
| `aider.py` | Runs `aider` as a subprocess (`--message-file`, `--read`, `--map-tokens`, `--test-cmd`, `--lint-cmd`). `fix_repository()` uses its `--auto-test` loop |
| `mock.py` | Deterministic backend for tests (`--backend mock`) |

Why composite: content-producing workers do not need Aider's edit-format protocol, so they use
direct LiteLLM completions (more reliable with local models). Repository editing benefits from
Aider's repo map, edit-format handling and filesystem mutation, so only that work goes through Aider.
Prompts for both live in `runtime/backends/prompts/` and are copied to `.jira2pr/runtime/backends/prompts/`.

## Integrations

```text
runtime/integrations/
├── jira.py
├── git.py
└── github.py
```

These provide deterministic external operations.

Examples:

```text
Fetch JIRA
Read git status
Commit
Push
Create/update PR
```

They are not AI agents.

## Workflow Engine

```text
runtime/workflow/
├── action_executor.py      # runs action capabilities (git.commit/push, pr.create/update)
├── context_strategy.py     # optional-context selection per worker
├── evidence.py             # git diff + test/lint evidence for implement/review
├── executor.py             # WorkflowExecutor: the state-machine loop
├── feedback.py             # WorkerFeedback passed to the next attempt
├── loader.py               # RuntimeProject: loads .jira2pr/ into memory
├── repository_context.py   # git ls-files + tree-sitter/ast/config repository map
├── review.py               # parses the reviewer's `review-verdict` block
├── state_manager.py        # atomic read/write of state/<TICKET>.yaml
├── supervisor_invoker.py   # supervisor evaluation → success|failure|escalate
├── task_scope.py           # keeps a coder attempt to its allowed files (reverts the rest)
├── transitions.py          # pure transition/retry/escalation logic (cycle budgets)
└── worker_invoker.py       # artifact workers, task-wise editing, and test-repair passes
```

The workflow engine is responsible for:

```text
Load workflow
Load persisted state
Resolve workers
Resolve context
Invoke workers
Normalize/validate artifacts
Invoke supervisor
Apply workflow transitions
Track retry counters and state visits
Persist state
Resume execution
```

---

# Context Strategy

Not all context should be supplied to every agent.

Jira2PR distinguishes three categories:

```text
Workflow-required context
    → state.consumes

Capability-required context
    → worker.runtime_context

Optional execution context
    → ContextStrategy
```

Required context must never be removed by context optimization.

Optional context may be included selectively to control context size and model reliability.

For example:

```text
jira-reader
    ↓
jira-reader.md
requirements-schema.md
JIRA ticket context

planner
    ↓
planner.md
plan.schema.yaml
requirements.md
repository/project context

coder
    ↓
coder.md
current plan task
project instructions
repository map/context

supervisor
    ↓
supervisor.md
supervisor contract
state-specific criteria
state evidence
```

This is especially important for local models, where excessive context can reduce instruction and edit-format compliance.

---

# Artifact Architecture

Jira2PR distinguishes human-oriented artifacts from machine-executed contracts.

## Document Artifacts

Examples:

```text
requirements.md
review.md
pr-description.md
decision-schema.md
```

These primarily communicate information between agents and humans.

## Executable Planning Contract

The implementation plan is:

```text
plan.yaml
```

rather than free-form Markdown.

Example:

```yaml
version: 1

summary: >
  Support multiple input CSV files.

tasks:
  - id: T1
    file_path: tools/example/main.py
    edit_mode: modify
    instructions: >
      Normalize the input configuration so that both a single path
      and a list of paths are supported.
    dependencies: []

tests:
  - id: TEST1
    file_path: tests/test_main.py
    edit_mode: modify
    instructions: >
      Add tests for single-file and multi-file input.
    verifies:
      - Single-file behavior remains backward compatible.
      - Multiple files are processed together.
    dependencies: [T1]

constraints:
  - Preserve existing behavior.

out_of_scope: []
```

`plan.yaml` acts as a machine-readable contract between the planner and the runtime/coder.

The runtime can deterministically derive:

```text
task order
file paths
edit modes
task dependencies
editing instructions
test expectations
```

without parsing free-form Markdown.

The authoritative schema is `canonical/artifacts/plan.schema.yaml`. Both `tasks` and `tests` entries
operate on exactly one repository file (`file_path`), and `edit_mode` is `create | modify | delete`
for tasks and `create | modify` for tests.

---

# Artifact Normalization and Validation

Generated artifacts pass through deterministic processing before semantic evaluation.

```text
Worker
    ↓ Generated artifact
    ↓
Normalize
    ↓
Structural validator
    ↓
Supervisor
```

Runtime artifact processing lives under:

```text
runtime/artifacts/
├── normalizer.py
└── validator.py
```

## Normalizer

The normalizer performs harmless mechanical cleanup.

Example:

````text
```yaml
version: 1
...
```
````

becomes plain YAML:

```yaml
version: 1
...
```

It only strips an outer Markdown fence and normalizes the trailing newline. It never repairs content.

## Structural Validator

`validate_artifact()` dispatches by artifact name. Today only `plan.yaml` has a structural validator
(`validate_plan()`); Markdown artifacts (`requirements.md`, `review.md`, `pr-description.md`) pass
through and are judged later by the supervisor or by their trailing metadata blocks.

`validate_plan()` parses the YAML and enforces, deterministically:

- `version: 1`, and non-empty `tasks` **and** `tests` lists
- unique, non-empty IDs across tasks and tests
- non-empty `instructions`; `dependencies` is a list of IDs that were already defined earlier
- `edit_mode` in `create|modify|delete` for tasks and `create|modify` for tests; `tests` entries need a
  non-empty `verifies` list
- `file_path` stays inside the repository root
- filesystem consistency: `modify`/`delete` targets must **exist**, `create` targets must **not** exist

A failure raises `ArtifactValidationError`, which the worker invoker converts into `WorkerOutputError`
→ `WorkerFeedback`, so the next attempt of the same state sees exactly what was wrong (the "feedback
loop"). The supervisor is never asked to judge structurally invalid output.

Other deterministic gates that parse trailing fenced blocks:

| Artifact | Block | Parsed by | Required keys |
|----------|-------|-----------|---------------|
| `review.md` | ```` ```review-verdict ```` | `runtime/workflow/review.py` | `verdict` (`approve\|changes_requested\|escalate`), `reason`, and `findings` (`file` + `instruction`, required for `changes_requested`; each `file` must be a `plan.yaml` `file_path`) |
| `pr-description.md` | ```` ```pr-actions ```` | `worker_invoker._extract_pr_action_metadata` | `commit_message`; optional `pr_title` |

---

# Execution Flow (Runtime Platform)

`jira2pr run feature PROJ-123` executes `WorkflowExecutor.run()`:

```text
load state/<TICKET>.yaml (or create it at initial_state)
    ↓
loop until the current state is terminal:
    ├─ enforce global max_total_iterations (else escalate)
    ├─ resolve context (consumes + runtime_context + ContextStrategy)
    ├─ invoke worker (model from config/runtime.yaml)              [kind: worker]
    │     ├─ state.produces non-empty → artifact worker → normalize → validate
    │     ├─ state.produces empty     → repository worker → one plan task at a time
    │     │                              (or one test-repair pass when the pending feedback reports failed verification)
    ├─ run deterministic verification                              [kind: verification]
    │     └─ test + lint commands from config/runtime.yaml → evidence
    ├─ evaluate the result  (see "Who judges what")
    ├─ transitions.next_state(outcome, retry_counts)
    ├─ write failure feedback to the transition target (e.g. implement-feedback.json)
    ├─ run the worker's declared actions on success (pr-author only)
    └─ persist state
```

## Who judges what

| State | Worker | Judged by |
|-------|--------|-----------|
| `jira-ingest` | jira-reader | supervisor (criteria `jira-ingest`) |
| `plan` | planner | structural validator, then supervisor (criteria `planning`) |
| `implement` | coder | the coder's own completion, with three failure checks. A backend error (Aider timeout or non-zero exit) counts as a failure against `implement`'s `max_attempts` (4). So does a task that changes a file outside its allowed set (the change is reverted), and a task whose file is unchanged after its edit. Each check runs after the task, so the attempt stops early. No supervisor. Otherwise the next state, `run-tests`, judges the result |
| `run-tests` | none (`kind: verification`) | **deterministic** evidence. First, the optional `lint_fix_command` (default `uv run ruff check --fix`) runs with the plan's changed files as arguments, so it only touches those files. Then the test and lint commands run. Pass → `review`. Fail → `implement` with the test output as feedback |
| `review` | reviewer | the reviewer's trailing `review-verdict` block: `approve` → success, `escalate` → escalate, `changes_requested` → failure to `implement` with one finding per file (`file` + `instruction`). Files must be `plan.yaml` `file_path`s. A missing or malformed block, or an unknown file, is `invalid_output` and re-runs `review` |
| `submit` | pr-author | action execution (`git.commit`, `git.push`, `pr.create`/`pr.update`) driven by a trailing `pr-actions` block |

## Implement state: task-wise editing and retry feedback

The coder never receives the whole plan as one prompt. On a first pass, `_invoke_repository_worker()`
loads `plan.yaml`, checks `dependencies`, and for each task calls `edit_repository()` with:

```text
read-only:  coder.md + project instructions + repo map + a small per-task context file
            + the current files edited by the task's dependencies (task.dependencies → their file_path)
editable:   exactly one repository file (task.file_path)
```

Dependency files let a dependent task (for example, a test task that depends on an implementation task) read the code it
builds on. Files that do not exist yet, and the task's own editable file, are skipped.

The coder prompt (`canonical/agents/coder.md`) asks for testable code: new behavior goes in named, importable functions,
not inline in entry points such as `main()`. A test task tests the function the earlier task defines, and names any
missing function or file instead of guessing it.

This keeps context small and edit-format compliance high for local models.

After each task, the runtime does two checks. Both run before the attempt can move on.

1. **Scope.** The working tree is captured before the task. Afterward, any change outside the task's one editable file is
   reverted, and the attempt fails with `out-of-scope-edit`. Fix passes check against the plan's files the same way.
2. **Progress.** A task that names a file must change it. If the file is unchanged, the attempt fails with `empty-diff`.

Together these verify that each step changed its own file and nothing else. They do not verify that the step did what
the plan asked. A task can change its file and still leave part of its instructions undone. Those gaps are caught
downstream: `run-tests` catches them only if the tests exercise the missing behavior, and `review` judges the combined
change across all planned files using `implementation-diff.patch`. The commit manifest (`git.py commit` aborts on files
outside `plan.yaml`) is the last check on scope.

When `implement` is re-entered with failure feedback, the runtime chooses a mode from the feedback's `source`:

- `verification` (failing tests or lint from `run-tests`): one `fix_repository()` call over all plan-authorized files,
  using Aider's test-repair prompt and `--auto-test`. The test and lint result files are read-only context for the repair.
  If the repair changes nothing, the attempt fails as `verification` again, with the original test and lint details kept.
  Tasks are not re-run, so a completed task is never flagged as a no-op.
- `review` (`changes_requested`): only the tasks whose `file_path` has an open finding are re-run, in plan order. Each
  task's context gets the open finding instructions as `review_findings`. Other tasks keep their edits. The coder prompt
  tells the coder to address the findings in its one file.
- **Finding status.** Every finding is kept in `<state>-findings.json` with a `status`:
  - `pending` when the review writes it.
  - `addressed` when its task completes with a change, or a successful fix pass covers its file.
  - `reopened` when a failing `run-tests` follows, because addressed changes can no longer be trusted.
  Only `pending` and `reopened` findings are open and get re-run. When `implement` succeeds, the file moves to
  `context/<TICKET>/archive/<state>-findings-<n>.json`, so each review cycle keeps its record.
- **State file.** `state/<TICKET>.yaml` has an `open_findings` list (`state`, `file`, `instruction`, `status`), refreshed
  after every attempt. It shows what the reviewer asked for that is still open.
- `llm-error`, `empty-diff`, or `out-of-scope-edit` (task-level failures): the retry resumes at the failed task. Tasks
  before it keep the edits they made in the previous attempt and are not run again. The failed task and the tasks after
  it run as normal. Re-running an earlier task would make it see its own finished work and report no change.

The feedback file, `implement-feedback.json`, is part of the read-only context in both modes. `run-tests` verifies the
result again. The feedback file is cleared when `implement` succeeds. When the run escalates, the feedback stays with the
failing state, so the file describes the latest failure and its `resume_from` task.

## Implement ⇄ run-tests ⇄ review loop

The loop is declared in the workflow DSL, not in code. Each failing edge goes back to `implement`:

- `implement` → `run-tests` on success.
- `run-tests` → `review` on success. On failure, → `implement` with the test output as feedback.
- `review` → `submit` on `approve`. On `changes_requested`, → `implement` with the review reason as feedback.
  A malformed `review.md` (no valid verdict) is `invalid_output` and goes back to `review` (`invalid_output: review`).
- `run-tests` and `review`'s `changes_requested` both draw from the shared budget `implement-cycle`
  (`budgets: {implement-cycle: 5}`). The fifth such failure escalates to `human-review`. The budget is cumulative
  for the run and is not reset on forward progress.
- `review`'s `max_attempts: 3` bounds malformed `review.md` (`invalid_output`, a self-loop). It is separate from the shared budget.
- `implement` (`max_attempts: 4`) is the attempt limit for each task. Failures are backend errors (`llm-error`), out-of-scope edits (`out-of-scope-edit`), and tasks whose file is unchanged after the edit (`empty-diff`). Each task has its own counter, `implement:<task>`. See "Counting retry attempts".
- The backend's `fix_repository()` may run its own in-session test loop. Aider uses `--auto-test`.
  The runtime still re-verifies after each fix, so a backend cannot mark a run as passing on its own.

## Retry and escalation

Defined by `workflows/shared/execution-policy.yaml` and each state's `retry` / `transitions`:

- `retry.max_attempts` bounds a state's own failures: self-loops, and cross-state failures from a state that declares
  `max_attempts` explicitly. Exhaustion escalates (`on_exhaustion: escalate`). If a state declares neither `max_attempts`
  nor `budget`, the policy default (`default_max_attempts`, 1) applies to self-loops only.
- `retry.budget: <name>` draws a state's failures from a shared workflow budget (`budgets:`) instead of its own counter.
- `retry.max_total_iterations` (workflow override, else policy default) bounds total state visits. A `{base, per_task}`
  override scales the cap with plan size: `base + per_task × N`, where N counts the tasks and tests in `plan.yaml`.
- `escalate` always routes to the terminal `human-review` state (status `escalated`).
- `done` is the terminal success state (status `completed`).

### Counting retry attempts

Every failure increments exactly one counter in `retry_counts`. Counters are keyed by state name, budget name, or, for
task-level failures, `<state>:<task>`.

1. A failure from a state with `retry.budget` increments that budget, whatever the failure target. Failures from
   `run-tests` and `review` (`changes_requested`) both increment `implement-cycle`.
2. A task-level failure in `implement` (`llm-error`, `empty-diff`, `out-of-scope-edit`) increments that task's own
   counter, `implement:<task>`. Each task has its own attempt budget, so a failure in one task does not use up another
   task's retries.
3. Otherwise, a self-loop failure or a cross-state failure from a state with `max_attempts` increments the state's own
   counter. This includes `invalid_output` (malformed `review.md`), which increments `review`.
4. Any other cross-state failure is plain routing and increments nothing.

Counters are cumulative for the run. Nothing resets them on forward progress. When a counter reaches its limit, the
transition escalates to `human-review`.

The canonical `feature` workflow counts as follows:

| Failure | Counter | Limit |
|---------|---------|-------|
| `jira-ingest` invalid output (self-loop) | `jira-ingest` | 2 |
| `plan` invalid output (self-loop) | `plan` | 3 |
| `implement` backend error (`llm-error`), out-of-scope edit (`out-of-scope-edit`), or unchanged task file (`empty-diff`) | `implement:<task>` | 4 per task |
| `run-tests` verification failed (`→ implement`) | `implement-cycle` | 5, shared |
| `review` `changes_requested` (`→ implement`) | `implement-cycle` | 5, shared |
| `review` malformed `review.md` (`invalid_output`, self-loop) | `review` | 3 |
| `submit` failure (self-loop, no `max_attempts`) | `submit` | 1 (policy default) |

The `attempt` number in logs, history, and feedback files is the visit number of the state in the run. It is not the
counter value. A shared budget therefore does not make `attempt` look like a per-state retry count. Total visits are
also capped by `max_total_iterations` (10 + 2 × plan task count in the canonical workflow). A full implement → run-tests → review cycle costs
3 visits, and each counted cycle adds 3. Five shared cycles plus the first pass need about 22 visits, which requires a plan of at least 6 tasks (10 + 2 × 6 = 22). Smaller plans hit the cap before the shared budget is exhausted, which is intended. The remaining headroom covers `plan` and `jira-ingest` retries.

Other exceptions, such as missing plan files, dependency errors, and Aider precondition errors, are not counted. They
stop the run.

### Worked example: how the budgets interact

Canonical settings: `max_total_iterations: {base: 10, per_task: 2}`, `budgets: implement-cycle: 5`, `implement`
`max_attempts: 4`, and `jira-ingest` `max_attempts: 2`. The cap is checked before every state visit. A visit is
blocked once `total_iterations` has reached the cap.

**Cap for this plan:** the planner writes 3 tasks: `T1` (implement `a.py`), `T2` (implement `b.py`), and `T3` (test
`test_a.py`). N = 3, so the cap is 10 + 2 × 3 = **16**.

**Run A: a few recoverable failures, then success**

| Visit | State | What happens | Counter changes | Total |
|---|---|---|---|---|
| 1 | jira-ingest | Succeeds | — | 1 |
| 2 | plan | Succeeds | — | 2 |
| 3 | implement | `T1`, `T2` edited. `T3` fails with `llm-error` and routes back to `implement`. | `implement:T3` = 1 | 3 |
| 4 | implement | Resumes at `T3`, which passes. | — | 4 |
| 5 | run-tests | Tests fail and route to `implement` | `implement-cycle` = 1 | 5 |
| 6 | implement | Fix pass from the test output | — | 6 |
| 7 | run-tests | Pass | — | 7 |
| 8 | review | `changes_requested` naming `a.py` and routes to `implement` | `implement-cycle` = 2 | 8 |
| 9 | implement | Only the `T1` (`a.py`) task reruns | — | 9 |
| 10 | run-tests | Pass | — | 10 |
| 11 | review | `approve` | — | 11 |
| 12 | submit | Succeeds, then `done` | — | 12 |

The run completes with 12 of 16 visits used and 2 of 5 shared cycles used. Each failure costs one visit, and that
visit counts toward the cap as well as toward its own counter.

**Run B: `jira-ingest` returns invalid output twice**

1. Visit 1: invalid output. The failure is a self-loop, so `jira-ingest` = 1 (limit 2) and the run retries.
2. Visit 2: invalid output again. `jira-ingest` = 2 reaches the limit, so the run escalates to `human-review`.

Two visits are used and the run escalates.

**Run C: the cap binds before the shared budget**

Without failures, the run takes 6 visits (jira-ingest, plan, implement, run-tests, review, submit). Each
`implement → run-tests → review` cycle costs 3 more visits. With a cap of 16, the first pass uses 5 visits, and three
full cycles bring the total to 14. The fourth cycle then starts, and the cap stops the run after two of its visits.
The run escalates with 4 of the 5 `implement-cycle` units used.

So with a 3-task plan, the cap, not `implement-cycle`, is the limit that matters. A larger plan raises the cap by 2
per task, which lets more cycles run.

| Knob | Counts | When it's exhausted |
|---|---|---|
| `retry.max_total_iterations` (`base`, `per_task`) | Every state visit | Escalates before the next visit once `total_iterations` ≥ base + per_task × N |
| `budgets.implement-cycle` | `run-tests` failures and `review` `changes_requested` | The failure that reaches 5 escalates |
| `implement` `max_attempts: 4` | Each task's failures (`implement:<task>`) | The 4th failure on the same task escalates |
| `jira-ingest` `max_attempts: 2` | Invalid `jira-ingest` output | The 2nd invalid output escalates |

## State file

`.jira2pr/state/<TICKET>.yaml` is written atomically **only** by the runtime/orchestrator. Fields
include `workflow`, `work_item`, `status` (`active|completed|escalated|failed`), `current_state`,
`retry_counts` (keyed by state name or budget name, e.g. `implement-cycle`), `total_iterations`, `artifacts`, `decisions`, `escalations`, `history`.
`jira2pr resume <TICKET>` simply reloads it and re-enters `run()`. Ticket keys are validated
(`^[A-Z][A-Z0-9]*-[0-9]+$`) before being used in a path.

---

# Platform Support

## Summary

| Concern | Runtime platform (Aider) | GitHub Copilot |
|---------|--------------------------|----------------|
| CLI target | `jira2pr init --platform runtime` (default) | `jira2pr init --platform copilot` |
| Who drives the workflow? | `WorkflowExecutor` (Python) | `orchestrator` agent in Copilot Chat |
| Who runs workers? | LiteLLM (artifacts, supervisor) and `aider` subprocess (code edits) | Copilot custom agents (sub-agents) |
| Who evaluates? | Deterministic tests/lint, reviewer verdict, supervisor via LiteLLM | `supervisor` sub-agent |
| Entry point | `jira2pr run feature <T>` / `resume` / `status` | `/feature`, `/resume`, `/status` prompts |
| Workflow definition | read by the Python loader from `.jira2pr/workflows/` | rendered into prompts/instructions; agents read `.jira2pr/workflows/` |
| Platform shell emitted | `AGENTS.md`, `.aider.conf.yml`, `.aiderignore`, `.jira2pr/config/runtime.yaml` | `.github/agents/*.agent.md`, `.github/prompts/*.prompt.md`, `.github/instructions/*.instructions.md`, `.github/copilot-instructions.md` |
| Capability execution | `runtime.capabilities.resolve()` → script argv | agent runs the script via the `execute` tool |
| Models | `platform-extras/runtime/models.yaml` (LiteLLM IDs) | `platform-extras/copilot/models.yaml` (Copilot IDs) |
| Shared payload | `.jira2pr/` | `.jira2pr/` |

## Aider (runtime platform)

**Aider is not a standalone platform adapter any more — it is the repository-editing backend of the
`runtime` platform.** History: an `AiderAssembler` (`platforms/aider.py`) originally let Aider
drive every worker. Commit `3fd3a07` ("replaced aider by runtime platform") introduced the composite
backend so that only repository edits go through Aider, while everything else uses LiteLLM.
The legacy `platforms/aider.py` and `platform-extras/aider/` have been removed; the per-platform
models for the runtime platform live in `platform-extras/runtime/models.yaml`.

Aider has no native multi-agent orchestration, so Jira2PR supplies it. `RuntimeAssembler` emits
**data only** — no workflow Python is generated into the target repo; the installed `jira2pr`
package owns behavior, so generated files cannot drift from the engine.

Generated for the target repository:

```text
AGENTS.md                      # project instructions (from canonical/project-instructions.md)
.aider.conf.yml                # Aider defaults; `read: [AGENTS.md]`
.aiderignore                   # keeps .jira2pr/state/ and .manifest.json out of Aider's context
.env.example
.jira2pr/                      # shared payload (see above)
├── agents/<slug>.md           # worker/supervisor system prompts (no orchestrator)
├── config/runtime.yaml
└── runtime/backends/prompts/  # Aider + LiteLLM prompt files
```

`config/runtime.yaml` is the runtime's configuration contract:

```yaml
backend: jira2pr
models: {coder: ollama_chat/qwen3-coder:30b, ...}   # from platform-extras/runtime/models.yaml
backends: {generation: litellm, repository: aider}
cli:
  base_args: [--yes-always, --no-auto-commits]
execution:                     # Aider repo-map budget per mode
  artifact:   {map_tokens: 0}
  structured: {map_tokens: 0}
  repository: {map_tokens: 5120}
verification:
  test_command: make test      # edit to match the target project
  lint_fix_command: uv run ruff check --fix   # optional autofix; the plan's files are appended as arguments; empty disables
  lint_command: make lint
```

Operating Aider safely:

- Aider is always run with `--yes-always --no-auto-commits`; **Jira2PR, not Aider, creates commits**
  (`pr-author` → `git.commit`), and only for files authorized by `plan.yaml`.
- Each Aider call receives an explicit `--read` list and an explicit editable-file list, so the
  model cannot wander across the repository.
- Local-model reliability is the main design pressure: per-task editing, explicit file lists,
  small context, bounded evidence output, and an Aider in-session test loop per fix attempt. The
  shared `implement-cycle` budget bounds the outer loop before escalation.

Requirements in the target environment: `aider` on `PATH`, `jira2pr` installed, `.env` with JIRA
and GitHub/Bitbucket credentials, and credentials/endpoints for each model provider referenced in
`models.yaml` (e.g. a local Ollama server, GitHub Copilot via LiteLLM).

## GitHub Copilot

Copilot has native custom agents and sub-agent delegation, so the platform can interpret the
workflow itself. `CopilotAssembler` emits an agent-driven UX shell under `.github/`:

```text
.github/
├── agents/<slug>.agent.md              # frontmatter (description, tools, model, agents) + agent body
├── prompts/{feature,bugfix,scope-creep,resume,status}.prompt.md   # slash commands
├── instructions/
│   ├── workflow-protocol.instructions.md       # criteria, retry/escalation policy, supervisor schema
│   ├── capabilities.instructions.md            # capability → script / native tool table
│   └── artifact-schemas.instructions.md        # index of .jira2pr/artifacts/*
├── copilot-instructions.md             # project instructions (from canonical/project-instructions.md)
└── README.md
```

Mapping rules:

- Only the `orchestrator` is `user-invocable: true`; all others are sub-agents only.
- `tools` are derived from `workers.yaml`: every agent gets `read`/`edit`; script-bound capabilities
  or declared `actions` add `execute`; native capabilities add the matching search/diff tool;
  `can_delegate` adds `agent`; the orchestrator also gets `plan`. The `agents:` frontmatter list is
  `can_delegate`.
- `model:` comes from `platform-extras/copilot/models.yaml`.
- The orchestrator reads `.jira2pr/workflows/<name>.workflow.yaml`, invokes the worker, invokes the
  `supervisor`, applies the workflow-defined transition, and writes `.jira2pr/state/<TICKET>.yaml`
  (the only writer; workers never touch state).
- Capability scripts under `.jira2pr/runtime/integrations/` are the same ones the runtime platform uses.

## Adding a platform

1. Create `canonical/platform-extras/<platform>/models.yaml` (+ optional `README.md.tpl`).
2. Add `engine/compiler/assembler/platforms/<platform>.py` with a `PlatformAssembler` subclass
   (`name = "<platform>"`) whose `assemble()` calls `assemble_core()` and then emits only the
   platform shell.
3. Register it in `platforms/__init__.py::_get_platforms()`. If it needs a runtime, implement an
   `LLMBackend`; if the platform has its own agent loop, emit an orchestrator instead.
4. Add tests in `engine/tests/test_<platform>_assembler.py`.

Canonical files must stay platform-agnostic: never add platform names, tool names, or model IDs to
`canonical/agents|workflows|artifacts`.

---

# Workflow DSL Reference

A `canonical/workflows/<name>.workflow.yaml` file is a state machine:

```yaml
version: 1
workflow: feature
initial_state: jira-ingest
retry:
  max_total_iterations:           # optional; integer, or {base, per_task} to scale with plan size
    base: 10
    per_task: 2
budgets:
  implement-cycle: 5              # shared by every state that sets retry.budget
states:
  plan:
    worker: planner               # slug from workflows/shared/workers.yaml
    consumes: [requirements.md, decisions/*.md]   # inputs (globs allowed)
    produces: [plan.yaml]         # empty/absent → repository-editing worker
    updates: [workflow-state.md]
    validation:
      success_criteria: planning  # key in workflows/shared/success-criteria.yaml
    retry:
      max_attempts: 2
    transitions:
      success: implement
      failure: plan               # self-loop = bounded retry
      escalate: human-review
  implement:
    worker: coder
    consumes: [plan.yaml, decisions/*.md, review.md]  # review.md exists only after a review
    updates: [workflow-state.md]
    validation:
      supervisor: false           # success is final; the next state judges it
    retry:
      max_attempts: 2
    transitions:
      success: run-tests
      failure: implement          # self-loop = bounded retry
      escalate: human-review
  run-tests:
    kind: verification            # deterministic test + lint; no worker
    retry:
      budget: implement-cycle     # draws from the shared budget (cycle edge)
    transitions:
      success: review
      failure: implement          # feedback is handed to implement
      escalate: human-review
  done:
    terminal: true
    outcome: success              # success | escalated
```

Fields: `kind` is `worker` (default) or `verification`. A verification state declares no `worker`.
`validation.supervisor: false` skips the supervisor for a worker state. `retry.max_attempts` and `retry.budget`
determine whether a cross-state failure consumes a counter (see "Counting retry attempts"). `transitions.invalid_output`
routes unusable worker output (for example, a malformed `review.md`) and falls back to `failure` when unset.

Rules enforced by `validate()` at compile time: every `worker` exists in `workers.yaml`; every
transition target is a defined state; every `success_criteria` key exists; capabilities referenced by
workers exist with the right `type` (`runtime_context` → `context`, `actions` → `action`);
`can_delegate` targets are real agents; artifact schemas exist; every state is reachable; and each
platform has a non-empty model for each agent it runs.

Success criteria (`success-criteria.yaml`) are labels, e.g. `planning: [requirements_covered,
implementation_feasible, test_strategy_defined]`. With `criteria_evaluation.mode: all_pass`, any
unverified label becomes a `violation`; the supervisor returns `failure` if the worker can fix it, or
`escalate` if a human decision is needed (escalation takes precedence).

---

# Runtime Files Written per Ticket

All under `.jira2pr/` and never tracked in `.manifest.json`:

```text
state/<TICKET>.yaml                          # WorkflowState (runtime-only writer)
state/archive/<TICKET>.yaml                  # archived state
artifacts/<TICKET>/requirements.md|plan.yaml|review.md|pr-description.md
context/<TICKET>/jira-read context, git-status context
context/<TICKET>/repository map              # git ls-files + tree-sitter/ast/config (non-editing workers)
context/<TICKET>/implementation-diff.patch   # evidence: diff of plan-authorized files only
context/<TICKET>/test-results.txt            # evidence: includes `exit_code:`
context/<TICKET>/lint-results.txt
context/<TICKET>/supervisor-<state>-decision.json
context/<TICKET>/<state>-feedback.json       # WorkerFeedback, addressed to the state that acts on it
                                             # (e.g. implement-feedback.json after a failed run-tests)
context/<TICKET>/commit-files.txt            # commit manifest: files `git.commit` may stage (from plan.yaml)
logs/jira2pr.log                             # all levels; console shows INFO (DEBUG with --debug)
```

`jira2pr clear-cache <TICKET>` removes a ticket's cached artifacts, context, and state. Prefer it to
deleting files by hand.

---

# Safety Boundaries

- **Ticket keys** are validated (`^[A-Z][A-Z0-9]*-[0-9]+$`) before being joined into any path.
- **Plan paths** must resolve inside the repository root; the coder may edit only the single file named
  by the current plan task.
- **Commits** stage only files derived from `plan.yaml` (a manifest); `git.py commit` aborts if the
  index holds anything not in the manifest.
- **Capability params** are validated against the DSL's argument template; unknown params and missing
  placeholders raise `CapabilityError`, so no arbitrary arguments reach a script.
- **Workers cannot mutate workflow state or choose transitions**; only the runtime/orchestrator does.
- **Bounded loops**: per-state `max_attempts`, shared `budgets` (for example `implement-cycle` across run-tests and review),
  global `max_total_iterations`, one test-repair attempt per verification failure, and bounded evidence output
  (`MAX_FAILURE_OUTPUT_CHARS`, 600s command timeout).
- **Secrets** live in `.env` (never committed); `.env.example` is the template.

---

# Testing

```bash
make test          # uv run python3 -m pytest tests/ -q (from engine/); pytest/ruff are in the dev dependency group
make lint          # ruff check engine/
```

| Test file | Covers |
|-----------|--------|
| `test_registry.py`, `test_workflow_loader.py`, `test_validator.py` | canonical loading and cross-reference validation, per-agent models |
| `test_runtime_assembler.py`, `test_copilot_assembler.py`, `test_writer.py` | generated output for each platform, idempotency (`check` mode), manifest pruning |
| `test_transitions.py`, `test_state_manager.py` | pure transition/retry logic; atomic state persistence |
| `test_executor_mock.py` | full workflow via `MockBackend` (happy path, verification loop and budget exhaustion, review routing to implement, global cap, resume) with `subprocess.run` patched |
| `test_action_executor.py`, `test_capabilities.py` | commit/push/PR actions, capability → argv resolution |
| `test_integrations_*.py` | `jira.py`, `git.py`, `github.py` helper scripts |

Tests load `canonical/` from the repo root (`conftest.py` also puts `engine/` and `engine/compiler/` on
`sys.path`). To test the runtime without models, use `jira2pr run feature <T> --backend mock`.

---

# Troubleshooting

| Symptom | Likely cause / action |
|---------|-----------------------|
| `ERROR: models.<slug>: no model configured` on `init` | add the agent to `platform-extras/<platform>/models.yaml` |
| `Backend configuration not found: .jira2pr/config/runtime.yaml` | package was generated for another platform; re-run `jira2pr init --platform runtime` |
| Workflow ends `escalated` | read `state/<TICKET>.yaml` → `escalations` and `retry_counts`, and `context/<TICKET>/*-feedback.json`. The escalation state tells you which counter ran out: `run-tests` or `review` means the shared `implement-cycle` budget (5) is spent; `implement` means two backend errors or no-change attempts; `review` with a malformed `review.md` means its `max_attempts` (3). Fix, then `jira2pr resume <TICKET>` |
| Plan rejected: `create target already exists` / `modify target does not exist` | the planner's file paths disagree with the repo; feedback is passed to the retry automatically |
| Evidence step fails with `No test command configured` | set `verification.test_command`/`lint_command` in `.jira2pr/config/runtime.yaml` (defaults are `make test` / `make lint`) |
| `aider` not found | install Aider and ensure it is on `PATH` for the process running `jira2pr` |
| Need details | rerun with `--debug`; see `.jira2pr/logs/jira2pr.log` |

---

# Command Reference

```bash
# from a source checkout (engine/)
cd engine && pip install -e .

jira2pr init   --platform runtime|copilot --target-dir <project>   # generate package
jira2pr check  --platform runtime|copilot --target-dir <project>   # CI: exit 1 if stale
jira2pr run    feature PROJ-123 [--backend jira2pr|mock] [--debug]
jira2pr resume PROJ-123
jira2pr status PROJ-123
jira2pr list
jira2pr clear-cache PROJ-123                                        # remove cached artifacts/state

make test      # cd engine && uv run python3 -m pytest tests/ -q
make lint      # ruff check (FIX=1 to autofix)
```

Required environment (`.env` in the target repo): `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`,
and `GITHUB_TOKEN` (or `BITBUCKET_TOKEN` + `BITBUCKET_USERNAME`). Plus model-provider credentials.

---

# Rules for Coding Agents Working in This Repo

1. **Edit `canonical/` and `engine/`, never generated output** (`.jira2pr/`, `.github/`, `AGENTS.md`,
   `.aider.conf.yml`, `tmp/`, `examples-autogenerated/`). Regenerate with `jira2pr init`.
2. Canonical semantics stay platform-neutral; platform specifics go in `platform-extras/` or an adapter.
3. Workers never change workflow state or choose transitions; the supervisor never chooses the next
   state; only the orchestrator/runtime applies workflow-defined transitions.
4. Cross-references (worker slugs, transition targets, success-criteria keys, capability IDs, models)
   are enforced by `engine/compiler/assembler/validator.py`. When adding any of these, update the
   validator tests in `engine/tests/`.
5. Keep deterministic work (tests, lint, git, JIRA, PR creation, schema validation) in runtime code,
   not in LLM prompts.
6. Run `make test` and `make lint` before finishing. Lint may report pre-existing import-order findings
   in files you did not touch; do not fix unrelated ones.

---

# Current Implementation Status and Known Gaps

Verified against the repository state at the time of writing; reconcile before relying on any item.

| Area | Status |
|------|--------|
| `runtime` platform (LiteLLM + Aider), `feature` workflow | Implemented end to end |
| `copilot` platform | `CopilotAssembler` reads models per agent via `registry.platform_models("copilot")` (same as `runtime.py`); `jira2pr init --platform copilot` works. The generated shell has not been exercised in a live Copilot session |
| `bugfix` and `scope-creep` workflows | Files are empty (the loader skips them with a warning), yet the Copilot assembler renders a prompt per workflow and the README advertises `/bugfix` |
| `--platform aider` | Rejected; Aider is the runtime platform's backend. `README.md` and `platform-extras/runtime/README.md.tpl` now use `--platform runtime`. `config/aider.yaml` references in the runtime template are still stale |
| Test suite | `uv run --with pytest python3 -m pytest tests -q` (from `engine/`). 254 pass. `test_model_baked_into_frontmatter` checks that every agent's frontmatter model matches `platform-extras/copilot/models.yaml`. Models are per-platform, so no test pins a model name. `MockBackend` implements all `LLMBackend` modes by output file name, and executor tests patch `subprocess.run` (see `tests/test_executor_mock.py`). `tests/test_runtime_assembler.py` replaced the legacy Aider assembler tests || Implement ⇄ run-tests ⇄ review loop | Implemented in the runtime engine (`kind: verification`, shared `budgets:` in the DSL, feedback addressed to the target state). `fix_repository()` (Aider's `--auto-test` loop) runs only for verification feedback. Review findings and attempt failures use the coder edit path. Copilot: the protocol instructs the agent to run the test and lint commands for verification states, but this path has not been exercised in a live session || OpenCode | Not supported; quarantined in `_opencode_quarantined.py` || `docs/` vs project instructions | The root project instructions mention `scripts/` and `examples-autogenerated/`; the current layout uses `engine/` and no checked-in generated examples || `produce_structured()` | Used by the supervisor invoker only; `plan.yaml` is produced through `produce_artifact()` and validated structurally || Context strategy | Implemented in `runtime/workflow/context_strategy.py`; repo map via `git ls-files` + tree-sitter for non-editing workers, Aider's repo map for editing workers |
Suggested next steps, in order: (1) refresh the stale README/templates for the runtime platform;
(2) author `bugfix` and `scope-creep` workflows or remove their prompt generation; (3) done: the
legacy Aider assembler (`platforms/aider.py`, `platform-extras/aider/`) has been deleted.