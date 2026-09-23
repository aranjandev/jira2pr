"""Invoke the supervisor to evaluate a completed workflow state.

The supervisor evaluates worker output against the success criteria assigned
to the current state and produces a structured JSON decision.

Supervisor output is materialized as a file under
``.jira2pr/context/<TICKET-KEY>/``. Backend stdout is diagnostic only.

The supervisor determines an outcome:

    success | failure | escalate

The workflow definition, not the supervisor, determines which state that
outcome transitions to.
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
    """Evaluate a completed workflow state and return its supervisor decision.

    The supervisor receives:

    - supervisor agent instructions
    - supervisor contract
    - success criteria
    - artifacts produced by the worker

    The backend writes the supervisor decision to a JSON file. The resulting
    file is authoritative; backend stdout is not parsed.

    Returns:
        A dictionary containing:

        {
            "outcome": "success|failure|escalate",
            "reason": "...",
            "feedback": "...",
            "violations": [...]
        }

    Malformed supervisor output is converted to ``outcome="failure"`` so a
    broken evaluator response cannot accidentally advance the workflow.
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
    # Resolve supervisor
    # ------------------------------------------------------------------

    supervisor_agent = project.agent("supervisor")

    if supervisor_agent is None:
        raise ValueError(
            "Supervisor agent is not defined in runtime project"
        )

    model = project.model_for_agent("supervisor")

    if not model:
        raise ValueError(
            f"No model configured for supervisor tier "
            f"{model}"
        )

    logger.debug(
        "Supervisor model: %s",
        model,
    )

    # ------------------------------------------------------------------
    # Resolve success criteria
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
        "Supervisor success criteria: %s",
        required_labels,
    )

    # ------------------------------------------------------------------
    # Build supervisor read-only context
    # ------------------------------------------------------------------

    read_files: list[Path] = []

    # Supervisor behavior.
    read_files.append(
        project.agent_path("supervisor")
    )

    # Canonical supervisor contract.
    supervisor_contract_path = (
        project.core_dir
        / "workflows"
        / "shared"
        / "supervisor.yaml"
    )

    if not supervisor_contract_path.is_file():
        raise FileNotFoundError(
            f"Supervisor contract not found: "
            f"{supervisor_contract_path}"
        )

    read_files.append(
        supervisor_contract_path
    )

    # Success-criteria definitions.
    success_criteria_path = (
        project.core_dir
        / "workflows"
        / "shared"
        / "success-criteria.yaml"
    )

    if not success_criteria_path.is_file():
        raise FileNotFoundError(
            f"Success criteria not found: "
            f"{success_criteria_path}"
        )

    read_files.append(
        success_criteria_path
    )

    # The state-specific worker artifacts being evaluated.
    artifacts_dir = project.artifacts_dir(ticket_key)

    for artifact_name in produced:
        artifact_path = artifacts_dir / artifact_name

        if not artifact_path.is_file():
            raise FileNotFoundError(
                f"Produced artifact not found for supervisor "
                f"evaluation: {artifact_path}"
            )

        read_files.append(
            artifact_path
        )

    # Remove duplicates while preserving order.
    read_files = list(
        dict.fromkeys(read_files)
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

    context_dir = project.context_dir(ticket_key)

    context_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

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

    reason = data.get("reason", "")
    feedback = data.get("feedback", "")
    violations = data.get("violations", [])

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