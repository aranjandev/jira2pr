"""jira2pr CLI - assemble platform packages and drive workflow execution.

Subcommands:
    init    Generate a platform-specific Jira2PR package.
    check   Dry-run init; exit 1 if generated output would change.
    run     Start a workflow for a ticket using the Jira2PR runtime.
    resume  Resume an in-progress workflow from persisted state.
    status  Show the status of a workflow.
    list    List all known workflow states in a target repository.

Platform targets:
    runtime  Jira2PR runtime-driven execution. This is the default.
    copilot  GitHub Copilot agent-driven execution.

Runtime execution uses the composite Jira2PR backend:

    content generation   -> LiteLLM
    structured output    -> LiteLLM
    repository editing   -> Aider
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from assembler.platforms import PLATFORMS
from assembler.registry import CanonicalRegistry
from assembler.validator import CanonicalValidationError, validate
from assembler.writer import FileWriter
from runtime.logging_config import get_logger, setup_logging

logger = get_logger("cli")

DEFAULT_PLATFORM = "runtime"
DEFAULT_BACKEND = "jira2pr"


def _default_canonical_dir() -> Path:
    """Locate canonical definitions from an install or development checkout."""

    bundled = (
        Path(__file__).resolve().parent
        / "_canonical"
    )

    if bundled.is_dir():
        return bundled

    dev_checkout = (
        Path(__file__).resolve().parent.parent.parent
        / "canonical"
    )

    if dev_checkout.is_dir():
        return dev_checkout

    raise SystemExit(
        "Could not locate canonical/ definitions. "
        "Pass --canonical-dir explicitly."
    )


def _resolve_canonical_dir(
    arg: str | None,
) -> Path:
    """Resolve the canonical definitions directory."""

    if arg:
        return Path(arg).resolve()

    return _default_canonical_dir()


def _load_and_validate(
    canonical_dir_arg: str | None,
    platform: str,
) -> CanonicalRegistry | None:
    """Load and validate canonical definitions for a platform."""

    registry = CanonicalRegistry.load(
        _resolve_canonical_dir(
            canonical_dir_arg
        )
    )

    for warning in registry.warnings:
        print(
            f"WARNING: {warning}",
            file=sys.stderr,
        )

    try:
        validate(
            registry,
            platform,
        )

    except CanonicalValidationError as exc:
        for error in exc.errors:
            print(
                f"ERROR: {error}",
                file=sys.stderr,
            )

        return None

    return registry


def cmd_init(
    args: argparse.Namespace,
) -> int:
    """Generate a platform-specific Jira2PR package."""

    registry = _load_and_validate(
        args.canonical_dir,
        args.platform,
    )

    if registry is None:
        return 1

    writer = FileWriter(
        Path(args.target_dir).resolve(),
        check=False,
    )

    PLATFORMS[
        args.platform
    ]().assemble(
        registry,
        writer,
    )

    writer.finalize()

    print(
        writer.summary()
    )

    return 0


def cmd_check(
    args: argparse.Namespace,
) -> int:
    """Check whether generated platform assets are up to date."""

    registry = _load_and_validate(
        args.canonical_dir,
        args.platform,
    )

    if registry is None:
        return 1

    writer = FileWriter(
        Path(args.target_dir).resolve(),
        check=True,
    )

    PLATFORMS[
        args.platform
    ]().assemble(
        registry,
        writer,
    )

    writer.finalize()

    print(
        writer.summary()
    )

    return (
        0
        if writer.all_ok
        else 1
    )


def _make_backend(
    name: str,
):
    """Create a workflow execution backend.

    The normal Jira2PR backend is composite:

        produce_artifact()   -> LiteLLM
        produce_structured() -> LiteLLM
        edit_repository()    -> Aider

    The mock backend remains available for testing.
    """

    if name == "mock":
        from runtime.backends.mock import MockBackend

        return MockBackend()

    if name == "jira2pr":
        from runtime.backends.aider import AiderBackend
        from runtime.backends.jira2pr import Jira2PRBackend
        from runtime.backends.litellm_backend import LiteLLMBackend

        litellm_backend = LiteLLMBackend()

        aider_backend = AiderBackend()

        return Jira2PRBackend(
            litellm_backend=litellm_backend,
            aider_backend=aider_backend,
        )

    raise SystemExit(
        f"Unknown backend: {name}"
    )


def cmd_run(
    args: argparse.Namespace,
) -> int:
    """Start a workflow for a ticket."""

    from runtime.workflow.executor import WorkflowExecutor
    from runtime.workflow.loader import RuntimeProject

    target_dir = Path(
        args.target_dir
    ).resolve()

    log_level = (
        "DEBUG"
        if args.debug
        else "INFO"
    )

    setup_logging(
        log_dir=(
            target_dir
            / ".jira2pr"
            / "logs"
        ),
        log_level=log_level,
    )

    logger.info(
        "Starting workflow: %s for ticket: %s",
        args.workflow,
        args.ticket,
    )

    logger.debug(
        "Target directory: %s",
        target_dir,
    )

    logger.debug(
        "Execution backend: %s",
        args.backend,
    )

    try:
        project = RuntimeProject.load(
            target_dir
        )

        logger.info(
            "Project loaded successfully"
        )

        backend = _make_backend(
            args.backend
        )

        executor = WorkflowExecutor(
            project,
            backend,
        )

        logger.info(
            "Executor initialized with backend: %s",
            backend.__class__.__name__,
        )

        state = executor.start(
            args.workflow,
            args.ticket,
        )

        logger.info(
            "Workflow completed with status: %s",
            state.status,
        )

        _print_state(
            state
        )

        return (
            0
            if state.status == "completed"
            else 1
        )

    except Exception:
        logger.exception(
            "Workflow failed with exception"
        )

        return 1


def cmd_resume(
    args: argparse.Namespace,
) -> int:
    """Resume an in-progress workflow."""

    from runtime.workflow.executor import WorkflowExecutor
    from runtime.workflow.loader import RuntimeProject

    target_dir = Path(
        args.target_dir
    ).resolve()

    log_level = (
        "DEBUG"
        if args.debug
        else "INFO"
    )

    setup_logging(
        log_dir=(
            target_dir
            / ".jira2pr"
            / "logs"
        ),
        log_level=log_level,
    )

    logger.info(
        "Resuming workflow for ticket: %s",
        args.ticket,
    )

    logger.debug(
        "Target directory: %s",
        target_dir,
    )

    logger.debug(
        "Execution backend: %s",
        args.backend,
    )

    try:
        project = RuntimeProject.load(
            target_dir
        )

        logger.info(
            "Project loaded successfully"
        )

        backend = _make_backend(
            args.backend
        )

        executor = WorkflowExecutor(
            project,
            backend,
        )

        logger.info(
            "Executor initialized with backend: %s",
            backend.__class__.__name__,
        )

        state = executor.resume(
            args.ticket
        )

        logger.info(
            "Workflow resumed and completed with status: %s",
            state.status,
        )

        _print_state(
            state
        )

        return (
            0
            if state.status == "completed"
            else 1
        )

    except Exception:
        logger.exception(
            "Workflow resume failed with exception"
        )

        return 1


def cmd_status(
    args: argparse.Namespace,
) -> int:
    """Show workflow state for a ticket."""

    from runtime.workflow.loader import RuntimeProject
    from runtime.workflow.state_manager import StateManager

    target_dir = Path(
        args.target_dir
    ).resolve()

    log_level = (
        "DEBUG"
        if args.debug
        else "INFO"
    )

    setup_logging(
        log_dir=(
            target_dir
            / ".jira2pr"
            / "logs"
        ),
        log_level=log_level,
    )

    logger.info(
        "Getting status for ticket: %s",
        args.ticket,
    )

    try:
        project = RuntimeProject.load(
            target_dir
        )

        state = StateManager(
            project.core_dir
        ).load(
            args.ticket
        )

        logger.info(
            "Status retrieved: %s",
            state.status,
        )

        _print_state(
            state
        )

        return 0

    except Exception:
        logger.exception(
            "Failed to get status"
        )

        return 1


def cmd_list(
    args: argparse.Namespace,
) -> int:
    """List tickets with persisted workflow state."""

    from runtime.workflow.loader import RuntimeProject
    from runtime.workflow.state_manager import TICKET_KEY_RE

    target_dir = Path(
        args.target_dir
    ).resolve()

    log_level = (
        "DEBUG"
        if args.debug
        else "INFO"
    )

    setup_logging(
        log_dir=(
            target_dir
            / ".jira2pr"
            / "logs"
        ),
        log_level=log_level,
    )

    logger.info(
        "Listing all known workflows"
    )

    try:
        project = RuntimeProject.load(
            target_dir
        )

        state_dir = project.state_dir()

        if state_dir.is_dir():
            tickets = sorted(
                path.stem
                for path in state_dir.glob("*.yaml")
                if TICKET_KEY_RE.match(
                    path.stem
                )
            )
        else:
            tickets = []

        logger.info(
            "Found %d workflow(s)",
            len(tickets),
        )

        if not tickets:
            print(
                "No workflows found."
            )

            return 0

        for ticket in tickets:
            print(
                ticket
            )

        return 0

    except Exception:
        logger.exception(
            "Failed to list workflows"
        )

        return 1


def _print_state(
    state,
) -> None:
    """Print workflow state in a concise human-readable form."""

    print(
        f"workflow:       {state.workflow}"
    )

    print(
        f"work_item:      {state.work_item}"
    )

    print(
        f"status:         {state.status}"
    )

    print(
        f"current_state:  {state.current_state}"
    )

    print(
        f"retry_counts:   {state.retry_counts}"
    )

    print(
        "history:"
    )

    for entry in state.history:
        print(
            f"  - {entry['state']} "
            f"(attempt {entry['attempt']}): "
            f"{entry['outcome']}"
        )


def build_parser() -> argparse.ArgumentParser:
    """Build the Jira2PR command-line parser."""

    parser = argparse.ArgumentParser(
        prog="jira2pr",
        description=(
            "jira2pr - JIRA ticket to Pull Request, "
            "multi-agent, multi-platform."
        ),
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging.",
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    # --------------------------------------------------------------
    # init
    # --------------------------------------------------------------

    p_init = sub.add_parser(
        "init",
        help="Generate a platform-specific Jira2PR package.",
    )

    p_init.add_argument(
        "--platform",
        default=DEFAULT_PLATFORM,
        choices=list(PLATFORMS.keys()),
        help=(
            "Target platform to generate "
            f"(default: {DEFAULT_PLATFORM})."
        ),
    )

    p_init.add_argument(
        "--target-dir",
        default=".",
    )

    p_init.add_argument(
        "--canonical-dir",
        default=None,
    )

    p_init.set_defaults(
        func=cmd_init
    )

    # --------------------------------------------------------------
    # check
    # --------------------------------------------------------------

    p_check = sub.add_parser(
        "check",
        help="Dry-run init; exit 1 if generated output would change.",
    )

    p_check.add_argument(
        "--platform",
        default=DEFAULT_PLATFORM,
        choices=list(PLATFORMS.keys()),
        help=(
            "Target platform to check "
            f"(default: {DEFAULT_PLATFORM})."
        ),
    )

    p_check.add_argument(
        "--target-dir",
        default=".",
    )

    p_check.add_argument(
        "--canonical-dir",
        default=None,
    )

    p_check.set_defaults(
        func=cmd_check
    )

    # --------------------------------------------------------------
    # run
    # --------------------------------------------------------------

    p_run = sub.add_parser(
        "run",
        help="Start a runtime-driven workflow for a ticket.",
    )

    p_run.add_argument(
        "workflow"
    )

    p_run.add_argument(
        "ticket"
    )

    p_run.add_argument(
        "--backend",
        default=DEFAULT_BACKEND,
        choices=[
            "jira2pr",
            "mock",
        ],
        help=(
            "Execution backend "
            f"(default: {DEFAULT_BACKEND})."
        ),
    )

    p_run.add_argument(
        "--target-dir",
        default=".",
    )

    p_run.set_defaults(
        func=cmd_run
    )

    # --------------------------------------------------------------
    # resume
    # --------------------------------------------------------------

    p_resume = sub.add_parser(
        "resume",
        help="Resume an in-progress runtime workflow.",
    )

    p_resume.add_argument(
        "ticket"
    )

    p_resume.add_argument(
        "--backend",
        default=DEFAULT_BACKEND,
        choices=[
            "jira2pr",
            "mock",
        ],
        help=(
            "Execution backend "
            f"(default: {DEFAULT_BACKEND})."
        ),
    )

    p_resume.add_argument(
        "--target-dir",
        default=".",
    )

    p_resume.set_defaults(
        func=cmd_resume
    )

    # --------------------------------------------------------------
    # status
    # --------------------------------------------------------------

    p_status = sub.add_parser(
        "status",
        help="Show the status of a workflow.",
    )

    p_status.add_argument(
        "ticket"
    )

    p_status.add_argument(
        "--target-dir",
        default=".",
    )

    p_status.set_defaults(
        func=cmd_status
    )

    # --------------------------------------------------------------
    # list
    # --------------------------------------------------------------

    p_list = sub.add_parser(
        "list",
        help="List all known workflow states.",
    )

    p_list.add_argument(
        "--target-dir",
        default=".",
    )

    p_list.set_defaults(
        func=cmd_list
    )

    return parser


def main(
    argv: list[str] | None = None,
) -> None:
    """CLI entry point."""

    args = build_parser().parse_args(
        argv
    )

    sys.exit(
        args.func(args)
    )


if __name__ == "__main__":
    main()