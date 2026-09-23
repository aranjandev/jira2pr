"""Optional context selection policy for worker invocations.

Worker context has three sources:

1. Workflow-required artifacts
   Declared through a state's ``consumes`` field. These are mandatory and
   must always be provided to the worker.

2. Worker-required runtime context
   Declared through the worker's ``runtime_context`` capabilities. These are
   resolved by the runtime and are also mandatory.

3. Optional execution context
   Additional information such as repository-level project instructions
   (for example, ``AGENTS.md``). ``ContextStrategy`` determines whether this
   context is useful enough to include for a particular worker.

The strategy exists primarily to control context size and avoid supplying
irrelevant information to models with limited context budgets.

A ContextStrategy may add or omit optional execution context, but it must
never remove workflow-declared artifacts or required runtime capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from compiler.assembler.model import AgentSpec, StateSpec
    from runtime.workflow.loader import RuntimeProject


@dataclass(frozen=True)
class ContextStrategy:
    """Select optional context for a worker invocation."""

    # Workers that materially depend on repository conventions.
    project_instruction_workers: frozenset[str] = frozenset(
        {
            "planner",
            "coder",
            "reviewer",
            "pr-author",
        }
    )

    def include_project_instructions(
        self,
        worker_slug: str,
    ) -> bool:
        """Return whether repository-level instructions should be supplied."""
        return worker_slug in self.project_instruction_workers

    def build_read_files(
        self,
        *,
        project: "RuntimeProject",
        state: "StateSpec",
        agent: "AgentSpec",
        artifacts_dir: Path,
        runtime_context_files: list[Path],
    ) -> list[Path]:
        """Build the read-only file set for a worker.

        Required context:
        - agent definition
        - output schema, when applicable
        - workflow artifacts declared in ``consumes``
        - resolved runtime context capabilities

        Optional context:
        - project instructions for repository-aware workers
        """
        if state.worker is None:
            raise ValueError(
                f"State '{state.name}' has no worker"
            )

        read_files: list[Path] = []

        # 1. Worker behavior is always required.
        read_files.append(
            project.agent_path(state.worker)
        )

        # 2. Output schema is required for schema-backed artifacts.
        if agent.artifact_schema:
            read_files.append(
                project.artifact_schema_path(
                    agent.artifact_schema
                )
            )

        # 3. Workflow-declared artifact dependencies are authoritative.
        read_files.extend(
            _resolve_consumed_files(
                artifacts_dir,
                state.consumes,
            )
        )

        # 4. Runtime capabilities that have been materialized as files.
        read_files.extend(runtime_context_files)

        # 5. Repository-wide instructions only when useful to this worker.
        if self.include_project_instructions(state.worker):
            instructions = project.project_instructions_path()

            if instructions is not None and instructions.is_file():
                read_files.append(instructions)

        return _deduplicate_paths(read_files)


def _resolve_consumed_files(
    artifacts_dir: Path,
    consumes: tuple[str, ...],
) -> list[Path]:
    """Resolve workflow artifact patterns into concrete files."""
    paths: list[Path] = []

    for pattern in consumes:
        if "*" in pattern:
            if artifacts_dir.is_dir():
                paths.extend(
                    path
                    for path in sorted(artifacts_dir.glob(pattern))
                    if path.is_file()
                )
            continue

        path = artifacts_dir / pattern

        if path.is_file():
            paths.append(path)

    return paths


def _deduplicate_paths(
    paths: list[Path],
) -> list[Path]:
    """Remove duplicate paths while preserving order."""
    seen: set[Path] = set()
    result: list[Path] = []

    for path in paths:
        resolved = path.resolve()

        if resolved in seen:
            continue

        seen.add(resolved)
        result.append(path)

    return result