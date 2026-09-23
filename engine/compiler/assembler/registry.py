"""CanonicalRegistry — loads and normalizes the entire canonical/ tree.

This is the "parse" stage of the compiler pipeline (parse -> validate ->
project). It has no knowledge of any target platform; it only turns the
canonical YAML/Markdown tree into the typed model defined in
`assembler.model`, using the shared parsing functions in
`assembler.dsl_parser` (also used by the runtime engine against the
generated `.jira2pr/` tree).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from assembler.dsl_parser import (
    load_yaml,
    parse_capabilities,
    parse_execution_policy,
    parse_success_criteria,
    parse_supervisor_contract,
    parse_workers,
    parse_workflows_dir,
)
from assembler.model import (
    AgentSpec,
    CapabilitySpec,
    ExecutionPolicy,
    SuccessCriteria,
    SupervisorContract,
    WorkerBinding,
    WorkflowSpec,
)


@dataclass
class CanonicalRegistry:
    """Structured, typed representation of the entire canonical/ tree."""

    canonical_dir: Path
    agents: list[AgentSpec] = field(default_factory=list)
    workflows: dict[str, WorkflowSpec] = field(default_factory=dict)
    success_criteria: SuccessCriteria = field(
        default_factory=lambda: SuccessCriteria(criteria={})
    )
    workers: dict[str, WorkerBinding] = field(default_factory=dict)
    supervisor_contract: SupervisorContract | None = None
    execution_policy: ExecutionPolicy | None = None
    capabilities: dict[str, CapabilitySpec] = field(default_factory=dict)
    project_instructions_tpl: str = ""
    warnings: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, canonical_dir: Path) -> "CanonicalRegistry":
        """Load and normalize all canonical content from *canonical_dir*."""
        canonical_dir = canonical_dir.resolve()
        if not canonical_dir.is_dir():
            print(f"ERROR: canonical directory not found: {canonical_dir}", file=sys.stderr)
            sys.exit(1)

        reg = cls(canonical_dir=canonical_dir)
        reg._load_agents()
        reg._load_workflows()
        reg._load_shared()
        reg.capabilities = parse_capabilities(canonical_dir / "capabilities.yaml")
        reg.project_instructions_tpl = (canonical_dir / "project-instructions.md").read_text()
        return reg

    # ------------------------------------------------------------------
    # Loading helpers
    # ------------------------------------------------------------------

    def _load_agents(self) -> None:
        raw = load_yaml(self.canonical_dir / "agents" / "_registry.yaml") or {}
        for item in raw.get("agents", []):
            self.agents.append(
                AgentSpec(
                    slug=item["slug"],
                    name=item["name"],
                    kind=item["kind"],
                    description=(item.get("description") or "").strip(),
                    artifact_schema=item.get("artifact_schema"),
                )
            )

    def _load_workflows(self) -> None:
        workflows_dir = self.canonical_dir / "workflows"
        self.workflows, warnings = parse_workflows_dir(workflows_dir, self.canonical_dir)
        self.warnings.extend(warnings)

    def _load_shared(self) -> None:
        shared_dir = self.canonical_dir / "workflows" / "shared"
        self.success_criteria = parse_success_criteria(shared_dir / "success-criteria.yaml")
        self.workers = parse_workers(shared_dir / "workers.yaml")
        self.supervisor_contract = parse_supervisor_contract(shared_dir / "supervisor.yaml")
        self.execution_policy = parse_execution_policy(shared_dir / "execution-policy.yaml")

    # ------------------------------------------------------------------
    # Content accessors
    # ------------------------------------------------------------------

    def agent(self, slug: str) -> AgentSpec | None:
        return next((a for a in self.agents if a.slug == slug), None)

    def agent_body(self, slug: str) -> str:
        """Read the canonical agent markdown body."""
        path = self.canonical_dir / "agents" / f"{slug}.md"
        if not path.exists():
            raise FileNotFoundError(f"Canonical agent file not found: {path}")
        return path.read_text()

    def artifact_schema_files(self) -> list[Path]:
        """List all artifact schema markdown files (excludes REGISTRY.md)."""
        d = self.canonical_dir / "artifacts"
        if not d.is_dir():
            return []
        return sorted(p for p in d.glob("*.md") if p.name != "REGISTRY.md")

    def artifact_schema_body(self, filename: str) -> str:
        path = self.canonical_dir / "artifacts" / filename
        if not path.exists():
            raise FileNotFoundError(f"Canonical artifact schema not found: {path}")
        return path.read_text()

    def state_template_path(self) -> Path:
        return self.canonical_dir / "state" / "workflow-state.template.yaml"

    def workflow_shared_dir(self) -> Path:
        return self.canonical_dir / "workflows" / "shared"

    def platform_extras_dir(self, platform: str) -> Path | None:
        """Return the platform-extras/<platform>/ directory, or None."""
        d = self.canonical_dir / "platform-extras" / platform
        return d if d.is_dir() else None

    def env_example_path(self) -> Path | None:
        """Return the .env.example path, or None."""
        p = self.canonical_dir / ".env.example"
        return p if p.is_file() else None

    def platform_models(
        self,
        platform: str,
    ) -> dict[str, str]:
        extras = self.platform_extras_dir(platform)

        if extras is None:
            return {}

        path = extras / "models.yaml"

        if not path.is_file():
            return {}

        raw = load_yaml(path) or {}
        models = raw.get("models", {})

        if not isinstance(models, dict):
            raise ValueError(
                f"Expected 'models' mapping in {path}"
            )

        return {
            str(slug): str(model)
            for slug, model in models.items()
        }