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

import json
import re
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
    ArtifactValidationError,
    validate_artifact,
)
from runtime.backends.base import BackendInvocationError, LLMBackend
from runtime.capabilities import (
    CapabilityError,
    resolve,
)
from runtime.logging_config import get_logger
from runtime.workflow.context_strategy import (
    ContextStrategy,
)
from runtime.workflow.feedback import WorkerOutputError, feedback_path
from runtime.workflow.loader import (
    RuntimeProject,
)
from runtime.workflow.task_scope import capture_scope, revert_out_of_scope

_PR_ACTIONS_BLOCK_RE = re.compile(
    r"```pr-actions\s*\n"
    r"(?P<content>.*?)"
    r"\n```\s*$",
    re.DOTALL,
)

logger = get_logger("workflow.worker_invoker")

from dataclasses import dataclass


@dataclass(frozen=True)
class RepositoryTask:
    id: str
    kind: str # "implementation" or "test"
    file_path: str
    edit_mode: str
    instructions: str
    dependencies: tuple[str, ...]
    verifies: tuple[str, ...] = ()
   
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
        ticket_key=ticket_key,
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
    project: RuntimeProject,
    workflow: WorkflowSpec,
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

    output_name = _require_single_output(state)

    output_path = artifacts_dir / output_name

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger.info(
        "Worker '%s' will produce artifact: %s",
        worker_slug,
        output_path,
    )

    execution_mode = (
        "planning"
        if worker_slug == "planner"
        else "artifact"
    )

    map_tokens = project.map_tokens_for(
        execution_mode
    )

    logger.debug(
        "Worker '%s' execution mode: %s, map_tokens: %s",
        worker_slug,
        execution_mode,
        map_tokens,
    )

    try:
        backend.produce_artifact(
            model=model,
            read_files=read_files,
            output_file=output_path,
            repo_root=repo_root,
            map_tokens=map_tokens,
        )

        logger.info(
            "Normalizing artifact at: %s",
            output_path,
        )

        normalize_artifact(
            output_path
        )

        logger.info(
            "Validating artifact at: %s",
            output_path,
        )

        validate_artifact(
            output_path,
            repo_root=repo_root,
        )

    except ArtifactValidationError as exc:
        logger.warning(
            "Artifact validation failed for worker '%s': %s",
            worker_slug,
            exc,
        )

        raise WorkerOutputError(
            source="artifact-validation",
            reason=str(exc),
        ) from exc

    except Exception:
        logger.exception(
            "Artifact worker '%s' failed",
            worker_slug,
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

    if worker_slug == "pr-author":
        action_metadata = _extract_pr_action_metadata(
            output_path
        )

        logger.debug(
            "Worker '%s' action metadata: %s",
            worker_slug,
            action_metadata,
        )

    return {
        output_name: artifact_content,
    }, action_metadata


def _parse_tasks(
    raw_tasks: list[dict],
    kind: str,
) -> list[RepositoryTask]:
    """Convert validated plan entries into RepositoryTask objects."""

    tasks: list[RepositoryTask] = []

    for raw_task in raw_tasks:
        verifies = (
            tuple(raw_task["verifies"])
            if kind == "test"
            else ()
        )

        tasks.append(
            RepositoryTask(
                id=raw_task["id"].strip(),
                kind=kind,
                file_path=raw_task["file_path"].strip(),
                edit_mode=raw_task["edit_mode"],
                instructions=raw_task["instructions"].strip(),
                dependencies=tuple(raw_task["dependencies"]),
                verifies=verifies,
            )
        )

    return tasks


def _load_repository_tasks(
    project: RuntimeProject,
    ticket_key: str,
) -> list[RepositoryTask]:
    """Load repository-editing tasks from the validated plan.yaml."""

    plan_path = (
        project.artifacts_dir(ticket_key)
        / "plan.yaml"
    )

    if not plan_path.is_file():
        raise FileNotFoundError(
            f"Repository worker requires plan.yaml: {plan_path}"
        )

    try:
        data = yaml.safe_load(
            plan_path.read_text(
                encoding="utf-8"
            )
        )
    except yaml.YAMLError as exc:
        raise ValueError(
            f"Unable to parse plan.yaml: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise TypeError(
            "plan.yaml must contain a YAML mapping"
        )

    implementation_tasks = _parse_tasks(
        data.get("tasks"),
        kind="implementation",
    )

    test_tasks = _parse_tasks(
        data.get("tests"),
        kind="test",
    )

    return implementation_tasks + test_tasks


def _check_task_dependencies(
    *,
    task: RepositoryTask,
    completed_tasks: set[str],
) -> None:
    """Ensure all dependencies for a repository task have completed."""

    missing = [
        dependency
        for dependency in task.dependencies
        if dependency not in completed_tasks
    ]

    if missing:
        raise RuntimeError(
            f"Task '{task.id}' cannot execute because dependencies "
            f"have not completed: {', '.join(missing)}"
        )


def _resolve_task_target(
    *,
    task: RepositoryTask,
    repo_root: Path,
) -> Path:
    """Resolve the validated repository target for a task."""

    target = (
        repo_root.resolve()
        / task.file_path
    ).resolve()

    if task.edit_mode == "create":
        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    if task.edit_mode == "delete":
        raise NotImplementedError(
            f"Task '{task.id}' uses edit_mode=delete; "
            "delete tasks are not supported yet"
        )

    return target


_RESUMABLE_FEEDBACK_SOURCES = frozenset({"llm-error", "empty-diff", "out-of-scope-edit"})


def _resume_task_id(context_dir: Path, state_name: str, task_ids: list[str]) -> str | None:
    """Return the task to resume at, or None to run every task.

    Only task-level failures resume. Review findings and fix-pass results
    change the work across tasks, so those re-run the whole plan.
    """
    path = feedback_path(context_dir, state_name)
    if not path.is_file():
        return None

    data = json.loads(path.read_text(encoding="utf-8"))
    resume_from = data.get("resume_from")
    if data.get("source") not in _RESUMABLE_FEEDBACK_SOURCES or resume_from is None:
        return None
    if resume_from not in task_ids:
        logger.warning(
            "Feedback resumes at task %s, which is not in the plan; running all tasks",
            resume_from,
        )
        return None
    return resume_from


def _has_verification_feedback(context_dir: Path, state_name: str) -> bool:
    """True when pending feedback reports failed tests or lint.

    Only that feedback goes to the test-repair mode. Review findings and
    attempt failures (llm-error, empty-diff) need the normal coder edit path,
    because a test-repair run has nothing to fix when tests already pass.
    """
    path = feedback_path(context_dir, state_name)
    if not path.is_file():
        return False
    return json.loads(path.read_text(encoding="utf-8")).get("source") == "verification"


def _invoke_fix_pass(
    *,
    project: RuntimeProject,
    worker_slug: str,
    tasks: list[RepositoryTask],
    read_files: list[Path],
    repo_root: Path,
    model: str,
    map_tokens: int | None,
    backend: LLMBackend,
) -> None:
    """Run one feedback-driven fix over every plan-authorized file.

    Used when the state is re-entered with failure feedback (failing tests,
    or review findings). The feedback file is already part of ``read_files``.
    The backend decides how to make the attempt. The runtime re-verifies
    afterwards and owns the attempt budget.
    """
    verification = project.backend_config.get("verification", {})

    edit_files = list(
        dict.fromkeys(
            _resolve_task_target(task=task, repo_root=repo_root)
            for task in tasks
        )
    )

    logger.info(
        "Worker '%s' running feedback fix over %d file(s)",
        worker_slug,
        len(edit_files),
    )

    scope = capture_scope(repo_root)

    try:
        backend.fix_repository(
            model=model,
            read_files=read_files,
            edit_files=edit_files,
            repo_root=repo_root,
            test_command=verification.get("test_command", ""),
            lint_command=verification.get("lint_command", ""),
            map_tokens=map_tokens,
        )
    except Exception:
        revert_out_of_scope(scope, allowed=set(edit_files))
        raise

    out_of_scope = revert_out_of_scope(scope, allowed=set(edit_files))
    if out_of_scope:
        raise WorkerOutputError(
            source="out-of-scope-edit",
            reason=(
                "The fix may edit only plan-authorized files. "
                f"It also changed {', '.join(out_of_scope)}; those changes were reverted."
            ),
        )


def _write_task_context(
    project: RuntimeProject,
    workflow: WorkflowSpec,
    state: StateSpec,
    ticket_key: str,
    task: RepositoryTask,
) -> Path:
    """Write focused read-only context for one repository-editing task."""

    context_dir = project.context_dir(ticket_key)
    context_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = context_dir / f"coder-task-{task.id}.yaml"

    data = {
        "workflow": workflow.name,
        "state": state.name,
        "task": {
            "id": task.id,
            "kind": task.kind,
            "file_path": task.file_path,
            "edit_mode": task.edit_mode,
            "instructions": task.instructions,
            "dependencies": list(task.dependencies),
            "verifies": list(task.verifies),
        },
    }

    path.write_text(
        yaml.safe_dump(
            data,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    logger.debug(
        "Coder task context written to: %s",
        path,
    )

    return path


def _build_task_read_files(
    *,
    read_files: list[Path],
    task_context_path: Path,
) -> list[Path]:
    """Build focused read-only context for one repository-editing task.

    The full ``plan.yaml`` is removed because the runtime has already selected
    the task being executed. The small task-specific context file replaces it,
    reducing model context and discouraging the coder from implementing later
    tasks prematurely.
    """

    task_read_files: list[Path] = []

    for path in read_files:
        if path.name == "plan.yaml":
            continue

        task_read_files.append(path)

    task_read_files.append(task_context_path)

    # Remove duplicates while preserving order.
    seen: set[Path] = set()
    result: list[Path] = []

    for path in task_read_files:
        resolved = path.resolve()

        if resolved in seen:
            continue

        seen.add(resolved)
        result.append(path)

    return result


def _invoke_repository_worker(
    project: RuntimeProject,
    workflow: WorkflowSpec,
    state: StateSpec,
    ticket_key: str,
    worker_slug: str,
    worker,
    model: str,
    read_files: list[Path],
    repo_root: Path,
    backend: LLMBackend,
) -> tuple[dict[str, str], dict[str, str]]:
    """Execute a repository-editing worker one plan task at a time.

    Repository workers do not produce workflow artifacts. Instead, the
    validated ``plan.yaml`` is loaded and each implementation task is executed
    sequentially.

    Each task operates on exactly one editable repository file. The worker
    receives:

    - its normal read-only execution context
    - a small task-specific context file
    - exactly one editable repository file

    Task dependencies are checked before execution.

    The implementation remains a single workflow state; task-by-task execution
    is a backend/runtime strategy within that state.
    """
    logger.info(
        "Worker '%s' produces no artifact; using task-based repository editing mode",
        worker_slug,
    )

    tasks = _load_repository_tasks(
        project=project,
        ticket_key=ticket_key,
    )

    logger.info(
        "Worker '%s' will execute %d repository task(s)",
        worker_slug,
        len(tasks),
    )

    map_tokens = project.map_tokens_for("repository")
    logger.debug(
        "Worker '%s' map_tokens for repository editing: %s",
        worker_slug,
        map_tokens,
    )

    completed_tasks: set[str] = set()

    if _has_verification_feedback(
        project.context_dir(ticket_key=ticket_key),
        state.name,
    ):
        _invoke_fix_pass(
            project=project,
            worker_slug=worker_slug,
            tasks=tasks,
            read_files=read_files,
            repo_root=repo_root,
            model=model,
            map_tokens=map_tokens,
            backend=backend,
        )

        return {}, {}

    resume_task = _resume_task_id(
        project.context_dir(ticket_key=ticket_key),
        state.name,
        [task.id for task in tasks],
    )
    skipping = resume_task is not None
    if skipping:
        logger.info(
            "Resuming at task %s; earlier tasks keep their edits from the previous attempt",
            resume_task,
        )

    for task in tasks:
        if skipping:
            if task.id == resume_task:
                skipping = False
            else:
                completed_tasks.add(task.id)
                logger.info(
                    "Skipping task %s: completed in an earlier attempt",
                    task.id,
                )
                continue

        _check_task_dependencies(
            task=task,
            completed_tasks=completed_tasks,
        )

        target_path = _resolve_task_target(
            task=task,
            repo_root=repo_root,
        )

        task_context_path = _write_task_context(
            project=project,
            workflow=workflow,
            state=state,
            ticket_key=ticket_key,
            task=task,
        )

        task_read_files = _build_task_read_files(
            read_files=read_files,
            task_context_path=task_context_path,
        )

        logger.info(
            "Executing repository task %s: %s %s",
            task.id,
            task.edit_mode,
            task.file_path,
        )

        logger.debug(
            "Task %s read-only context:\n%s",
            task.id,
            "\n".join(
                f"  - {path}"
                for path in task_read_files
            ),
        )

        logger.debug(
            "Task %s editable file: %s",
            task.id,
            target_path,
        )

        scope = capture_scope(repo_root)
        before_task = _snapshot_files([target_path])

        try:
            backend.edit_repository(
                model=model,
                read_files=task_read_files,
                edit_files=[target_path],
                repo_root=repo_root,
                map_tokens=map_tokens,
            )

        except BackendInvocationError as exc:
            revert_out_of_scope(scope, allowed={target_path})
            raise WorkerOutputError(
                source="llm-error",
                reason=f"Task {task.id} failed: coder backend call failed: {exc}",
                resume_from=task.id,
            ) from exc

        except Exception:
            revert_out_of_scope(scope, allowed={target_path})
            logger.exception(
                "Repository task %s failed for worker '%s'",
                task.id,
                worker_slug,
            )
            raise

        out_of_scope = revert_out_of_scope(scope, allowed={target_path})
        if out_of_scope:
            raise WorkerOutputError(
                source="out-of-scope-edit",
                reason=(
                    f"Task {task.id} may edit only {task.file_path}. "
                    f"It also changed {', '.join(out_of_scope)}; those changes were reverted."
                ),
                resume_from=task.id,
            )

        # A task that names a file must change that file. Checking here stops
        # the attempt at the first no-op task instead of after the whole plan.
        if _snapshot_files([target_path]) == before_task:
            raise WorkerOutputError(
                source="empty-diff",
                reason=(
                    f"Task {task.id} made no changes to "
                    f"{task.file_path} in this attempt."
                ),
                resume_from=task.id,
            )

        completed_tasks.add(task.id)

        logger.info(
            "Repository task %s completed successfully",
            task.id,
        )

    logger.info(
        "Worker '%s' completed all %d repository task(s)",
        worker_slug,
        len(tasks),
    )

    # Repository-editing workers currently produce no workflow artifacts.
    produced: dict[str, str] = {}

    # Action metadata can be introduced later if repository-editing workers
    # require post-execution actions.
    action_metadata: dict[str, str] = {}

    return produced, action_metadata


def _extract_pr_action_metadata(
    artifact_path: Path,
) -> dict[str, str]:
    """Extract action metadata from the trailing pr-actions block.

    The PR description remains normal Markdown. Runtime action parameters
    are read from the final fenced block:

        ```pr-actions
        commit_message: "feat: example"
        pr_title: "Example PR"
        ```

    commit_message is always required.

    pr_title is optional because it may be omitted when updating an
    existing pull request.
    """

    content = artifact_path.read_text(
        encoding="utf-8",
    )

    match = _PR_ACTIONS_BLOCK_RE.search(
        content
    )

    if match is None:
        raise WorkerOutputError(
            source="artifact-validation",
            reason=(
                "pr-description.md must end with a "
                "```pr-actions metadata block"
            ),
        )

    raw_metadata = match.group(
        "content"
    )

    try:
        metadata = yaml.safe_load(
            raw_metadata
        )
    except yaml.YAMLError as exc:
        raise WorkerOutputError(
            source="artifact-validation",
            reason=(
                "Unable to parse pr-actions metadata: "
                f"{exc}"
            ),
        ) from exc

    if not isinstance(metadata, dict):
        raise WorkerOutputError(
            source="artifact-validation",
            reason=(
                "pr-actions metadata must contain a YAML mapping"
            ),
        )

    commit_message = metadata.get(
        "commit_message"
    )

    if (
        not isinstance(commit_message, str)
        or not commit_message.strip()
    ):
        raise WorkerOutputError(
            source="artifact-validation",
            reason=(
                "pr-actions metadata must contain a "
                "non-empty commit_message"
            ),
        )

    action_metadata = {
        "commit_message": commit_message.strip(),
    }

    pr_title = metadata.get(
        "pr_title"
    )

    if pr_title is not None:
        if (
            not isinstance(pr_title, str)
            or not pr_title.strip()
        ):
            raise WorkerOutputError(
                source="artifact-validation",
                reason=(
                    "pr_title must be a non-empty string "
                    "when present"
                ),
            )

        action_metadata["pr_title"] = (
            pr_title.strip()
        )

    return action_metadata

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
            project=project,
            workflow=workflow,
            state=state,
            worker_slug=worker_slug,
            worker=worker,
            model=model,
            read_files=read_files,
            artifacts_dir=artifacts_dir,
            repo_root=repo_root,
            backend=backend,
        )

    return _invoke_coder_attempt(
        project=project,
        workflow=workflow,
        state=state,
        ticket_key=ticket_key,
        worker_slug=worker_slug,
        worker=worker,
        model=model,
        read_files=read_files,
        repo_root=repo_root,
        backend=backend,
    )


def _snapshot_files(paths: list[Path]) -> dict[Path, bytes | None]:
    """Return each file's bytes, or None when it does not exist."""
    return {path: path.read_bytes() if path.is_file() else None for path in paths}


def _invoke_coder_attempt(
    *,
    project: RuntimeProject,
    workflow: WorkflowSpec,
    state: StateSpec,
    ticket_key: str,
    worker_slug: str,
    worker,
    model: str,
    read_files: list[Path],
    repo_root: Path,
    backend: LLMBackend,
) -> tuple[dict[str, str], dict[str, str]]:
    """Run one repository-editing attempt and classify its outcome.

    Two outcomes count as a failed attempt, regardless of backend:
    - the backend raised BackendInvocationError (timeout, process exit,
      provider error), reported as ``llm-error``;
    - no plan task changed its file (task path), or the fix pass changed
      nothing, reported as ``empty-diff``. This is a deterministic check on
      file contents.
    """
    tasks = _load_repository_tasks(
        project=project,
        ticket_key=ticket_key,
    )

    target_paths = list(
        dict.fromkeys(
            _resolve_task_target(task=task, repo_root=repo_root)
            for task in tasks
        )
    )

    before = _snapshot_files(target_paths)

    try:
        result = _invoke_repository_worker(
            project=project,
            workflow=workflow,
            state=state,
            ticket_key=ticket_key,
            worker_slug=worker_slug,
            worker=worker,
            model=model,
            read_files=read_files,
            repo_root=repo_root,
            backend=backend,
        )
    except BackendInvocationError as exc:
        raise WorkerOutputError(
            source="llm-error",
            reason=f"Coder backend call failed: {exc}",
        ) from exc

    if _snapshot_files(target_paths) == before:
        raise WorkerOutputError(
            source="empty-diff",
            reason=(
                "The coder made no changes to the plan-authorized "
                "files in this attempt."
            ),
        )

    return result