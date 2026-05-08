"""CanonicalRegistry — loads all YAML registries and canonical content from the canonical/ tree."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None  # type: ignore[assignment]


def load_yaml(path: Path) -> Any:
    """Load a YAML file.  Requires pyyaml."""
    text = path.read_text()
    if yaml is not None:
        return yaml.safe_load(text)
    raise SystemExit(
        "pyyaml is not installed.  Install it (`pip install pyyaml`) or run "
        "this script inside a container where it is available."
    )


@dataclass
class CanonicalRegistry:
    """Structured representation of the entire canonical/ tree."""

    canonical_dir: Path
    agents: list[dict] = field(default_factory=list)
    skills: list[dict] = field(default_factory=list)
    instructions: list[dict] = field(default_factory=list)
    prompts: list[dict] = field(default_factory=list)
    model_tiers: dict = field(default_factory=dict)
    project_instructions_tpl: str = ""

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, canonical_dir: Path) -> "CanonicalRegistry":
        """Load all registries and templates from *canonical_dir*."""
        canonical_dir = canonical_dir.resolve()
        if not canonical_dir.is_dir():
            print(f"ERROR: canonical directory not found: {canonical_dir}", file=sys.stderr)
            sys.exit(1)

        agents = load_yaml(canonical_dir / "agents" / "_registry.yaml").get("agents", [])
        skills = load_yaml(canonical_dir / "skills" / "_registry.yaml").get("skills", [])
        instructions = load_yaml(canonical_dir / "instructions" / "_registry.yaml").get("instructions", [])
        prompts = load_yaml(canonical_dir / "prompts" / "_registry.yaml").get("prompts", [])
        model_tiers = load_yaml(canonical_dir / "model-tiers.yaml")
        project_instructions_tpl = (canonical_dir / "project-instructions.md").read_text()

        return cls(
            canonical_dir=canonical_dir,
            agents=agents,
            skills=skills,
            instructions=instructions,
            prompts=prompts,
            model_tiers=model_tiers,
            project_instructions_tpl=project_instructions_tpl,
        )

    # ------------------------------------------------------------------
    # Content accessors
    # ------------------------------------------------------------------

    def agent_body(self, slug: str) -> str:
        """Read the canonical agent markdown body."""
        path = self.canonical_dir / "agents" / f"{slug}.md"
        if not path.exists():
            raise FileNotFoundError(f"Canonical agent file not found: {path}")
        return path.read_text()

    def skill_body(self, slug: str) -> str:
        """Read the canonical skill SKILL.md body."""
        path = self.canonical_dir / "skills" / slug / "SKILL.md"
        if not path.exists():
            raise FileNotFoundError(f"Canonical skill file not found: {path}")
        return path.read_text()

    def skill_scripts_dir(self, slug: str) -> Path | None:
        """Return the scripts/ directory for a skill, or None if it doesn't exist."""
        d = self.canonical_dir / "skills" / slug / "scripts"
        return d if d.is_dir() else None

    def instruction_body(self, slug: str) -> str:
        """Read the canonical instruction markdown body."""
        path = self.canonical_dir / "instructions" / f"{slug}.md"
        if not path.exists():
            raise FileNotFoundError(f"Canonical instruction file not found: {path}")
        return path.read_text()

    def prompt_body(self, slug: str) -> str:
        """Read the canonical prompt markdown body."""
        path = self.canonical_dir / "prompts" / f"{slug}.md"
        if not path.exists():
            raise FileNotFoundError(f"Canonical prompt file not found: {path}")
        return path.read_text()

    def workflow_files(self) -> list[Path]:
        """List all workflow markdown files."""
        d = self.canonical_dir / "workflows"
        return sorted(d.glob("*.md")) if d.is_dir() else []

    def state_files(self) -> list[Path]:
        """List all state/ markdown files (SCHEMA, templates — not agent-managed state files)."""
        d = self.canonical_dir / "state"
        if not d.is_dir():
            return []
        return sorted(p for p in d.glob("*.md") if not p.name.startswith("_"))

    def artifacts_files(self) -> list[Path]:
        """List all artifacts/ markdown files (SCHEMA only — not the agent-managed REGISTRY.md)."""
        d = self.canonical_dir / "artifacts"
        if not d.is_dir():
            return []
        # Exclude _registry.yaml (not .md, but defensive) and REGISTRY.md so the
        # assembler can never accidentally overwrite accumulated agent history.
        excluded = {"_", "REGISTRY.md"}
        return sorted(
            p for p in d.glob("*.md")
            if not p.name.startswith("_") and p.name != "REGISTRY.md"
        )

    def model_for_tier(self, tier: int, platform: str) -> str:
        """Look up the model name for a tier + platform combination."""
        tiers = self.model_tiers.get("tiers", {})
        tier_data = tiers.get(tier, tiers.get(str(tier), {}))
        models = tier_data.get("models", {})
        return models.get(platform, f"Tier-{tier} (unknown for {platform})")

    def platform_extras_dir(self, platform: str) -> Path | None:
        """Return the platform-extras/<platform>/ directory, or None."""
        d = self.canonical_dir / "platform-extras" / platform
        return d if d.is_dir() else None

    def env_example_path(self) -> Path | None:
        """Return the .env.example path, or None."""
        p = self.canonical_dir / ".env.example"
        return p if p.is_file() else None
