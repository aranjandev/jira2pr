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

import yaml
from compiler.assembler.model import (
    AgentSpec,
    StateSpec,
    WorkflowSpec,
)

from runtime.artifacts.normalizer import (
    normalize_artifact,
)
from runtime.artifacts.validator import (
    validate_artifact,
)
from runtime.backends.base import LLMBackend
from runtime.capabilities import (
    CapabilityError,
    resolve,
)
from runtime.logging_config import get_logger
from runtime.workflow.context_strategy import (
    ContextStrategy,
)
from runtime.workflow.loader import (
    RuntimeProject,
)

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


def _require_worker_slug(
    state: StateSpec,
) -> str:
    """Return the state's worker slug or raise for an invalid state."""

    if state.worker is None:
        raise ValueError(
            f"State '{state.name}' has no worker to invoke"
        )

    return state.worker


def _require_agent(
    project: RuntimeProject,
    worker_slug: str,
) -> AgentSpec:
    """Return the worker's agent definition or raise if it is unknown."""

    agent = project.agent(worker_slug)

    if agent is None:
        raise ValueError(
            f"Unknown worker agent '{worker_slug}'"
        )

    return agent


def _build_worker_context(
    *,
    project: RuntimeProject,
    state: StateSpec,
    agent: AgentSpec,
    worker_slug: str,
    ticket_key: str,
    artifacts_dir: Path,
    context_strategy: ContextStrategy,
) -> list:
    """Build the read-only context supplied to a worker.
    Required runtime capabilities are materialized first. ContextStrategy then
    combines agent instructions, artifact schemas, consumed artifacts, runtime
    context files, and optional execution context.
    """

    runtime_context_files = _fetch_runtime_context(
        project,
        worker_slug,
        ticket_key,
    )

    logger.debug(
        "Resolved %d runtime context file(s) for '%s'",
        len(runtime_context_files),
        worker_slug,
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
        worker_slug,
        len(read_files),
    )

    logger.debug(
        "Read-only context files for '%s':\n%s",
        worker_slug,
        "\n".join(
            f"  - {path}"
            for path in read_files
        ),
    )

    return read_files


def _require_single_output(
    state: StateSpec,
) -> str:
    """Return the single artifact declared by an artifact-producing state."""

    if len(state.produces) != 1:
        raise ValueError(
            f"State '{state.name}' produces "
            f"{len(state.produces)} artifacts. "
            "Artifact workers currently require exactly one "
            "primary artifact per invocation."
        )

    return state.produces[0]

def _invoke_artifact_worker(
    state: StateSpec,
    worker_slug: str,
    worker,
    model: str,
    read_files: list[Path],
    artifacts_dir: Path,
    repo_root: Path,
    backend: LLMBackend,
) -> tuple[dict[str, str], dict[str, str]]:
    """Execute an artifact-producing worker."""

    output_name = _require_single_output(
        state
    )

    output_path = (
        artifacts_dir
        / output_name
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger.info(
        "Worker '%s' will produce artifact: %s",
        worker_slug,
        output_path,
    )

    try:
        backend.produce_artifact(
            model=model,
            read_files=read_files,
            output_file=output_path,
            repo_root=repo_root,
        )

        logger.info("Normalizing artifact at: %s", output_path)
        normalize_artifact(
            output_path
        )
        logger.info("Validating artifact at: %s", output_path)
        validate_artifact(
            output_path,
            repo_root=repo_root,
        )

    except Exception as exc:
        logger.exception(
            "Artifact worker '%s' failed: %s",
            worker_slug,
            exc,
        )
        raise

    artifact_content = output_path.read_text(
        encoding="utf-8"
    )

    logger.info(
        "Produced artifact '%s' (%d characters)",
        output_name,
        len(artifact_content),
    )

    action_metadata: dict[str, str] = {}

    if worker and worker.actions:
        logger.warning(
            "Worker '%s' declares runtime actions while also producing "
            "an artifact. Action metadata should be handled separately "
            "from artifact content.",
            worker_slug,
        )

    return {
        output_name: artifact_content,
    }, action_metadata


def _resolve_repository_edit_files(
    project: RuntimeProject,
    ticket_key: str,
    repo_root: Path,
) -> list:
    """Resolve repository files that a repository worker may modify.

    Editable files are derived from the validated ``plan.yaml`` artifact.

    Tasks with edit_mode ``create`` or ``modify`` are passed to Aider as
    editable files. Delete operations are intentionally excluded from this
    initial happy-path implementation.
    """

    artifacts_dir = project.artifacts_dir(
        ticket_key
    )

    plan_path = (
        artifacts_dir
        / "plan.yaml"
    )

    if not plan_path.is_file():
        raise FileNotFoundError(
            f"Repository worker requires plan.yaml: {plan_path}"
        )

    try:
        plan = yaml.safe_load(
            plan_path.read_text(
                encoding="utf-8"
            )
        )

    except yaml.YAMLError as exc:
        raise ValueError(
            f"Unable to parse plan.yaml: {exc}"
        ) from exc

    if not isinstance(plan, dict):
        raise ValueError(
            "plan.yaml must contain a YAML mapping"
        )

    tasks = plan.get("tasks")

    if not isinstance(tasks, list):
        raise ValueError(
            "plan.yaml must contain a tasks list"
        )

    edit_files: list[Path] = []

    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise ValueError(
                f"plan.yaml tasks[{index}] must be a mapping"
            )

        edit_mode = task.get(
            "edit_mode"
        )

        file_path = task.get(
            "file_path"
        )

        if edit_mode not in {
            "create",
            "modify",
        }:
            continue

        if not isinstance(file_path, str) or not file_path:
            raise ValueError(
                f"plan.yaml tasks[{index}].file_path "
                "must be a non-empty string"
            )

        target = (
            repo_root
            / file_path
        ).resolve()

        try:
            target.relative_to(
                repo_root.resolve()
            )

        except ValueError as exc:
            raise ValueError(
                f"Plan task '{file_path}' escapes repository root"
            ) from exc

        edit_files.append(
            target
        )

    # Deduplicate while preserving task order.
    edit_files = list(
        dict.fromkeys(edit_files)
    )

    if not edit_files:
        raise ValueError(
            "plan.yaml contains no create/modify tasks "
            "for repository execution"
        )

    return edit_files

def _invoke_repository_worker(
    project: RuntimeProject,
    state: StateSpec,
    ticket_key: str,
    worker_slug: str,
    model: str,
    read_files: list[Path],
    repo_root: Path,
    backend: LLMBackend,
) -> tuple[dict[str, str], dict[str, str]]:
    """Execute a worker whose output is repository state.

    Repository-editing workers do not produce workflow artifacts. Editable
    repository files are derived from the validated implementation plan and
    passed explicitly to the backend.

    The coder is currently the primary repository-editing worker.
    """

    logger.info(
        "Worker '%s' produces no artifact; using repository editing mode",
        worker_slug,
    )

    edit_files = _resolve_repository_edit_files(
        project=project,
        ticket_key=ticket_key,
        repo_root=repo_root,
    )

    logger.info(
        "Worker '%s' may edit %d repository file(s)",
        worker_slug,
        len(edit_files),
    )

    logger.debug(
        "Editable repository files for '%s':\n%s",
        worker_slug,
        "\n".join(
            f"  - {path}"
            for path in edit_files
        ),
    )

    try:
        backend.edit_repository(
            model=model,
            read_files=read_files,
            edit_files=edit_files,
            repo_root=repo_root,
        )

    except Exception as exc:
        logger.exception(
            "Repository worker '%s' failed: %s",
            worker_slug,
            exc,
        )
        raise

    # Repository-editing workers currently produce no workflow artifact.
    produced: dict[str, str] = {}

    # Runtime action metadata can be added later when repository workers
    # require post-execution actions.
    action_metadata: dict[str, str] = {}

    return produced, action_metadata

def invoke_worker(
    project: RuntimeProject,
    workflow: WorkflowSpec,
    state: StateSpec,
    ticket_key: str,
    backend: LLMBackend,
    context_strategy: ContextStrategy | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    """Execute the worker assigned to one workflow state.

    The workflow determines required artifact inputs and outputs. Runtime
    capabilities are materialized before invocation, and ContextStrategy
    assembles the worker's read-only execution context.

    Artifact-producing workers write their declared workflow artifact.
    Repository-editing workers modify repository files instead.

    Artifact normalization and deterministic validation happen before an
    artifact is returned to the workflow executor.

    Returns:
        produced_artifacts:
            Mapping of produced artifact name to final contents. Empty for
            repository-editing workers.

        action_metadata:
            Structured metadata required by runtime actions. Empty when no
            runtime actions are declared.
    """
    worker_slug = _require_worker_slug(state)

    logger.info(
        "Invoking worker agent: %s for state: %s",
        worker_slug,
        state.name,
    )

    agent = _require_agent(
        project,
        worker_slug,
    )

    worker = project.workers.get(worker_slug)

    model = project.model_for_agent(
        worker_slug
    )

    logger.debug(
        "Worker '%s' uses model: %s",
        worker_slug,
        model,
    )

    repo_root = project.core_dir.parent

    artifacts_dir = project.artifacts_dir(
        ticket_key
    )
    artifacts_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    context_strategy = (
        context_strategy
        or ContextStrategy()
    )

    read_files = _build_worker_context(
        project=project,
        state=state,
        agent=agent,
        worker_slug=worker_slug,
        ticket_key=ticket_key,
        artifacts_dir=artifacts_dir,
        context_strategy=context_strategy,
    )

    if state.produces:
        return _invoke_artifact_worker(
            state=state,
            worker_slug=worker_slug,
            worker=worker,
            model=model,
            read_files=read_files,
            artifacts_dir=artifacts_dir,
            repo_root=repo_root,
            backend=backend,
        )

    return _invoke_repository_worker(
        project=project,
        state=state,
        ticket_key=ticket_key,
        worker_slug=worker_slug,
        model=model,
        read_files=read_files,
        repo_root=repo_root,
        backend=backend,
    )