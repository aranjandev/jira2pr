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


# ---------------------------------------------------------------------------
# "How Agents Contribute to Code" section generator
# ---------------------------------------------------------------------------

def generate_agents_section(
    registry: "CanonicalRegistry",
    platform: str,
    project_instructions_file: str,
) -> str:
    """Build the markdown for the dynamic (data-driven) table sub-sections.

    The static canonical prose (section heading, overview paragraphs,
    State & Artifact Architecture) lives in canonical/project-instructions.md
    after the AGENTS_SECTION:AUTO_GENERATED marker and is passed through
    verbatim by the assembler.  This function emits only the parts that are
    generated from registry data.
    """
    lines: list[str] = []

    # --- Agent Roster ---
    lines.append("")
    lines.append("### Agent Roster")
    lines.append("")
    lines.append("Five agents are available. Each has a defined scope and model tier:")
    lines.append("")
    lines.append("| Agent | Role | Model |")
    lines.append("|-------|------|-------|")
    for agent in registry.agents:
        model = registry.model_for_tier(agent["tier"], platform)
        # Strip the "(copilot)" suffix for display
        display_model = re.sub(r"\s*\(copilot\)\s*$", "", model)
        lines.append(f"| **{agent['name']}** | {agent['description'].split('.')[0]} | {display_model} |")
    lines.append("")
    lines.append("Agent definitions live in `.github/agents/`. Each file is a `.agent.md` with YAML frontmatter declaring its `description`, `tools`, `model`, and which subagents it may invoke.")

    # --- Skills ---
    lines.append("")
    lines.append("### Skills")
    lines.append("")
    lines.append("Skills are reusable, domain-specific instruction sets that agents load on demand. They live in `.github/skills/<skill-name>/SKILL.md`.")
    lines.append("")
    lines.append("| Skill | Purpose |")
    lines.append("|-------|---------|")
    for skill in registry.skills:
        purpose = re.split(r"\.\s", skill["description"], maxsplit=1)[0]
        lines.append(f"| `{skill['slug']}` | {purpose} |")

    # --- Agent Prompts ---
    lines.append("")
    lines.append("### Agent Prompts")
    lines.append("")
    lines.append("User-facing entry points are defined as `.prompt.md` files in `.github/prompts/`. Invoke them with a `/` slash command in the Copilot chat:")
    lines.append("")
    lines.append("| Prompt | Slash command | What it does |")
    lines.append("|--------|---------------|--------------|")
    for prompt in registry.prompts:
        purpose = prompt["description"].split(".")[0]
        lines.append(f"| `{prompt['slug']}.prompt.md` | `/{prompt['slug']}` | {purpose} |")

    # --- Workflows ---
    lines.append("")
    lines.append("### Workflows")
    lines.append("")
    lines.append("Multi-phase workflow definitions live in `.github/agent-workflows/`. The Orchestrator reads the matching workflow file and executes it phase-by-phase:")
    lines.append("")
    lines.append("| Workflow | Trigger | Phases |")
    lines.append("|----------|---------|--------|")
    lines.append("| `feature.md` | `/feature` | Bootstrap → Understand → Plan → Implement → Review → Submit |")
    lines.append("| `bugfix.md` | `/bugfix` | Bootstrap → Understand → Diagnose → Fix → Review → Submit |")
    lines.append("| `_resume.md` | Any PR link | Parses PR state and routes to the correct phase to continue |")
    lines.append("")
    lines.append("All workflows include a **Phase 0: Bootstrap** that handles both fresh (JIRA input) and resume (PR link) modes automatically.")

    # --- Instructions ---
    lines.append("")
    lines.append("### Instructions")
    lines.append("")
    lines.append("Persistent rules that apply across all agents are defined as `.instructions.md` files in `.github/instructions/`:")
    lines.append("")
    lines.append("| File | Scope | What it governs |")
    lines.append("|------|-------|-----------------|")
    for instr in registry.instructions:
        lines.append(f"| `{instr['slug']}.instructions.md` | PR bodies / commits | {instr['description'].split('.')[0]} |")

    # --- Git Push Authentication ---
    lines.append("")
    lines.append("### Git Push Authentication for Agents")
    lines.append("")
    lines.append("Agents push code using the `git-operations` skill (`git_helper.py push`). The script reads `.env` at the repo root and injects credentials automatically via `GIT_ASKPASS` — no system credential helper or `gh auth` required.")
    lines.append("")
    lines.append("**Required `.env` variables for HTTPS remotes:**")
    lines.append("- GitHub: `GITHUB_TOKEN=<personal-access-token>` (needs `repo` scope)")
    lines.append("- Bitbucket: `BITBUCKET_TOKEN=<app-password>` and `BITBUCKET_USERNAME=<your-username>`")
    lines.append("")
    lines.append("SSH remotes do not require these variables.")
    lines.append("")
    lines.append("> **Critical:** If `GITHUB_TOKEN` is absent or expired, `git push` will hang or fail silently. Do **not** attempt to work around this by calling `gh` CLI or modifying the remote URL manually — fix the token in `.env` instead.")

    # --- Shell Command Rules ---
    lines.append("")
    lines.append("### Shell Command Rules for Agents")
    lines.append("")
    lines.append("Applies whenever an agent runs shell commands in a terminal. Violations produce silent, hard-to-debug corruption:")
    lines.append("")
    lines.append("- **Never write file content using heredocs** (`<< 'EOF' ... EOF`) — they get mangled in agent terminal sessions.")
    lines.append('- **Never use `python3 -c "..."`  with double outer quotes** — the shell expands `$variables` and backticks inside.')
    lines.append("- **Always use `python3 -c '...'` with single outer quotes** and `\\n` for newlines — this is the only reliable pattern:")
    lines.append("  ```bash")
    lines.append("  python3 -c 'open(\"/tmp/file.md\",\"w\").write(\"line1\\nline2\\n\")'")
    lines.append('  # With dynamic values, concatenate inside the expression')
    lines.append("  python3 -c 'import datetime; ts=datetime.datetime.utcnow().strftime(\"%Y-%m-%dT%H:%M:%SZ\"); open(\"/tmp/file.md\",\"w\").write(\"# Title\\nTimestamp: \"+ts+\"\\n\")'")
    lines.append("  ```")

    # --- Model Tiers ---
    lines.append("")
    lines.append("### Model Tiers")
    lines.append("")
    lines.append(f"`.github/model-tiers.json` maps model tiers (0–3) to concrete Copilot model names. The `scripts/apply_model_tiers.py` script stamps the correct model into each agent file at setup time. Tier assignment reflects cost/capability trade-offs:")
    lines.append("")
    tiers = registry.model_tiers.get("tiers", {})
    for tier_num in sorted(tiers.keys(), key=lambda x: int(x)):
        tier_data = tiers[tier_num]
        model = tier_data.get("models", {}).get(platform, "?")
        display_model = re.sub(r"\s*\(copilot\)\s*$", "", model)
        lines.append(f"- **Tier {tier_num}** — {tier_data.get('description', '')}: {tier_data.get('role', '')}")

    return "\n".join(lines) + "\n"
