"""Cross-reference validation for the canonical DSL.

This is the "validate" stage of the compiler pipeline:

    parse -> validate -> project

Validation checks relationships across canonical definitions and the selected
platform configuration so invalid packages fail during compilation rather
than later at runtime.

Every check contributes a human-readable error containing the offending file
and key path where possible. All discovered violations are reported together.
"""

from __future__ import annotations

from assembler.registry import CanonicalRegistry


class CanonicalValidationError(Exception):
    """Raised when one or more canonical validation checks fail.

    ``errors`` contains one human-readable message per violation.
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


def validate(
    registry: CanonicalRegistry,
    platform: str,
) -> None:
    """Validate canonical definitions and platform configuration.

    Checks include:

    - workflow state references
    - worker references
    - transition targets
    - success criteria references
    - capability references and types
    - delegation targets
    - artifact schemas
    - workflow reachability
    - platform-specific agent model mappings

    Raises:
        CanonicalValidationError:
            If any validation errors are found.
    """

    errors: list[str] = []

    agent_slugs = {
        agent.slug
        for agent in registry.agents
    }

    worker_slugs = {
        agent.slug
        for agent in registry.agents
        if agent.kind == "worker"
    }

    # ------------------------------------------------------------------
    # Execution policy
    # ------------------------------------------------------------------

    if (
        registry.execution_policy is not None
        and registry.execution_policy.max_total_iterations <= 0
    ):
        errors.append(
            "workflows/shared/execution-policy.yaml: "
            "retry.max_total_iterations must be a positive integer"
        )

    # ------------------------------------------------------------------
    # Workflows
    # ------------------------------------------------------------------

    for workflow in registry.workflows.values():
        src = workflow.source_path

        if workflow.initial_state not in workflow.states:
            errors.append(
                f"{src}: initial_state '{workflow.initial_state}' "
                "is not a defined state"
            )

        if (
            workflow.max_total_iterations is not None
            and workflow.max_total_iterations <= 0
        ):
            errors.append(
                f"{src}: retry.max_total_iterations must be a "
                f"positive integer "
                f"(found: {workflow.max_total_iterations})"
            )

        for state in workflow.states.values():
            key = f"{src}: states.{state.name}"

            if state.terminal:
                if state.outcome not in (
                    "success",
                    "escalated",
                ):
                    errors.append(
                        f"{key}.outcome: terminal state must declare "
                        f"outcome 'success' or 'escalated' "
                        f"(found: {state.outcome!r})"
                    )

                continue

            if state.worker is None:
                errors.append(
                    f"{key}.worker: non-terminal state must "
                    "declare a worker"
                )

            elif state.worker not in worker_slugs:
                errors.append(
                    f"{key}.worker: '{state.worker}' is not a known "
                    f"worker agent (known: {sorted(worker_slugs)})"
                )

            if (
                state.success_criteria is not None
                and state.success_criteria
                not in registry.success_criteria.criteria
            ):
                errors.append(
                    f"{key}.validation.success_criteria: "
                    f"'{state.success_criteria}' not found in "
                    "workflows/shared/success-criteria.yaml"
                )

            for label, target in (
                ("success", state.transitions.success),
                ("failure", state.transitions.failure),
                ("escalate", state.transitions.escalate),
            ):
                if target is None:
                    continue

                if target not in workflow.states:
                    errors.append(
                        f"{key}.transitions.{label}: target state "
                        f"'{target}' is not defined"
                    )

        _check_reachability(
            workflow,
            errors,
        )

    # ------------------------------------------------------------------
    # Worker bindings
    # ------------------------------------------------------------------

    for slug, binding in registry.workers.items():
        if slug not in agent_slugs:
            errors.append(
                "workflows/shared/workers.yaml: "
                f"worker '{slug}' is not a known agent"
            )

        for cap_id in binding.runtime_context:
            _check_capability(
                registry,
                cap_id,
                expected_type="context",
                errors=errors,
                where=f"workers.{slug}.runtime_context",
            )

        for cap_id in binding.actions:
            _check_capability(
                registry,
                cap_id,
                expected_type="action",
                errors=errors,
                where=f"workers.{slug}.actions",
            )

        for target in binding.can_delegate:
            if target not in agent_slugs:
                errors.append(
                    "workflows/shared/workers.yaml: "
                    f"workers.{slug}.can_delegate: "
                    f"'{target}' is not a known agent"
                )

    # ------------------------------------------------------------------
    # Artifact schemas
    # ------------------------------------------------------------------

    for agent in registry.agents:
        if agent.artifact_schema is None:
            continue

        path = (
            registry.canonical_dir
            / "artifacts"
            / agent.artifact_schema
        )

        if not path.is_file():
            errors.append(
                "agents/_registry.yaml: "
                f"agents.{agent.slug}.artifact_schema: "
                f"'{agent.artifact_schema}' does not exist under "
                "canonical/artifacts/"
            )

    # ------------------------------------------------------------------
    # Platform model mapping
    # ------------------------------------------------------------------

    _check_platform_models(
        registry,
        platform,
        errors,
    )

    # ------------------------------------------------------------------
    # Final result
    # ------------------------------------------------------------------

    if errors:
        raise CanonicalValidationError(errors)


def _check_platform_models(
    registry: CanonicalRegistry,
    platform: str,
    errors: list[str],
) -> None:
    """Validate agent-to-model mappings for the selected platform."""

    try:
        models = registry.platform_models(platform)

    except (
        FileNotFoundError,
        ValueError,
    ) as exc:
        errors.append(
            f"platform-extras/{platform}/models.yaml: {exc}"
        )
        return

    # Aider uses the Python workflow runtime instead of the orchestrator
    # agent, so the orchestrator does not require an Aider model mapping.
    required_agents = {
        agent.slug
        for agent in registry.agents
        if not (
            platform == "aider"
            and agent.kind == "orchestrator"
        )
    }

    configured_agents = set(models)

    missing = sorted(
        required_agents - configured_agents
    )

    for slug in missing:
        errors.append(
            f"platform-extras/{platform}/models.yaml: "
            f"models.{slug}: no model configured for agent '{slug}'"
        )

    # Catch blank mappings as well as missing keys.
    for slug in sorted(
        required_agents & configured_agents
    ):
        model = models.get(slug)

        if not isinstance(model, str) or not model.strip():
            errors.append(
                f"platform-extras/{platform}/models.yaml: "
                f"models.{slug}: model must be a non-empty string"
            )


def _check_capability(
    registry: CanonicalRegistry,
    cap_id: str,
    expected_type: str,
    errors: list[str],
    where: str,
) -> None:
    """Validate a worker capability reference."""

    cap = registry.capabilities.get(cap_id)

    if cap is None:
        errors.append(
            "workflows/shared/workers.yaml: "
            f"{where}: capability '{cap_id}' is not defined "
            "in capabilities.yaml"
        )
        return

    if cap.type != expected_type:
        errors.append(
            "workflows/shared/workers.yaml: "
            f"{where}: capability '{cap_id}' has type "
            f"'{cap.type}', expected '{expected_type}'"
        )


def _check_reachability(
    workflow,
    errors: list[str],
) -> None:
    """Validate that every workflow state is reachable."""

    seen: set[str] = set()
    stack = [
        workflow.initial_state,
    ]

    while stack:
        name = stack.pop()

        if (
            name in seen
            or name not in workflow.states
        ):
            continue

        seen.add(name)

        state = workflow.states[name]

        for target in (
            state.transitions.success,
            state.transitions.failure,
            state.transitions.escalate,
        ):
            if target is not None:
                stack.append(target)

    unreachable = (
        set(workflow.states) - seen
    )

    for name in sorted(unreachable):
        errors.append(
            f"{workflow.source_path}: state '{name}' is "
            f"unreachable from initial_state "
            f"'{workflow.initial_state}'"
        )