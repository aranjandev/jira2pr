"""Shared template logic — variable substitution and auto-generated section builder."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from assembler.registry import CanonicalRegistry


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


def _display_model(model: str, platform: str) -> str:
    """Strip the "(copilot)" style platform suffix for readable prose."""
    return re.sub(rf"\s*\({re.escape(platform)}\)\s*$", "", model)


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
    labels: dict[str, str] | None = None,
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
    lines.append("")
    lines.append("### Agent Roster")
    lines.append("")
    lines.append(f"{len(registry.agents)} agents are available:")
    lines.append("")
    lines.append("| Agent | Kind | Model | Artifact |")
    lines.append("|-------|------|-------|----------|")
    for agent in registry.agents:
        model = registry.model_for_tier(agent.model_tier, platform)
        display_model = _display_model(model, platform)
        artifact = f"`{agent.artifact_schema}`" if agent.artifact_schema else "—"
        lines.append(f"| **{agent.name}** | {agent.kind} | {display_model} | {artifact} |")
    lines.append("")
    lines.append(
        f"Agent definitions live in `{labels['agents_dir']}`. Each file is a "
        f"`{labels['agent_file_ext']}` with YAML frontmatter declaring its "
        f"`description`, `{labels['capability_field']}`, and `model`."
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
            resolution = f"`python3 {cap.binding.script} {' '.join(cap.binding.args)}`"
        lines.append(f"| `{cap.id}` | {cap.type} | {resolution} |")

    # --- Model Tiers ---
    lines.append("")
    lines.append("### Model Tiers")
    lines.append("")
    tiers = registry.model_tiers.get("tiers", {})
    for tier_num in sorted(tiers.keys(), key=lambda x: int(x)):
        tier_data = tiers[tier_num]
        model = tier_data.get("models", {}).get(platform, "?")
        display_model = _display_model(model, platform)
        lines.append(
            f"- **Tier {tier_num}** — {tier_data.get('description', '')}: "
            f"{tier_data.get('role', '')} ({display_model})"
        )

    return "\n".join(lines) + "\n"

