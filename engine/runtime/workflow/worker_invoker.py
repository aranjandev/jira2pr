"""Invoke worker agents for individual workflow states.

Worker execution is file-oriented.

Required context is assembled from:
- the worker's agent definition
- its artifact schema, when applicable
- artifacts declared by the workflow state's ``consumes`` field
- runtime context capabilities materialized as files
- optional repository context selected by ``ContextStrategy``

Artifact-producing workers write directly to the artifact declared by the
workflow state. Non-artifact workers, such as the coder, modify repository
state instead.

Runtime context capabilities such as ``jira.read`` and ``git.status`` are
resolved deterministically before worker invocation and materialized under
``.jira2pr/context/<TICKET-KEY>/``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from compiler.assembler.model import StateSpec, WorkflowSpec
from runtime.backends.base import LLMBackend
from runtime.capabilities import resolve, CapabilityError
from runtime.logging_config import get_logger
from runtime.workflow.loader import RuntimeProject
from runtime.workflow.context_strategy import ContextStrategy

logger = get_logger("workflow.worker_invoker")


def _fetch_runtime_context(
    project: RuntimeProject,
    worker_slug: str,
    ticket_key: str,
) -> list[Path]:
    """Resolve script-backed runtime context into read-only context files.

    Context capabilities such as ``jira.read`` and ``git.status`` are
    deterministic integrations executed before the worker is invoked.

    Their stdout is materialized under:

        .jira2pr/context/<TICKET-KEY>/

    The returned paths can then be supplied to a backend as read-only context,
    for example via Aider's ``--read`` option.

    Native capabilities are skipped here because they are fulfilled directly
    by the execution platform.

    Returns:
        Paths to context files produced by script-backed context capabilities.
    """
    worker = project.workers.get(worker_slug)
    if not worker or not worker.runtime_context:
        logger.debug(
            f"Worker '{worker_slug}' has no runtime context capabilities"
        )
        return []

    repo_root = project.core_dir.parent

    context_dir = project.context_dir(ticket_key)
    context_dir.mkdir(parents=True, exist_ok=True)

    context_files: list[Path] = []

    for cap_id in worker.runtime_context:
        cap = project.capabilities.get(cap_id)

        if cap is None:
            logger.warning(
                f"Capability '{cap_id}' not found in project.capabilities"
            )
            continue

        # Native capabilities are provided by the platform itself.
        if cap.binding.kind != "script":
            logger.debug(
                f"Skipping native context capability '{cap_id}'"
            )
            continue

        # This function only materializes context capabilities.
        if cap.type != "context":
            logger.debug(
                f"Skipping non-context capability '{cap_id}'"
            )
            continue

        params: dict[str, str] = {}

        if cap_id == "jira.read":
            params["ticket_key_or_url"] = ticket_key

        logger.info(f"Resolving runtime context: {cap_id}")

        try:
            argv = resolve(
                cap,
                str(repo_root),
                params,
            )

            logger.debug(f"Running: {' '.join(argv)}")

            result = subprocess.run(
                argv,
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

        except CapabilityError as exc:
            logger.error(
                f"Failed to resolve capability '{cap_id}': {exc}"
            )
            raise RuntimeError(
                f"Failed to resolve capability '{cap_id}': {exc}"
            ) from exc

        except subprocess.TimeoutExpired as exc:
            logger.error(
                f"Context capability '{cap_id}' timed out after 60s"
            )
            raise RuntimeError(
                f"Capability '{cap_id}' timed out"
            ) from exc

        if result.returncode != 0:
            error = result.stderr.strip()

            logger.error(
                f"Context capability '{cap_id}' failed: {error}"
            )

            raise RuntimeError(
                f"Capability '{cap_id}' exited "
                f"{result.returncode}: {error}"
            )

        # Convert a capability identifier into a stable filename.
        #
        # jira.read  -> jira-read.json
        # git.status -> git-status.txt
        filename = _context_filename(cap_id)

        context_path = context_dir / filename
        context_path.write_text(result.stdout)

        context_files.append(context_path)

        logger.info(
            f"Context '{cap_id}' materialized at {context_path}"
        )

    return context_files


def _context_filename(cap_id: str) -> str:
    """Return the runtime context filename for a capability."""

    names = {
        "jira.read": "jira-ticket.json",
        "git.status": "git-status.txt",
    }

    return names.get(
        cap_id,
        f"{cap_id.replace('.', '-')}.txt",
    )


def invoke_worker(
    project: RuntimeProject,
    workflow: WorkflowSpec,
    state: StateSpec,
    ticket_key: str,
    backend: LLMBackend,
    context_strategy: ContextStrategy | None = None,
) -> tuple[dict[str, str], dict[str, str]]:

    """Execute the worker assigned to a workflow state.

    The workflow defines required artifact dependencies through ``consumes`` and
    ``produces``. Runtime capabilities are resolved before invocation, and
    ``ContextStrategy`` selects the final read-only context presented to the
    backend.

    Artifact-producing workers use a file-oriented execution contract:

    read-only context:
        - worker agent definition
        - output artifact schema
        - consumed workflow artifacts
        - materialized runtime context
        - optional repository instructions selected by ContextStrategy

    editable output:
        - exactly one artifact declared by ``state.produces``

    The produced file is authoritative. Backend stdout is not treated as the
    artifact content.

    Workers with no produced artifact, currently primarily ``coder``, use the
    repository execution path instead. Their output is repository state rather
    than a workflow artifact.

    Returns:
        A tuple of:

        produced_artifacts:
            Mapping of produced artifact filename to final file contents.
            Empty for repository-editing workers.

        action_metadata:
            Structured metadata required by runtime actions. Empty when the
            worker declares no actions.
    """

    logger.info(
        f"Invoking worker agent: {state.worker} for state: {state.name}"
    )

    if state.worker is None:
        raise ValueError(
            f"State '{state.name}' has no worker to invoke"
        )

    context_strategy = context_strategy or ContextStrategy()

    agent = project.agent(state.worker)
    if agent is None:
        raise ValueError(
            f"Unknown worker agent '{state.worker}'"
        )

    worker = project.workers.get(state.worker)

    model = project.config.get(
        "models", {}
    ).get(str(agent.model_tier), "")

    if not model:
        raise ValueError(
            f"No model configured for tier {agent.model_tier} "
            f"(worker '{state.worker}')"
        )

    logger.debug(
        f"Worker '{state.worker}' uses model tier "
        f"{agent.model_tier}: {model}"
    )

    artifacts_dir = project.artifacts_dir(ticket_key)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Resolve execution context
    # ------------------------------------------------------------------

    runtime_context_files = _fetch_runtime_context(
        project,
        state.worker,
        ticket_key,
    )

    logger.debug(
        "Resolved %d runtime context file(s)",
        len(runtime_context_files),
    )

    read_files = context_strategy.build_read_files(
        project=project,
        state=state,
        agent=agent,
        artifacts_dir=artifacts_dir,
        runtime_context_files=runtime_context_files,
    )

    logger.info(
        "Worker '%s' context contains %d read-only file(s)",
        state.worker,
        len(read_files),
    )

    logger.debug(
        "Read-only context files:\n%s",
        "\n".join(
            f"  - {path}" for path in read_files
        ),
    )
    
    # ------------------------------------------------------------------
    # Artifact-producing workers
    # ------------------------------------------------------------------

    if state.produces:
        if len(state.produces) != 1:
            raise ValueError(
                f"State '{state.name}' produces "
                f"{len(state.produces)} artifacts. "
                "Artifact workers currently support exactly one "
                "primary artifact per invocation."
            )

        output_name = state.produces[0]
        output_path = artifacts_dir / output_name

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.info(
            f"Worker '{state.worker}' will produce: {output_path}"
        )

        # Treat the filesystem as authoritative. Backends such as
        # Aider directly edit the artifact rather than returning it
        # through stdout.
        if not output_path.is_file():
            raise RuntimeError(
                f"Worker '{state.worker}' did not produce "
                f"expected artifact: {output_path}"
            )

        artifact_content = output_path.read_text()

        if not artifact_content.strip():
            raise RuntimeError(
                f"Worker '{state.worker}' produced an empty "
                f"artifact: {output_path}"
            )

        logger.info(
            f"Produced artifact '{output_name}' "
            f"({len(artifact_content)} characters)"
        )

        produced = {
            output_name: artifact_content,
        }

        # Artifact-producing workers should generally not need
        # conversational action metadata. If actions are eventually
        # required here, model them as a separate structured output
        # rather than embedding metadata in the artifact.
        action_metadata: dict[str, str] = {}

        if worker and worker.actions:
            logger.warning(
                f"Worker '{state.worker}' declares runtime actions "
                "while also producing an artifact. Action metadata "
                "should be handled separately from artifact content."
            )

        return produced, action_metadata

    # ------------------------------------------------------------------
    # Non-artifact workers
    # ------------------------------------------------------------------
    #
    # Coder is the current primary example. Its output is repository
    # state rather than a Markdown artifact.
    #
    # This remains a separate backend execution mode and should
    # eventually become backend.edit_repository(...).
    # ------------------------------------------------------------------

    logger.info(
        f"Worker '{state.worker}' produces no artifact; "
        "using repository execution mode"
    )

    system_prompt = project.agent_body(state.worker)

    invocation_context = [
        f"Ticket: {ticket_key}",
        f"Workflow: {workflow.name}",
        f"State: {state.name}",
    ]

    # For backends that still use complete(), provide paths rather
    # than duplicating entire file contents where possible.
    if read_files:
        invocation_context.append(
            "Read-only context files:\n"
            + "\n".join(str(path) for path in read_files)
        )

    user_prompt = "\n\n".join(invocation_context)

    try:
        response = backend.complete(
            system_prompt,
            user_prompt,
            model=model,
            files=read_files,
        )
    except Exception as exc:
        logger.exception(
            f"Worker '{state.worker}' invocation failed: {exc}"
        )
        raise

    action_metadata: dict[str, str] = {}

    if worker and worker.actions:
        logger.debug(
            f"Worker '{state.worker}' declares "
            f"{len(worker.actions)} runtime action(s)"
        )

        try:
            from runtime.workflow.action_executor import (
                parse_pr_actions,
            )

            action_metadata = parse_pr_actions(response)

            logger.info(
                "Parsed action metadata: %s",
                list(action_metadata),
            )

        except Exception as exc:
            logger.exception(
                f"Failed to parse action metadata: {exc}"
            )
            raise

    return {}, action_metadata

