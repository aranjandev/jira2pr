"""Shared template logic — variable substitution and auto-generated section builder."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from assembler.model import ExecutionPolicy
    from assembler.registry import CanonicalRegistry

from assembler.model import CAPABILITY_HANDLER_SCRIPT_MAP, CAPABILITY_ARGS_MAP


def substitute_vars(text: str, variables: dict[str, str]) -> str:
    """Replace ``{{KEY}}`` placeholders in *text* with values from *variables*.

    Raises ``ValueError`` if any placeholders remain after substitution.
    """
    for key, value in variables.items():
        text = text.replace("{{" + key + "}}", value)
    remaining = re.findall(r"\{\{([A-Z_]+)\}\}", text)
    if remaining:
        raise ValueError(f"Unresolved template variable(s): {', '.join(remaining)}")
    return text


def execution_policy_vars(policy: "ExecutionPolicy") -> dict[str, str]:
    """``{{...}}`` vars every platform injects into agent bodies that reference
    execution-policy defaults (currently only the orchestrator agent).
    """
    return {
        "DEFAULT_MAX_ATTEMPTS": str(policy.default_max_attempts),
        "ON_EXHAUSTION": policy.on_exhaustion,
        "DEFAULT_MAX_TOTAL_ITERATIONS": str(policy.max_total_iterations),
        "TERMINAL_SUCCESS_STATE": policy.terminal_success_state,
        "TERMINAL_ESCALATED_STATE": policy.terminal_escalated_state,
    }


# ---------------------------------------------------------------------------
# "How Agents Contribute to Code" section generator
# ---------------------------------------------------------------------------

COPILOT_AGENTS_SECTION_LABELS: dict[str, str] = {
    "agents_dir": ".github/agents/",
    "agent_file_ext": ".agent.md",
    "capability_field": "tools",
}


def generate_agents_section(
    registry: "CanonicalRegistry",
    platform: str,
    models: dict[str, str],
    labels: dict[str, str] | None = None,
    include_orchestrator: bool = True,
) -> str:
    """Build the markdown for the dynamic (registry-driven) table sub-sections.

    The static canonical prose (section heading, overview paragraphs, state
    architecture) lives in canonical/project-instructions.md after the
    AGENTS_SECTION:AUTO_GENERATED marker and is passed through verbatim by
    the assembler. This function emits only the parts generated from the
    workflow/agent/capability registries.
    """
    labels = labels or COPILOT_AGENTS_SECTION_LABELS
    lines: list[str] = []

    # --- Agent Roster ---
    roster_agents = [
        agent
        for agent in registry.agents
        if include_orchestrator or agent.kind != "orchestrator"
    ]

    lines.append("")
    lines.append("### Agent Roster")
    lines.append("")
    lines.append(f"{len(roster_agents)} agents are available:")
    lines.append("")
    lines.append("| Agent | Kind | Model | Artifact |")
    lines.append("|-------|------|-------|----------|")

    for agent in roster_agents:
        model = models.get(agent.slug, "not configured")

        artifact = (
            f"`{agent.artifact_schema}`"
            if agent.artifact_schema
            else "—"
        )

        lines.append(
            f"| **{agent.name}** | "
            f"{agent.kind} | "
            f"`{model}` | "
            f"{artifact} |"
        )

    # --- Workflows ---
    lines.append("")
    lines.append("### Workflows")
    lines.append("")
    lines.append("| Workflow | Initial State | States |")
    lines.append("|----------|---------------|--------|")
    for workflow in sorted(registry.workflows.values(), key=lambda w: w.name):
        state_names = ", ".join(f"`{s}`" for s in workflow.states)
        lines.append(f"| `{workflow.name}` | `{workflow.initial_state}` | {state_names} |")

    # --- Capabilities ---
    lines.append("")
    lines.append("### Capabilities")
    lines.append("")
    lines.append("| Capability | Type | Resolution |")
    lines.append("|------------|------|------------|")
    for cap in sorted(registry.capabilities.values(), key=lambda c: c.id):
        if cap.binding.kind == "native":
            resolution = "native platform tool"
        else:
                script = CAPABILITY_HANDLER_SCRIPT_MAP[cap.binding.handler]
                args = CAPABILITY_ARGS_MAP.get(cap.id, [])
                resolution = f"`python3 {script} {' '.join(args)}`"
        lines.append(f"| `{cap.id}` | {cap.type} | {resolution} |")

    return "\n".join(lines) + "\n"

