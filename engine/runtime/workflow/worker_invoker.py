"""Invokes a worker agent for one workflow state and writes its produced artifacts.

Consumed artifacts are read from `.jira2pr/artifacts/<TICKET-KEY>/` and folded
into the user prompt; produced artifacts are written back there.
"""

from __future__ import annotations

from pathlib import Path

from assembler.model import StateSpec, WorkflowSpec
from runtime.backends.base import LLMBackend
from runtime.logging_config import get_logger
from runtime.workflow.loader import RuntimeProject

logger = get_logger("workflow.worker_invoker")


def invoke_worker(
    project: RuntimeProject,
    workflow: WorkflowSpec,
    state: StateSpec,
    ticket_key: str,
    backend: LLMBackend,
) -> dict[str, str]:
    """Run the worker for *state*, returning ``{produced_filename: content}``.

    The worker's raw response is written verbatim to each file the state was
    expected to `produce`. States with zero `produces` entries (e.g.
    `implement`, which edits the repo directly rather than writing a named
    artifact) return an empty dict.
    """
    logger.info(f"Invoking worker agent: {state.worker} for state: {state.name}")

    if state.worker is None:
        logger.error(f"State '{state.name}' has no worker to invoke")
        raise ValueError(f"State '{state.name}' has no worker to invoke")

    agent = project.agent(state.worker)
    if agent is None:
        logger.error(f"Unknown worker agent '{state.worker}'")
        raise ValueError(f"Unknown worker agent '{state.worker}'")

    logger.debug(f"Worker agent model tier: {agent.model_tier}")
    system_prompt = project.agent_body(state.worker)
    if agent.artifact_schema:
        logger.debug(f"Including artifact schema: {agent.artifact_schema}")
        system_prompt += "\n\n---\n\n" + project.artifact_schema_body(agent.artifact_schema)

    artifacts_dir = project.artifacts_dir(ticket_key)
    logger.debug(f"Artifacts directory: {artifacts_dir}")
    consumed_text = _read_consumed(artifacts_dir, state.consumes)
    logger.debug(f"Consumed {len(state.consumes)} artifact(s), total content length: {len(consumed_text)}")

    user_prompt = f"Ticket: {ticket_key}\nWorkflow: {workflow.name}\nState: {state.name}\n\n{consumed_text}"

    model = project.config.get("models", {}).get(str(agent.model_tier), "")
    logger.info(f"Calling backend with model: {model}")

    try:
        response = backend.complete(system_prompt, user_prompt, model=model)
        logger.info(f"Worker response received, length: {len(response)} characters")
    except Exception as e:
        logger.exception(f"Worker invocation failed: {e}")
        raise

    produced: dict[str, str] = {}
    if state.produces:
        logger.info(f"Writing {len(state.produces)} produced artifact(s)")
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        for name in state.produces:
            path = artifacts_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(response)
            produced[name] = response
            logger.debug(f"Wrote artifact: {path}")
    else:
        logger.debug("State produces no artifacts")

    return produced


def _read_consumed(artifacts_dir: Path, consumes: tuple[str, ...]) -> str:
    parts = []
    for pattern in consumes:
        if "*" in pattern:
            if not artifacts_dir.is_dir():
                continue
            for path in sorted(artifacts_dir.glob(pattern)):
                parts.append(f"### {path.name}\n\n{path.read_text()}")
            continue
        path = artifacts_dir / pattern
        if path.exists():
            parts.append(f"### {pattern}\n\n{path.read_text()}")
    return "\n\n".join(parts)
