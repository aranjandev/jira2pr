"""Cross-reference validation for the canonical DSL.

This is the "validate" stage of the compiler pipeline (parse -> validate ->
project). The old assembler performed zero cross-reference checking, which is
how the skills/prompts/instructions drift went unnoticed until the assembler
crashed outright. Every check here raises with the offending file + key path
so failures are actionable.
"""

from __future__ import annotations

from assembler.registry import CanonicalRegistry


class CanonicalValidationError(Exception):
    """Raised when one or more cross-reference checks fail.

    ``errors`` contains one human-readable message per violation, each
    prefixed with the offending file (and key path, where applicable).
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


def validate(registry: CanonicalRegistry, platform: str) -> None:
    """Validate *registry* for internal consistency and platform support.

    Raises ``CanonicalValidationError`` with every violation found (not just
    the first) so a single run surfaces the whole list of problems.
    """
    errors: list[str] = []
    agent_slugs = {a.slug for a in registry.agents}
    worker_slugs = {a.slug for a in registry.agents if a.kind == "worker"}

    for workflow in registry.workflows.values():
        src = workflow.source_path

        if workflow.initial_state not in workflow.states:
            errors.append(
                f"{src}: initial_state '{workflow.initial_state}' is not a defined state"
            )

        for state in workflow.states.values():
            key = f"{src}: states.{state.name}"

            if state.terminal:
                if state.outcome not in ("success", "escalated"):
                    errors.append(
                        f"{key}.outcome: terminal state must declare outcome "
                        f"'success' or 'escalated' (found: {state.outcome!r})"
                    )
                continue

            if state.worker is None:
                errors.append(f"{key}.worker: non-terminal state must declare a worker")
            elif state.worker not in worker_slugs:
                errors.append(
                    f"{key}.worker: '{state.worker}' is not a known worker agent "
                    f"(known: {sorted(worker_slugs)})"
                )

            if state.success_criteria is not None and (
                state.success_criteria not in registry.success_criteria.criteria
            ):
                errors.append(
                    f"{key}.validation.success_criteria: '{state.success_criteria}' not "
                    f"found in workflows/shared/success-criteria.yaml"
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
                        f"{key}.transitions.{label}: target state '{target}' is not defined"
                    )

        _check_reachability(workflow, errors)

    for slug, binding in registry.workers.items():
        if slug not in agent_slugs:
            errors.append(
                f"workflows/shared/workers.yaml: worker '{slug}' is not a known agent"
            )
        for cap_id in binding.runtime_context:
            _check_capability(registry, cap_id, expected_type="context", errors=errors, where=f"workers.{slug}.runtime_context")
        for cap_id in binding.actions:
            _check_capability(registry, cap_id, expected_type="action", errors=errors, where=f"workers.{slug}.actions")
        for target in binding.can_delegate:
            if target not in agent_slugs:
                errors.append(
                    f"workflows/shared/workers.yaml: workers.{slug}.can_delegate: "
                    f"'{target}' is not a known agent"
                )

    for agent in registry.agents:
        if agent.artifact_schema is None:
            continue
        path = registry.canonical_dir / "artifacts" / agent.artifact_schema
        if not path.exists():
            errors.append(
                f"agents/_registry.yaml: agents.{agent.slug}.artifact_schema: "
                f"'{agent.artifact_schema}' does not exist under canonical/artifacts/"
            )

        model = registry.model_for_tier(agent.model_tier, platform)
        if model.startswith("Tier-") and "unknown for" in model:
            errors.append(
                f"model-tiers.yaml: tier {agent.model_tier} has no model defined "
                f"for platform '{platform}' (required by agent '{agent.slug}')"
            )

    if errors:
        raise CanonicalValidationError(errors)


def _check_capability(
    registry: CanonicalRegistry,
    cap_id: str,
    expected_type: str,
    errors: list[str],
    where: str,
) -> None:
    cap = registry.capabilities.get(cap_id)
    if cap is None:
        errors.append(
            f"workflows/shared/workers.yaml: {where}: capability '{cap_id}' is not "
            f"defined in capabilities.yaml"
        )
        return
    if cap.type != expected_type:
        errors.append(
            f"workflows/shared/workers.yaml: {where}: capability '{cap_id}' has "
            f"type '{cap.type}', expected '{expected_type}'"
        )


def _check_reachability(workflow, errors: list[str]) -> None:
    seen: set[str] = set()
    stack = [workflow.initial_state]
    while stack:
        name = stack.pop()
        if name in seen or name not in workflow.states:
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

    unreachable = set(workflow.states) - seen
    for name in sorted(unreachable):
        errors.append(
            f"{workflow.source_path}: state '{name}' is unreachable from "
            f"initial_state '{workflow.initial_state}'"
        )
