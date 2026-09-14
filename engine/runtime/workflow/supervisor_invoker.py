"""Invokes the supervisor to evaluate a worker's output against success criteria."""

from __future__ import annotations

import re

import yaml

from assembler.model import StateSpec, WorkflowSpec
from runtime.backends.base import LLMBackend
from runtime.workflow.loader import RuntimeProject

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
    supervisor_agent = project.agent("supervisor")
    system_prompt = project.agent_body("supervisor")

    required_labels: tuple[str, ...] = ()
    if state.success_criteria:
        required_labels = project.success_criteria.criteria.get(state.success_criteria, ())

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
    raw = backend.complete(system_prompt, user_prompt, model=model)

    try:
        return _parse_outcome(raw)
    except SupervisorOutputError as exc:
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
    except yaml.YAMLError as exc:
        raise SupervisorOutputError(str(exc)) from exc
    if not isinstance(data, dict):
        raise SupervisorOutputError("expected a YAML mapping")
    outcome = data.get("outcome")
    if outcome not in VALID_OUTCOMES:
        raise SupervisorOutputError(f"invalid outcome: {outcome!r}")
    return {
        "outcome": outcome,
        "reason": data.get("reason", ""),
        "feedback": data.get("feedback", ""),
        "violations": list(data.get("violations") or []),
    }


def _extract_yaml_block(raw: str) -> str:
    match = re.search(r"```(?:ya?ml)?\s*\n(.*?)```", raw, re.DOTALL)
    return match.group(1) if match else raw
