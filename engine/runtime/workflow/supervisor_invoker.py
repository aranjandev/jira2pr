"""Invokes the supervisor to evaluate a worker's output against success criteria."""

from __future__ import annotations

import re

import yaml

from assembler.model import StateSpec, WorkflowSpec
from runtime.backends.base import LLMBackend
from runtime.logging_config import get_logger
from runtime.workflow.loader import RuntimeProject

logger = get_logger("workflow.supervisor_invoker")

VALID_OUTCOMES = {"success", "failure", "escalate"}


class SupervisorOutputError(Exception):
    """Raised internally when the supervisor's response cannot be parsed."""


def invoke_supervisor(
    project: RuntimeProject,
    workflow: WorkflowSpec,
    state: StateSpec,
    ticket_key: str,
    produced: dict[str, str],
    backend: LLMBackend,
) -> dict:
    """Return ``{"outcome", "reason", "feedback", "violations"}``.

    Malformed supervisor output is treated as ``outcome="failure"`` (a broken
    evaluator response is itself evidence the state didn't succeed) rather
    than raised, so it can never crash the run outright.
    """
    logger.info(f"Invoking supervisor for state: {state.name}, workflow: {workflow.name}")
    logger.debug(f"Produced artifacts: {list(produced.keys())}")

    supervisor_agent = project.agent("supervisor")
    system_prompt = project.agent_body("supervisor")

    required_labels: tuple[str, ...] = ()
    if state.success_criteria:
        required_labels = project.success_criteria.criteria.get(state.success_criteria, ())
        logger.debug(f"Success criteria: {required_labels}")

    produced_text = "\n\n".join(f"### {name}\n\n{content}" for name, content in produced.items())
    user_prompt = (
        f"Workflow: {workflow.name}\n"
        f"State: {state.name}\n"
        f"Required success criteria labels: {', '.join(required_labels) or '(none)'}\n\n"
        f"Worker output:\n\n{produced_text}"
    )

    model = (
        project.config.get("models", {}).get(str(supervisor_agent.model_tier), "")
        if supervisor_agent
        else ""
    )
    logger.debug(f"Supervisor model: {model}")
    logger.info("Calling backend to evaluate worker output")

    try:
        raw = backend.complete(system_prompt, user_prompt, model=model)
        logger.debug(f"Supervisor response length: {len(raw)} characters")
    except Exception as e:
        logger.exception(f"Supervisor backend call failed: {e}")
        raise

    try:
        result = _parse_outcome(raw)
        logger.info(f"Supervisor evaluation result: outcome={result['outcome']}")
        logger.debug(f"Supervisor reason: {result.get('reason', 'N/A')}")
        return result
    except SupervisorOutputError as exc:
        logger.warning(f"Supervisor output parsing failed: {exc}, treating as failure")
        return {
            "outcome": "failure",
            "reason": f"Supervisor output could not be parsed: {exc}",
            "feedback": "Return only valid YAML matching the documented output schema.",
            "violations": list(required_labels),
        }


def _parse_outcome(raw: str) -> dict:
    text = _extract_yaml_block(raw)
    try:
        data = yaml.safe_load(text)
        logger.debug("Supervisor YAML parsed successfully")
    except yaml.YAMLError as exc:
        logger.error(f"YAML parsing error: {exc}")
        raise SupervisorOutputError(str(exc)) from exc

    if not isinstance(data, dict):
        logger.error(f"Expected YAML dict, got {type(data).__name__}")
        raise SupervisorOutputError("expected a YAML mapping")

    outcome = data.get("outcome")
    if outcome not in VALID_OUTCOMES:
        logger.error(f"Invalid outcome value: {outcome!r}, expected one of {VALID_OUTCOMES}")
        raise SupervisorOutputError(f"invalid outcome: {outcome!r}")

    logger.debug(f"Parsed outcome: {outcome}")
    return {
        "outcome": outcome,
        "reason": data.get("reason", ""),
        "feedback": data.get("feedback", ""),
        "violations": list(data.get("violations") or []),
    }


def _extract_yaml_block(raw: str) -> str:
    match = re.search(r"```(?:ya?ml)?\s*\n(.*?)```", raw, re.DOTALL)
    return match.group(1) if match else raw
