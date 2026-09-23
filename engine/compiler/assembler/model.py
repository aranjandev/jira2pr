"""Shared dataclasses describing the canonical DSL.

Both the compiler (parse -> validate -> project) and the runtime workflow
engine (`runtime/workflow/loader.py`) import these so the schema can never
silently diverge between "what gets generated" and "what gets executed".
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AgentSpec:
    slug: str
    name: str
    kind: str  # "orchestrator" | "supervisor" | "worker"
    description: str
    artifact_schema: str | None = None


@dataclass(frozen=True)
class CapabilityBinding:
    kind: str  # "native" (platform tool, no runtime script) | "script"
    handler: str  # handler key that will be resolved by the engine for platform specific implementation

@dataclass(frozen=True)
class CapabilitySpec:
    id: str
    description: str
    type: str  # "context" | "action"
    binding: CapabilityBinding


@dataclass(frozen=True)
class WorkerBinding:
    slug: str
    runtime_context: tuple[str, ...] = ()
    can_delegate: tuple[str, ...] = ()
    actions: tuple[str, ...] = ()


@dataclass(frozen=True)
class TransitionSpec:
    success: str | None = None
    failure: str | None = None
    escalate: str | None = None


@dataclass(frozen=True)
class StateSpec:
    name: str
    worker: str | None = None
    consumes: tuple[str, ...] = ()
    produces: tuple[str, ...] = ()
    updates: tuple[str, ...] = ()
    success_criteria: str | None = None
    max_attempts: int | None = None
    transitions: TransitionSpec = field(default_factory=TransitionSpec)
    terminal: bool = False
    outcome: str | None = None  # required when terminal is True: "success" | "escalated"


@dataclass(frozen=True)
class WorkflowSpec:
    name: str
    version: int
    initial_state: str
    states: dict[str, StateSpec]
    source_path: str = ""
    max_total_iterations: int | None = None  # None -> use ExecutionPolicy.max_total_iterations


@dataclass(frozen=True)
class SuccessCriteria:
    criteria: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class SupervisorContract:
    output_schema: dict
    criteria_evaluation: tuple[str, ...]
    instructions: str


@dataclass(frozen=True)
class ExecutionPolicy:
    default_max_attempts: int
    on_exhaustion: str  # "escalate"
    criteria_mode: str  # "all_pass"
    terminal_success_state: str
    terminal_escalated_state: str
    max_total_iterations: int


# Capability handler resolution maps (single source of truth for both compiler and runtime)

CAPABILITY_HANDLER_SCRIPT_MAP = {
    "jira": ".jira2pr/runtime/integrations/jira.py",
    "git": ".jira2pr/runtime/integrations/git.py",
    "github": ".jira2pr/runtime/integrations/github.py",
}

CAPABILITY_ARGS_MAP = {
    "jira.read": ["<ticket_key_or_url>"],
    "git.status": ["status"],
    "git.commit": ["commit", "<message>"],
    "git.push": ["push"],
    "pr.create": ["create", "--title", "<title>", "--body-file", "<body_file>"],
    "pr.update": [
        "update",
        "--pr-number",
        "<pr_number>",
        "--body-file",
        "<body_file>",
    ],
}
