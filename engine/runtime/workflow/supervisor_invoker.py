"""Evaluate completed workflow states using the supervisor agent.

The supervisor receives only the evidence relevant to the current state:

- supervisor behavior
- supervisor output contract
- state-specific evaluation context
- artifacts consumed by the state
- artifacts produced by the state

The runtime resolves the state's success criteria before invocation and
materializes them into a small JSON context file. The full
``success-criteria.yaml`` is intentionally not provided to the supervisor,
which prevents criteria belonging to other workflow states from influencing
the evaluation.

Supervisor output is materialized as JSON under::

    .jira2pr/context/<TICKET-KEY>/

Backend stdout is diagnostic only.

The supervisor determines only the outcome:

    success | failure | escalate

The workflow definition determines how that outcome maps to the next state.
"""

from __future__ import annotations

import json
from pathlib import Path

from compiler.assembler.model import StateSpec, WorkflowSpec
from runtime.backends.base import LLMBackend
from runtime.logging_config import get_logger
from runtime.workflow.loader import RuntimeProject


logger = get_logger("workflow.supervisor_invoker")

VALID_OUTCOMES = {
    "success",
    "failure",
    "escalate",
}


class SupervisorOutputError(Exception):
    """Raised when supervisor output violates the expected contract."""


def invoke_supervisor(
    project: RuntimeProject,
    workflow: WorkflowSpec,
    state: StateSpec,
    ticket_key: str,
    produced: dict[str, str],
    backend: LLMBackend,
) -> dict:
    """Evaluate a completed workflow state.

    Supervisor context consists of:

    - supervisor agent instructions
    - supervisor output contract
    - current workflow/state/worker information
    - success criteria for this state only
    - artifacts consumed by this state
    - artifacts produced by this state

    The backend writes the decision to a JSON file. The filesystem result is
    authoritative; backend stdout is never parsed as supervisor output.

    Returns:
        {
            "outcome": "success|failure|escalate",
            "reason": "...",
            "feedback": "...",
            "violations": [...]
        }

    Invalid supervisor output is converted to ``failure`` so malformed
    evaluator output can never advance the workflow.
    """

    logger.info(
        "Invoking supervisor for state: %s, workflow: %s",
        state.name,
        workflow.name,
    )

    logger.debug(
        "Produced artifacts: %s",
        list(produced),
    )

    # ------------------------------------------------------------------
    # Resolve supervisor and model
    # ------------------------------------------------------------------

    supervisor_agent = project.agent("supervisor")

    if supervisor_agent is None:
        raise ValueError(
            "Supervisor agent is not defined in runtime project"
        )

    model = project.model_for_agent("supervisor")

    logger.debug(
        "Supervisor model: %s",
        model,
    )

    # ------------------------------------------------------------------
    # Resolve success criteria for this state only
    # ------------------------------------------------------------------

    required_labels: tuple[str, ...] = ()

    if state.success_criteria:
        required_labels = (
            project.success_criteria.criteria.get(
                state.success_criteria,
                (),
            )
        )

    logger.debug(
        "Supervisor success criteria '%s': %s",
        state.success_criteria,
        required_labels,
    )

    # ------------------------------------------------------------------
    # Runtime directories
    # ------------------------------------------------------------------

    artifacts_dir = project.artifacts_dir(ticket_key)

    context_dir = project.context_dir(ticket_key)
    context_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ------------------------------------------------------------------
    # Materialize state-specific supervisor context
    # ------------------------------------------------------------------

    evaluation_context_path = (
        context_dir
        / f"supervisor-{state.name}-context.json"
    )

    evaluation_context = {
        "workflow": workflow.name,
        "state": state.name,
        "worker": state.worker,
        "success_criteria_key": state.success_criteria,
        "success_criteria": list(required_labels),
    }

    evaluation_context_path.write_text(
        json.dumps(
            evaluation_context,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    logger.debug(
        "Supervisor evaluation context written to: %s",
        evaluation_context_path,
    )

    # ------------------------------------------------------------------
    # Build supervisor read-only context
    # ------------------------------------------------------------------

    read_files: list[Path] = [
        # How the supervisor behaves.
        project.agent_path("supervisor"),

        # Supervisor I/O contract.
        (
            project.core_dir
            / "workflows"
            / "shared"
            / "supervisor.yaml"
        ),

        # Current state and only its resolved success criteria.
        evaluation_context_path,
    ]

    # Validate the supervisor contract explicitly so a packaging error is
    # reported clearly before invoking the backend.
    supervisor_contract_path = read_files[1]

    if not supervisor_contract_path.is_file():
        raise FileNotFoundError(
            f"Supervisor contract not found: "
            f"{supervisor_contract_path}"
        )

    # ------------------------------------------------------------------
    # Add artifacts consumed by this state
    # ------------------------------------------------------------------
    #
    # The supervisor needs the inputs used by the worker in order to assess
    # criteria such as "requirements_covered".
    #
    # Example for the plan state:
    #
    #   requirements.md
    #   decisions/*.md
    #   plan.md
    #
    # Without requirements.md, the supervisor cannot determine whether the
    # plan actually covers the requirements.
    # ------------------------------------------------------------------

    consumed_files = _resolve_artifact_files(
        artifacts_dir,
        state.consumes,
    )

    read_files.extend(consumed_files)

    logger.debug(
        "Supervisor received %d consumed artifact(s)",
        len(consumed_files),
    )

    # ------------------------------------------------------------------
    # Add artifacts produced by this state
    # ------------------------------------------------------------------

    produced_files: list[Path] = []

    for artifact_name in produced:
        artifact_path = (
            artifacts_dir
            / artifact_name
        )

        if not artifact_path.is_file():
            raise FileNotFoundError(
                "Produced artifact not found for supervisor "
                f"evaluation: {artifact_path}"
            )

        produced_files.append(
            artifact_path
        )

    read_files.extend(produced_files)

    logger.debug(
        "Supervisor received %d produced artifact(s)",
        len(produced_files),
    )

    # Remove duplicate paths while preserving order.
    read_files = _deduplicate_paths(
        read_files
    )

    logger.info(
        "Supervisor context contains %d read-only file(s)",
        len(read_files),
    )

    logger.debug(
        "Supervisor read-only context:\n%s",
        "\n".join(
            f"  - {path}"
            for path in read_files
        ),
    )

    # ------------------------------------------------------------------
    # Structured output destination
    # ------------------------------------------------------------------

    decision_path = (
        context_dir
        / f"supervisor-{state.name}-decision.json"
    )

    logger.info(
        "Supervisor decision output: %s",
        decision_path,
    )

    # ------------------------------------------------------------------
    # Invoke supervisor
    # ------------------------------------------------------------------

    try:
        backend.produce_structured(
            model=model,
            read_files=read_files,
            output_file=decision_path,
            repo_root=project.core_dir.parent,
        )

    except Exception as exc:
        logger.exception(
            "Supervisor backend call failed: %s",
            exc,
        )
        raise

    # ------------------------------------------------------------------
    # Parse and validate decision
    # ------------------------------------------------------------------

    try:
        result = _parse_outcome_file(
            decision_path,
        )

    except SupervisorOutputError as exc:
        logger.warning(
            "Supervisor output validation failed: %s; "
            "treating state as failure",
            exc,
        )

        return {
            "outcome": "failure",
            "reason": (
                "Supervisor output could not be validated: "
                f"{exc}"
            ),
            "feedback": (
                "Return valid JSON matching the supervisor "
                "output contract."
            ),
            "violations": list(required_labels),
        }

    logger.info(
        "Supervisor evaluation result: outcome=%s",
        result["outcome"],
    )

    logger.debug(
        "Supervisor reason: %s",
        result["reason"],
    )

    return result


def _resolve_artifact_files(
    artifacts_dir: Path,
    patterns: tuple[str, ...],
) -> list[Path]:
    """Resolve workflow artifact names/globs into concrete files."""

    paths: list[Path] = []

    for pattern in patterns:
        if "*" in pattern:
            if artifacts_dir.is_dir():
                paths.extend(
                    path
                    for path in sorted(
                        artifacts_dir.glob(pattern)
                    )
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


def _parse_outcome_file(
    path: Path,
) -> dict:
    """Parse and validate a supervisor decision file."""

    if not path.is_file():
        raise SupervisorOutputError(
            f"decision file does not exist: {path}"
        )

    text = path.read_text(
        encoding="utf-8"
    ).strip()

    if not text:
        raise SupervisorOutputError(
            "decision file is empty"
        )

    try:
        data = json.loads(text)

    except json.JSONDecodeError as exc:
        raise SupervisorOutputError(
            f"invalid JSON: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise SupervisorOutputError(
            "expected a JSON object"
        )

    outcome = data.get("outcome")

    if outcome not in VALID_OUTCOMES:
        raise SupervisorOutputError(
            f"invalid outcome {outcome!r}; "
            f"expected one of {sorted(VALID_OUTCOMES)}"
        )

    reason = data.get(
        "reason",
        "",
    )

    feedback = data.get(
        "feedback",
        "",
    )

    violations = data.get(
        "violations",
        [],
    )

    if not isinstance(reason, str):
        raise SupervisorOutputError(
            "'reason' must be a string"
        )

    if not isinstance(feedback, str):
        raise SupervisorOutputError(
            "'feedback' must be a string"
        )

    if not isinstance(violations, list):
        raise SupervisorOutputError(
            "'violations' must be a list"
        )

    if not all(
        isinstance(item, str)
        for item in violations
    ):
        raise SupervisorOutputError(
            "'violations' entries must be strings"
        )

    return {
        "outcome": outcome,
        "reason": reason,
        "feedback": feedback,
        "violations": violations,
    }