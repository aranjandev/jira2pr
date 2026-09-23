"""Invokes a worker agent for one workflow state and writes its produced artifacts.

Consumed artifacts are read from `.jira2pr/artifacts/<TICKET-KEY>/` and folded
into the user prompt; produced artifacts are written back there.

Runtime context capabilities (e.g., jira.read, git.status) are resolved
deterministically via subprocess and injected into the prompt before the
LLM backend is invoked.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from assembler.model import StateSpec, WorkflowSpec
from runtime.backends.base import LLMBackend
from runtime.capabilities import resolve, CapabilityError
from runtime.logging_config import get_logger
from runtime.workflow.loader import RuntimeProject

logger = get_logger("workflow.worker_invoker")


def _fetch_runtime_context(
    project: RuntimeProject,
    worker_slug: str,
    ticket_key: str,
) -> str:
    """Fetch runtime context capabilities and return formatted text for the prompt.

    Context capabilities are script-backed deterministic integrations (e.g.,
    jira.read, git.status) that are invoked as subprocesses before the LLM
    backend is called.

    Returns: concatenated "### Runtime Context: {cap_id}\n\n{stdout}" blocks,
    or empty string if no context capabilities are defined for this worker.
    """
    worker = project.workers.get(worker_slug)
    if not worker or not worker.runtime_context:
        logger.debug(f"Worker '{worker_slug}' has no runtime context capabilities")
        return ""

    repo_root = project.core_dir.parent
    parts = []

    for cap_id in worker.runtime_context:
        cap = project.capabilities.get(cap_id)
        if not cap:
            logger.warning(f"Capability '{cap_id}' not found in project.capabilities")
            continue

        # Skip native capabilities (no script to run)
        if cap.binding.kind != "script":
            logger.debug(f"Skipping native capability '{cap_id}'")
            continue

        # Skip action capabilities (only fetch context capabilities)
        if cap.type != "context":
            logger.debug(f"Skipping action capability '{cap_id}'")
            continue

        # Build capability-specific params
        params: dict[str, str] = {}
        if cap_id == "jira.read":
            params["ticket_key_or_url"] = ticket_key
        # git.status requires no parameters

        logger.info(f"Resolving runtime context: {cap_id}")
        try:
            argv = resolve(cap, str(repo_root), params)
            logger.debug(f"Running: {' '.join(argv)}")
            result = subprocess.run(
                argv,
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                logger.error(f"Context capability '{cap_id}' failed: {result.stderr.strip()}")
                raise RuntimeError(
                    f"Capability '{cap_id}' exited {result.returncode}: {result.stderr.strip()}"
                )
            parts.append(f"### Runtime Context: {cap_id}\n\n{result.stdout}")
            logger.info(f"Context '{cap_id}' retrieved successfully")
        except CapabilityError as e:
            logger.error(f"Failed to resolve capability '{cap_id}': {e}")
            raise RuntimeError(f"Failed to resolve capability '{cap_id}': {e}") from e
        except subprocess.TimeoutExpired:
            logger.error(f"Context capability '{cap_id}' timed out after 60s")
            raise RuntimeError(f"Capability '{cap_id}' timed out") from None

    return "\n\n".join(parts)


def invoke_worker(
    project: RuntimeProject,
    workflow: WorkflowSpec,
    state: StateSpec,
    ticket_key: str,
    backend: LLMBackend,
) -> tuple[dict[str, str], dict[str, str]]:
    """Run the worker for *state*, returning (produced_artifacts, action_metadata).

    produced_artifacts: {produced_filename: content} for files the state
    expected to `produce`. States with zero `produces` entries return an empty dict.

    action_metadata: dict with keys like 'commit_message', 'pr_title', or empty
    dict if the worker has no actions. Extracted from trailing pr-actions block
    in the response if the worker declares actions.

    The worker's raw response is written to each produced artifact file with
    the pr-actions block (if present) stripped out, so artifacts stay clean.
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

    # Fetch runtime context (deterministic integrations like jira.read, git.status)
    context_text = _fetch_runtime_context(project, state.worker, ticket_key)
    if context_text:
        logger.debug(f"Fetched runtime context: {len(context_text)} characters")

    # Build user prompt: ticket key, consumed artifacts, and fetched context
    prompt_parts = [f"Ticket: {ticket_key}", f"Workflow: {workflow.name}", f"State: {state.name}"]
    if consumed_text:
        prompt_parts.append(consumed_text)
    if context_text:
        prompt_parts.append(context_text)
    user_prompt = "\n\n".join(prompt_parts)

    model = project.config.get("models", {}).get(str(agent.model_tier), "")
    logger.info(f"Calling backend with model: {model}")

    try:
        response = backend.complete(system_prompt, user_prompt, model=model)
        logger.info(f"Worker response received, length: {len(response)} characters")
    except Exception as e:
        logger.exception(f"Worker invocation failed: {e}")
        raise

    # Extract and validate action metadata if the worker has actions
    action_metadata: dict[str, str] = {}
    response_for_artifacts = response
    worker = project.workers.get(state.worker)
    if worker and worker.actions:
        logger.debug(f"Worker has {len(worker.actions)} action(s), parsing pr-actions block")
        try:
            from runtime.workflow.action_executor import parse_pr_actions, strip_pr_actions_block
            action_metadata = parse_pr_actions(response)
            response_for_artifacts = strip_pr_actions_block(response)
            logger.info(f"Parsed action metadata: {list(action_metadata.keys())}")
        except Exception as e:
            logger.exception(f"Failed to parse pr-actions block: {e}")
            raise

    produced: dict[str, str] = {}
    if state.produces:
        logger.info(f"Writing {len(state.produces)} produced artifact(s)")
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        for name in state.produces:
            path = artifacts_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(response_for_artifacts)
            produced[name] = response_for_artifacts
            logger.debug(f"Wrote artifact: {path}")
    else:
        logger.debug("State produces no artifacts")

    return produced, action_metadata


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
