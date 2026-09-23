"""jira2pr CLI — assemble platform packages and drive workflow execution.

Subcommands:
    init    Generate a platform-specific agent setup from canonical definitions.
    check   Dry-run `init`; exit 1 if the generated output would change.
    run     Start a workflow for a ticket (Aider backend only; Copilot runs via its own agent UI).
    resume  Resume an in-progress workflow from its persisted state.
    status  Show the status of a workflow.
    list    List all known workflow states in a target repo.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from assembler.platforms import PLATFORMS
from assembler.registry import CanonicalRegistry
from assembler.validator import CanonicalValidationError, validate
from assembler.writer import FileWriter
from runtime.logging_config import setup_logging, get_logger

logger = get_logger("cli")


def _default_canonical_dir() -> Path:
    """Locate canonical/: bundled with an installed package, or a sibling dev checkout."""
    bundled = Path(__file__).resolve().parent / "_canonical"
    if bundled.is_dir():
        return bundled
    dev_checkout = Path(__file__).resolve().parent.parent.parent / "canonical"
    if dev_checkout.is_dir():
        return dev_checkout
    raise SystemExit("Could not locate canonical/ definitions. Pass --canonical-dir explicitly.")


def _resolve_canonical_dir(arg: str | None) -> Path:
    return Path(arg).resolve() if arg else _default_canonical_dir()


def _load_and_validate(canonical_dir_arg: str | None, platform: str) -> CanonicalRegistry | None:
    registry = CanonicalRegistry.load(_resolve_canonical_dir(canonical_dir_arg))
    for warning in registry.warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    try:
        validate(registry, platform)
    except CanonicalValidationError as exc:
        for err in exc.errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return None
    return registry


def cmd_init(args: argparse.Namespace) -> int:
    registry = _load_and_validate(args.canonical_dir, args.platform)
    if registry is None:
        return 1

    writer = FileWriter(Path(args.target_dir).resolve(), check=False)
    PLATFORMS[args.platform]().assemble(registry, writer)
    writer.finalize()
    print(writer.summary())
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    registry = _load_and_validate(args.canonical_dir, args.platform)
    if registry is None:
        return 1

    writer = FileWriter(Path(args.target_dir).resolve(), check=True)
    PLATFORMS[args.platform]().assemble(registry, writer)
    writer.finalize()
    print(writer.summary())
    return 0 if writer.all_ok else 1


def _make_backend(name: str):
    if name == "mock":
        from runtime.backends.mock import MockBackend

        return MockBackend()
    if name == "aider":
        from runtime.backends.aider import AiderBackend

        return AiderBackend()
    raise SystemExit(f"Unknown backend: {name}")


def cmd_run(args: argparse.Namespace) -> int:
    from runtime.workflow.executor import WorkflowExecutor
    from runtime.workflow.loader import RuntimeProject

    target_dir = Path(args.target_dir).resolve()
    setup_logging(log_dir=target_dir / ".jira2pr" / "logs")

    logger.info(f"Starting workflow: {args.workflow} for ticket: {args.ticket}")
    logger.debug(f"Target directory: {target_dir}")
    logger.debug(f"Backend: {args.backend}")

    try:
        project = RuntimeProject.load(target_dir)
        logger.info("Project loaded successfully")
        executor = WorkflowExecutor(project, _make_backend(args.backend))
        logger.info(f"Executor initialized with backend: {args.backend}")
        state = executor.start(args.workflow, args.ticket)
        logger.info(f"Workflow completed with status: {state.status}")
        _print_state(state)
        return 0 if state.status == "completed" else 1
    except Exception as e:
        logger.exception(f"Workflow failed with exception: {e}")
        return 1


def cmd_resume(args: argparse.Namespace) -> int:
    from runtime.workflow.executor import WorkflowExecutor
    from runtime.workflow.loader import RuntimeProject

    target_dir = Path(args.target_dir).resolve()
    setup_logging(log_dir=target_dir / ".jira2pr" / "logs")

    logger.info(f"Resuming workflow for ticket: {args.ticket}")
    logger.debug(f"Target directory: {target_dir}")
    logger.debug(f"Backend: {args.backend}")

    try:
        project = RuntimeProject.load(target_dir)
        logger.info("Project loaded successfully")
        executor = WorkflowExecutor(project, _make_backend(args.backend))
        logger.info(f"Executor initialized with backend: {args.backend}")
        state = executor.resume(args.ticket)
        logger.info(f"Workflow resumed and completed with status: {state.status}")
        _print_state(state)
        return 0 if state.status == "completed" else 1
    except Exception as e:
        logger.exception(f"Workflow resume failed with exception: {e}")
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    from runtime.workflow.loader import RuntimeProject
    from runtime.workflow.state_manager import StateManager

    target_dir = Path(args.target_dir).resolve()
    setup_logging(log_dir=target_dir / ".jira2pr" / "logs")

    logger.info(f"Getting status for ticket: {args.ticket}")

    try:
        project = RuntimeProject.load(target_dir)
        state = StateManager(project.core_dir).load(args.ticket)
        logger.info(f"Status retrieved: {state.status}")
        _print_state(state)
        return 0
    except Exception as e:
        logger.exception(f"Failed to get status: {e}")
        return 1


def cmd_list(args: argparse.Namespace) -> int:
    from runtime.workflow.loader import RuntimeProject
    from runtime.workflow.state_manager import TICKET_KEY_RE

    target_dir = Path(args.target_dir).resolve()
    setup_logging(log_dir=target_dir / ".jira2pr" / "logs")

    logger.info("Listing all known workflows")

    try:
        project = RuntimeProject.load(target_dir)
        state_dir = project.state_dir()
        tickets = (
            sorted(p.stem for p in state_dir.glob("*.yaml") if TICKET_KEY_RE.match(p.stem))
            if state_dir.is_dir()
            else []
        )
        logger.info(f"Found {len(tickets)} workflow(s)")
        if not tickets:
            print("No workflows found.")
            return 0
        for ticket in tickets:
            print(ticket)
        return 0
    except Exception as e:
        logger.exception(f"Failed to list workflows: {e}")
        return 1


def _print_state(state) -> None:
    print(f"workflow:       {state.workflow}")
    print(f"work_item:      {state.work_item}")
    print(f"status:         {state.status}")
    print(f"current_state:  {state.current_state}")
    print(f"retry_counts:   {state.retry_counts}")
    print("history:")
    for entry in state.history:
        print(f"  - {entry['state']} (attempt {entry['attempt']}): {entry['outcome']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jira2pr", description="jira2pr — JIRA ticket to Pull Request, multi-agent, multi-platform."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Generate a platform-specific agent setup.")
    p_init.add_argument("--platform", required=True, choices=list(PLATFORMS.keys()))
    p_init.add_argument("--target-dir", default=".")
    p_init.add_argument("--canonical-dir", default=None)
    p_init.set_defaults(func=cmd_init)

    p_check = sub.add_parser("check", help="Dry-run init; exit 1 if output would change.")
    p_check.add_argument("--platform", required=True, choices=list(PLATFORMS.keys()))
    p_check.add_argument("--target-dir", default=".")
    p_check.add_argument("--canonical-dir", default=None)
    p_check.set_defaults(func=cmd_check)

    p_run = sub.add_parser("run", help="Start a workflow for a ticket.")
    p_run.add_argument("workflow")
    p_run.add_argument("ticket")
    p_run.add_argument("--backend", default="aider", choices=["aider", "mock"])
    p_run.add_argument("--target-dir", default=".")
    p_run.set_defaults(func=cmd_run)

    p_resume = sub.add_parser("resume", help="Resume an in-progress workflow.")
    p_resume.add_argument("ticket")
    p_resume.add_argument("--backend", default="aider", choices=["aider", "mock"])
    p_resume.add_argument("--target-dir", default=".")
    p_resume.set_defaults(func=cmd_resume)

    p_status = sub.add_parser("status", help="Show the status of a workflow.")
    p_status.add_argument("ticket")
    p_status.add_argument("--target-dir", default=".")
    p_status.set_defaults(func=cmd_status)

    p_list = sub.add_parser("list", help="List all known workflow states.")
    p_list.add_argument("--target-dir", default=".")
    p_list.set_defaults(func=cmd_list)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
