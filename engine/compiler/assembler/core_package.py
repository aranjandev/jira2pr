"""core_package — emits the platform-neutral `.jira2pr/` payload.

Both the Copilot and Aider adapters call this before laying down their own
platform-specific UX shell (`.github/` or `.aider.conf.yml`). Workflow state
always lives under `.jira2pr/state/`, never inside a platform-specific
directory, so it survives a platform switch untouched.
"""

from __future__ import annotations
from pathlib import Path

import yaml

from assembler import __version__
from assembler.registry import CanonicalRegistry
from assembler.writer import FileWriter

CORE_PREFIX = ".jira2pr"

def assemble_core(registry: CanonicalRegistry, writer: FileWriter, platform: str, runtime_dir: Path) -> None:
    """Emit the shared `.jira2pr/` payload."""
    writer.copy_tree(registry.canonical_dir / "workflows", f"{CORE_PREFIX}/workflows")
    # copy runtime integrations
    src = runtime_dir / "integrations"
    destination = f"{CORE_PREFIX}/runtime/integrations"
    assert src.exists(), f"Runtime integrations source directory does not exist: {src}"
    print(f"Copying runtime integrations from {src} to {destination}")
    writer.copy_tree(
        src,
        destination,
    )

    for schema_file in registry.artifact_schema_files():
        writer.copy(schema_file, f"{CORE_PREFIX}/artifacts/{schema_file.name}")

    writer.copy(
        registry.state_template_path(),
        f"{CORE_PREFIX}/state/workflow-state.template.yaml",
    )

    writer.put(
        f"{CORE_PREFIX}/capabilities.yaml",
        (registry.canonical_dir / "capabilities.yaml").read_text(),
    )

    writer.put(f"{CORE_PREFIX}/config.yaml", _render_config(registry, platform))

    env_example = registry.env_example_path()
    if env_example is not None:
        writer.copy(env_example, ".env.example")

def _render_config(
    registry: CanonicalRegistry,
    platform: str,
) -> str:
    agents = [
        {
            "slug": agent.slug,
            "kind": agent.kind,
            "artifact_schema": agent.artifact_schema,
        }
        for agent in registry.agents
    ]

    config = {
        "generated_by": "jira2pr",
        "generator_version": __version__,
        "platform": platform,
        "agents": agents,
    }

    return yaml.safe_dump(
        config,
        sort_keys=False,
    )