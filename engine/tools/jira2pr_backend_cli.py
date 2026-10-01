#!/usr/bin/env python3

"""Developer CLI for exercising the Jira2PR composite backend.

This tool provides a command-line interface over Jira2PRBackend.

Execution routing is owned by Jira2PRBackend:

    artifact generation   -> LiteLLM
    structured generation -> LiteLLM
    repository editing    -> Aider

The CLI contains no backend implementation logic itself.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Sequence

from runtime.backends.aider import AiderBackend
from runtime.backends.jira2pr import Jira2PRBackend
from runtime.backends.litellm_backend import LiteLLMBackend


LOGGER = logging.getLogger("jira2pr-backend-cli")

DEFAULT_TIMEOUT_SECONDS = 600


def _parse_args(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Exercise Jira2PR backend operations from the command line."
        )
    )

    parser.add_argument(
        "--operation",
        choices=(
            "artifact",
            "structured",
            "repository",
        ),
        required=True,
        help=(
            "Jira2PR backend operation. "
            "'artifact' and 'structured' use LiteLLM; "
            "'repository' uses Aider."
        ),
    )

    parser.add_argument(
        "--model",
        required=True,
        help=(
            "Model identifier, for example "
            "'github_copilot/claude-sonnet-5.5' or "
            "'ollama_chat/qwen3.8:27b'."
        ),
    )

    parser.add_argument(
        "--read",
        action="append",
        default=[],
        metavar="FILE",
        help=(
            "Read-only context file. "
            "May be specified multiple times."
        ),
    )

    parser.add_argument(
        "--output",
        metavar="FILE",
        help=(
            "Output artifact path. Required for artifact and "
            "structured operations."
        ),
    )

    parser.add_argument(
        "--edit",
        action="append",
        default=[],
        metavar="FILE",
        help=(
            "Editable repository file. Required for repository "
            "operations. May be specified multiple times."
        ),
    )

    parser.add_argument(
        "--repo-root",
        default=".",
        metavar="DIR",
        help=(
            "Repository root directory. "
            "Defaults to the current directory."
        ),
    )

    parser.add_argument(
        "--map-tokens",
        type=int,
        metavar="TOKENS",
        help=(
            "Aider repository-map token budget. "
            "Used by repository editing."
        ),
    )

    parser.add_argument(
        "--model-settings-file",
        metavar="FILE",
        help=(
            "Aider-compatible model settings YAML file. "
            "Used by both LiteLLM and Aider backends."
        ),
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        metavar="SECONDS",
        help=(
            "Backend timeout in seconds. "
            f"Default: {DEFAULT_TIMEOUT_SECONDS}."
        ),
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )

    return parser.parse_args(argv)


def _configure_logging(
    verbose: bool,
) -> None:
    """Configure CLI logging."""

    level = (
        logging.DEBUG
        if verbose
        else logging.INFO
    )

    logging.basicConfig(
        level=level,
        format=(
            "%(asctime)s | %(levelname)-8s | "
            "%(name)s | %(message)s"
        ),
    )

    # Keep dependency logging quiet even when the CLI itself is verbose.
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def _resolve_existing_file(
    value: str,
    description: str,
) -> Path:
    """Resolve and validate an existing regular file."""

    path = Path(value).expanduser().resolve()

    if not path.is_file():
        raise FileNotFoundError(
            f"{description} does not exist or is not a file: "
            f"{path}"
        )

    return path


def _resolve_repo_root(
    value: str,
) -> Path:
    """Resolve and validate the repository root."""

    path = Path(value).expanduser().resolve()

    if not path.is_dir():
        raise FileNotFoundError(
            f"Repository root does not exist: {path}"
        )

    return path


def _resolve_read_files(
    values: list[str],
) -> list[Path]:
    """Resolve read-only context files."""

    return [
        _resolve_existing_file(
            value,
            "Read-only context file",
        )
        for value in values
    ]


def _resolve_edit_files(
    values: list[str],
    repo_root: Path,
) -> list[Path]:
    """Resolve repository edit targets.

    Existing files and new file paths are both allowed, but every target
    must remain inside the repository root.
    """

    result: list[Path] = []

    for value in values:
        path = Path(value).expanduser()

        if not path.is_absolute():
            path = repo_root / path

        path = path.resolve()

        try:
            path.relative_to(repo_root)
        except ValueError as exc:
            raise ValueError(
                f"Editable file is outside repository root: {path}"
            ) from exc

        result.append(path)

    return result


def _resolve_output_file(
    value: str,
    repo_root: Path,
) -> Path:
    """Resolve an output artifact path."""

    path = Path(value).expanduser()

    if not path.is_absolute():
        path = repo_root / path

    return path.resolve()


def _build_backend(
    args: argparse.Namespace,
) -> Jira2PRBackend:
    """Construct the composite Jira2PR backend."""

    model_settings_file = None

    if args.model_settings_file:
        model_settings_file = _resolve_existing_file(
            args.model_settings_file,
            "Model settings file",
        )

    litellm_backend = LiteLLMBackend(
        model_settings_file=model_settings_file,
        timeout=args.timeout,
    )

    aider_backend = AiderBackend(
        timeout=args.timeout,
    )

    return Jira2PRBackend(
        litellm_backend=litellm_backend,
        aider_backend=aider_backend,
    )


def _run_artifact(
    *,
    backend: Jira2PRBackend,
    args: argparse.Namespace,
    repo_root: Path,
    read_files: list[Path],
) -> None:
    """Run artifact generation."""

    if not args.output:
        raise ValueError(
            "--output is required for operation 'artifact'"
        )

    if args.edit:
        raise ValueError(
            "--edit is not valid for operation 'artifact'"
        )

    output_file = _resolve_output_file(
        args.output,
        repo_root,
    )

    LOGGER.info(
        "Generating artifact: model=%s read_files=%d output=%s",
        args.model,
        len(read_files),
        output_file,
    )

    backend.produce_artifact(
        model=args.model,
        read_files=read_files,
        output_file=output_file,
        repo_root=repo_root,
        map_tokens=args.map_tokens,
    )

    LOGGER.info(
        "Artifact generated: %s",
        output_file,
    )


def _run_structured(
    *,
    backend: Jira2PRBackend,
    args: argparse.Namespace,
    repo_root: Path,
    read_files: list[Path],
) -> None:
    """Run structured-output generation."""

    if not args.output:
        raise ValueError(
            "--output is required for operation 'structured'"
        )

    if args.edit:
        raise ValueError(
            "--edit is not valid for operation 'structured'"
        )

    output_file = _resolve_output_file(
        args.output,
        repo_root,
    )

    LOGGER.info(
        "Generating structured output: "
        "model=%s read_files=%d output=%s",
        args.model,
        len(read_files),
        output_file,
    )

    backend.produce_structured(
        model=args.model,
        read_files=read_files,
        output_file=output_file,
        repo_root=repo_root,
        map_tokens=args.map_tokens,
    )

    LOGGER.info(
        "Structured output generated: %s",
        output_file,
    )


def _run_repository(
    *,
    backend: Jira2PRBackend,
    args: argparse.Namespace,
    repo_root: Path,
    read_files: list[Path],
) -> None:
    """Run repository editing."""

    if args.output:
        raise ValueError(
            "--output is not valid for operation 'repository'"
        )

    if not args.edit:
        raise ValueError(
            "At least one --edit file is required for "
            "operation 'repository'"
        )

    edit_files = _resolve_edit_files(
        args.edit,
        repo_root,
    )

    LOGGER.info(
        "Editing repository: model=%s read_files=%d edit_files=%d",
        args.model,
        len(read_files),
        len(edit_files),
    )

    backend.edit_repository(
        model=args.model,
        read_files=read_files,
        edit_files=edit_files,
        repo_root=repo_root,
        map_tokens=args.map_tokens,
    )

    LOGGER.info(
        "Repository editing completed"
    )


def main(
    argv: Sequence[str] | None = None,
) -> int:
    """CLI entry point."""

    args = _parse_args(argv)

    _configure_logging(
        args.verbose
    )

    try:
        repo_root = _resolve_repo_root(
            args.repo_root
        )

        read_files = _resolve_read_files(
            args.read
        )

        backend = _build_backend(
            args
        )

        if args.operation == "artifact":
            _run_artifact(
                backend=backend,
                args=args,
                repo_root=repo_root,
                read_files=read_files,
            )

        elif args.operation == "structured":
            _run_structured(
                backend=backend,
                args=args,
                repo_root=repo_root,
                read_files=read_files,
            )

        elif args.operation == "repository":
            _run_repository(
                backend=backend,
                args=args,
                repo_root=repo_root,
                read_files=read_files,
            )

        else:
            raise ValueError(
                f"Unsupported operation: {args.operation}"
            )

        return 0

    except Exception as exc:
        if args.verbose:
            LOGGER.exception(
                "Backend invocation failed"
            )
        else:
            LOGGER.error(
                "%s",
                exc,
            )

        return 1


if __name__ == "__main__":
    sys.exit(main())