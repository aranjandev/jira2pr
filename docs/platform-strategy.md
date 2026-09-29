# Jira2PR Platform Architecture Strategy

## Overview

Jira2PR defines platform-independent software-development workflows and projects them into different agent execution environments.

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
canonical/
├── agents/
├── artifacts/
├── capabilities.yaml
├── platform-extras/
├── project-instructions.md
├── state/
└── workflows/

engine/
├── compiler/
├── jira2pr/
└── runtime/
```

## 1. Canonical Layer

The canonical tree defines Jira2PR workflow semantics.

```text
canonical/
├── agents/             # Agent behavior
├── artifacts/          # Artifact contracts
├── capabilities.yaml   # Logical external capabilities
├── workflows/          # Workflow state machines
├── state/              # Workflow state template
├── platform-extras/    # Platform-specific configuration inputs
└── project-instructions.md
```

The canonical layer answers:

```text
Who performs work?        → agents/
What gets produced?       → artifacts/
When does work happen?    → workflows/
What can workers access?  → capabilities.yaml + workers.yaml
How is work judged?       → success-criteria.yaml + supervisor.yaml
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
OpenCode
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

Runtime-driven platforms such as Aider do not require an orchestrator agent.

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
        ├── aider.py
        └── copilot.py
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

Both Aider and Copilot receive a shared Jira2PR payload under:

```text
.jira2pr/
```

Typical contents include:

```text
.jira2pr/
├── agents/
├── artifacts/
├── capabilities.yaml
├── config/
├── config.yaml
├── context/
├── runtime/
├── state/
└── workflows/
```

The exact contents depend on the platform.

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
├── aider/
│   └── models.yaml
└── copilot/
    └── models.yaml
```

Example Aider mapping:

```yaml
models:
  jira-reader: ollama_chat/qwen3-coder:30b
  planner: ollama_chat/deepseek-r1:32b
  coder: ollama_chat/qwen3-coder:30b
  reviewer: ...
  pr-author: ...
  supervisor: ...
```

This replaces the previous scalar model-tier system.

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
Aider runtime
    ↓
runtime integration

jira.read
    ↓
Copilot
    ↓
generated executable/tool binding
```

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

Backends translate Jira2PR execution semantics into model/platform invocation.

For Aider, three distinct execution modes have emerged:

```text
produce_artifact()
produce_structured()
edit_repository()
```

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
├── action_executor.py
├── context_strategy.py
├── executor.py
├── loader.py
├── state_manager.py
├── supervisor_invoker.py
├── transitions.py
└── worker_invoker.py
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
Track attempts
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

These primarily communicate information between agents and h*mans.

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

tasks:*  - id: T1
    file_path: tools/ex*mple/main.py
    edit_mode: modify    instructions: >
      Normalize the input configuration so that both a single path
      and a list of paths are supported.
    dependencies: []

tests:
  - description: single-file behavior remains backward compatible.
  - description: Multiple files are processed together.
constraints:
  - Preserve existing behavior.

out_of_scope: []
```

*plan.yaml` acts as a machine-reada*le contract between planner and ru*time/coder.

The runtime can deter*inistically derive:

```text
task order
file paths
edit modes
task dependencies
editing instructions
tes* expectations
```

without parsing*free-form Markdown.

---

# Artifa*t Normalization and Validation

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

Runtime artifact pr*cessing lives under:

```text
runtime/artifacts/
├── normalizer.py
└─- validator.py
```

## Normalizer

The normalizer performs harmless mechanical cleanup.

Example:

````text
```yaml
version: 1
...
```