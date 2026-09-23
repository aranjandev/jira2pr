"""Loads workflow definitions and agent metadata from a generated `.jira2pr/` tree.

Mirrors `assembler.registry.CanonicalRegistry` but reads the *generated*
package inside a target repo (produced by `jira2pr init`) instead of the
`canonical/` source tree, using the same parsing functions from
`assembler.dsl_parser` so the schema can never diverge between compile time
and run time.
"""

from __future__ import annotations

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
from runtime.logging_config import get_logger

logger = get_logger("workflow.loader")

CORE_DIRNAME = ".jira2pr"


class WorkflowNotFoundError(Exception):
    """Raised when a requested workflow name has no definition."""


@dataclass
class RuntimeProject:
    """Everything the runtime engine needs, loaded from `<repo>/.jira2pr/`."""

    core_dir: Path
    agents: list[AgentSpec] = field(default_factory=list)
    workflows: dict[str, WorkflowSpec] = field(default_factory=dict)
    success_criteria: SuccessCriteria = field(
        default_factory=lambda: SuccessCriteria(criteria={})
    )
    workers: dict[str, WorkerBinding] = field(default_factory=dict)
    supervisor_contract: SupervisorContract | None = None
    execution_policy: ExecutionPolicy | None = None
    capabilities: dict[str, CapabilitySpec] = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, repo_root: Path) -> "RuntimeProject":
        logger.info(f"Loading RuntimeProject from {repo_root}")
        core_dir = Path(repo_root).resolve() / CORE_DIRNAME
        if not core_dir.is_dir():
            logger.error(f"{core_dir} not found")
            raise FileNotFoundError(
                f"{core_dir} not found — run `jira2pr init --platform <copilot|aider>` first."
            )

        logger.debug(f"Core directory found: {core_dir}")
        project = cls(core_dir=core_dir)

        logger.debug("Loading configuration")
        project.config = load_yaml(core_dir / "config.yaml") or {}
        logger.debug(f"Configuration loaded: {len(project.config)} top-level keys")

        logger.debug("Parsing agents")
        for item in project.config.get("agents", []):
            project.agents.append(
                AgentSpec(
                    slug=item["slug"],
                    name=item["slug"].replace("-", " "),
                    kind=item["kind"],
                    model_tier=int(item["model_tier"]),
                    description="",
                    artifact_schema=item.get("artifact_schema"),
                )
            )
        logger.info(f"Loaded {len(project.agents)} agents")

        logger.debug("Parsing workflows")
        workflows_dir = core_dir / "workflows"
        project.workflows, project.warnings = parse_workflows_dir(workflows_dir, core_dir)
        logger.info(f"Loaded {len(project.workflows)} workflows: {sorted(project.workflows.keys())}")

        logger.debug("Parsing shared workflow definitions")
        shared_dir = workflows_dir / "shared"
        project.success_criteria = parse_success_criteria(shared_dir / "success-criteria.yaml")
        logger.debug(f"Success criteria loaded: {len(project.success_criteria.criteria)} entries")

        project.workers = parse_workers(shared_dir / "workers.yaml")
        logger.debug(f"Workers loaded: {len(project.workers)} entries")

        project.supervisor_contract = parse_supervisor_contract(shared_dir / "supervisor.yaml")
        logger.debug("Supervisor contract loaded")

        project.execution_policy = parse_execution_policy(shared_dir / "execution-policy.yaml")
        logger.debug(
            f"Execution policy loaded: max_total_iterations={project.execution_policy.max_total_iterations}"
        )

        project.capabilities = parse_capabilities(core_dir / "capabilities.yaml")
        logger.debug(f"Capabilities loaded: {len(project.capabilities)} entries")

        if project.warnings:
            for warning in project.warnings:
                logger.warning(f"Project warning: {warning}")

        logger.info("RuntimeProject loaded successfully")
        return project

    def workflow(self, name: str) -> WorkflowSpec:
        try:
            logger.debug(f"Loading workflow: {name}")
            return self.workflows[name]
        except KeyError as exc:
            logger.error(f"Workflow not found: {name}")
            raise WorkflowNotFoundError(
                f"Unknown workflow '{name}'. Available: {sorted(self.workflows)}"
            ) from exc

    def agent(self, slug: str) -> AgentSpec | None:
        agent = next((a for a in self.agents if a.slug == slug), None)
        if agent:
            logger.debug(f"Found agent: {slug}")
        else:
            logger.warning(f"Agent not found: {slug}")
        return agent

    def agent_path(self, slug: str) -> Path:
        """Return the path to an agent definition."""
        path = self.core_dir / "agents" / f"{slug}.md"

        if not path.is_file():
            raise FileNotFoundError(
                f"Agent definition not found: {path}"
            )

        logger.debug(f"Agent definition for '{slug}': {path}")
        return path


    def agent_body(self, slug: str) -> str:
        """Return the contents of an agent definition."""
        return self.agent_path(slug).read_text()


    def artifact_schema_path(self, filename: str) -> Path:
        """Return the path to an artifact schema."""
        path = self.core_dir / "artifacts" / filename

        if not path.is_file():
            raise FileNotFoundError(
                f"Artifact schema not found: {path}"
            )

        logger.debug(f"Artifact schema '{filename}': {path}")
        return path


    def artifact_schema_body(self, filename: str) -> str:
        """Return the contents of an artifact schema."""
        return self.artifact_schema_path(filename).read_text()


    def artifacts_dir(self, ticket_key: str) -> Path:
        """Return the runtime artifact directory for a work item."""
        path = self.core_dir / "artifacts" / ticket_key
        logger.debug(f"Artifacts directory for {ticket_key}: {path}")
        return path


    def context_dir(self, ticket_key: str) -> Path:
        """Return the runtime context directory for a work item."""
        path = self.core_dir / "context" / ticket_key
        logger.debug(f"Context directory for {ticket_key}: {path}")
        return path


    def state_dir(self) -> Path:
        """Return the workflow-state directory."""
        path = self.core_dir / "state"
        logger.debug(f"State directory: {path}")
        return path


    def project_instructions_path(self) -> Path | None:
        """Return repository-level project instructions when available.

        AGENTS.md is the platform-neutral/default location used by the Aider
        runtime. Copilot may instead use .github/copilot-instructions.md.
        """
        repo_root = self.core_dir.parent

        candidates = [
            repo_root / "AGENTS.md",
            repo_root / ".github" / "copilot-instructions.md",
        ]

        for path in candidates:
            if path.is_file():
                logger.debug(f"Project instructions found: {path}")
                return path

        logger.debug("No project instructions found")
        return None