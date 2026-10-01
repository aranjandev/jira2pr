#!/usr/bin/env python3

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence

import yaml


LOGGER = logging.getLogger("jira2pr-backend")

DEFAULT_MODEL_SETTINGS_FILE = Path.home() / ".aider.model.settings.yml"


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Thin jira2pr backend supporting direct LiteLLM completion "
            "and Aider repository editing."
        )
    )

    parser.add_argument(
        "--backend",
        choices=("aider", "litellm"),
        required=True,
        help="Backend implementation to use.",
    )

    parser.add_argument(
        "--model",
        required=True,
        help=(
            "Model name, for example "
            "'github_copilot/claude-sonnet-5.5' or "
            "'ollama_chat/qwen3.8:27b'."
        ),
    )

    parser.add_argument(
        "--read",
        action="append",
        default=[],
        metavar="FILE",
        help="Read-only context file. May be specified multiple times.",
    )

    parser.add_argument(
        "--message-file",
        required=True,
        metavar="FILE",
        help="File containing the worker prompt.",
    )

    parser.add_argument(
        "--model-settings-file",
        metavar="FILE",
        help=(
            "Aider-compatible model settings YAML file. "
            "Defaults to ~/.aider.model.settings.yml if it exists."
        ),
    )

    parser.add_argument(
        "--edit-format",
        metavar="FORMAT",
        help="Aider edit format. Ignored by the LiteLLM backend.",
    )

    parser.add_argument(
        "--map-tokens",
        type=int,
        metavar="TOKENS",
        help=(
            "Aider repo-map token budget. Passed to Aider. "
            "Currently ignored by the LiteLLM backend."
        ),
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        metavar="SECONDS",
        help="Backend timeout in seconds. Default: 600.",
    )

    parser.add_argument(
        "--yes-always",
        action="store_true",
        help="Pass --yes-always to Aider. Ignored by LiteLLM.",
    )

    parser.add_argument(
        "--no-auto-commits",
        action="store_true",
        help="Pass --no-auto-commits to Aider. Ignored by LiteLLM.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )

    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help=(
            "Editable/output files. Aider mode passes all positional files "
            "to Aider. LiteLLM mode requires exactly one output artifact."
        ),
    )

    return parser.parse_args(argv)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    # LiteLLM can be extremely noisy at DEBUG level. Keep jira2pr's own
    # verbose logging without dumping LiteLLM internals.
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def _require_file(path_value: str | Path, description: str) -> Path:
    path = Path(path_value).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(
            f"{description} does not exist: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"{description} is not a regular file: {path}"
        )

    return path


def _read_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _resolve_model_settings_file(
    explicit_path: str | None,
) -> Path | None:
    if explicit_path:
        return _require_file(
            explicit_path,
            "Model settings file",
        )

    if DEFAULT_MODEL_SETTINGS_FILE.is_file():
        return DEFAULT_MODEL_SETTINGS_FILE.resolve()

    return None


def _load_model_settings(
    settings_path: Path | None,
) -> list[dict[str, Any]]:
    if settings_path is None:
        LOGGER.debug(
            "No model settings file found; using provider defaults."
        )
        return []

    raw = yaml.safe_load(
        settings_path.read_text(encoding="utf-8")
    )

    if raw is None:
        return []

    if not isinstance(raw, list):
        raise ValueError(
            f"Model settings file must contain a YAML list: "
            f"{settings_path}"
        )

    settings: list[dict[str, Any]] = []

    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(
                f"Model settings entry {index} in {settings_path} "
                "must be a mapping."
            )

        name = entry.get("name")

        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"Model settings entry {index} in {settings_path} "
                "must have a non-empty 'name'."
            )

        settings.append(entry)

    LOGGER.debug(
        "Loaded %d model settings entries from %s",
        len(settings),
        settings_path,
    )

    return settings


def _get_extra_params(
    model: str,
    settings: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    """
    Resolve LiteLLM extra parameters using Aider-compatible model settings.

    Aider supports a special 'aider/extra_params' entry whose extra_params
    apply to every model. Model-specific extra_params are then applied on
    top, overriding global values.

    If duplicate entries exist, later entries win.
    """

    extra_params: dict[str, Any] = {}

    for entry in settings:
        if entry.get("name") != "aider/extra_params":
            continue

        entry_extra_params = entry.get("extra_params", {})

        if entry_extra_params is None:
            continue

        if not isinstance(entry_extra_params, dict):
            raise ValueError(
                "'extra_params' for aider/extra_params must be a mapping."
            )

        extra_params.update(entry_extra_params)

    for entry in settings:
        if entry.get("name") != model:
            continue

        entry_extra_params = entry.get("extra_params", {})

        if entry_extra_params is None:
            continue

        if not isinstance(entry_extra_params, dict):
            raise ValueError(
                f"'extra_params' for model '{model}' must be a mapping."
            )

        extra_params.update(entry_extra_params)

    return extra_params


def _build_context(read_files: Sequence[str]) -> str:
    sections: list[str] = []

    for path_value in read_files:
        path = _require_file(
            path_value,
            "Context file",
        )

        content = _read_text_file(path)

        sections.append(
            "\n".join(
                [
                    f'<context_file path="{path}">',
                    content,
                    "</context_file>",
                ]
            )
        )

    return "\n\n".join(sections)


def _strip_markdown_fence(text: str) -> str:
    """
    Remove one outer Markdown fence if the model enclosed the entire
    artifact in a fenced code block.

    Examples:

        ```yaml
        version: 1
        ```

        ```
        {...}
        ```

    Fences embedded inside the artifact are preserved.
    """

    stripped = text.strip()

    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()

    if len(lines) < 3:
        return stripped

    if lines[-1].strip() != "```":
        return stripped

    return "\n".join(lines[1:-1]).strip()


def _extract_response_content(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError) as exc:
        raise RuntimeError(
            "LiteLLM returned a response without message content."
        ) from exc

    if content is None:
        raise RuntimeError(
            "LiteLLM returned an empty message content value."
        )

    if not isinstance(content, str):
        raise RuntimeError(
            "LiteLLM returned non-text message content."
        )

    return content


def _usage_value(
    usage: Any,
    attribute: str,
) -> int | None:
    if usage is None:
        return None

    value = getattr(usage, attribute, None)

    if value is not None:
        return value

    if isinstance(usage, dict):
        value = usage.get(attribute)
        if isinstance(value, int):
            return value

    return None


def _log_litellm_usage(response: Any) -> None:
    usage = getattr(response, "usage", None)

    input_tokens = _usage_value(
        usage,
        "prompt_tokens",
    )
    output_tokens = _usage_value(
        usage,
        "completion_tokens",
    )
    total_tokens = _usage_value(
        usage,
        "total_tokens",
    )

    LOGGER.info(
        "LiteLLM completion finished: "
        "input_tokens=%s output_tokens=%s total_tokens=%s",
        input_tokens if input_tokens is not None else "?",
        output_tokens if output_tokens is not None else "?",
        total_tokens if total_tokens is not None else "?",
    )


def _write_artifact(
    output_path: Path,
    content: str,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = output_path.with_name(
        f".{output_path.name}.tmp"
    )

    try:
        temporary_path.write_text(
            content.rstrip() + "\n",
            encoding="utf-8",
        )

        temporary_path.replace(output_path)

    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _run_litellm_backend(
    args: argparse.Namespace,
) -> int:
    if len(args.files) != 1:
        raise ValueError(
            "LiteLLM backend requires exactly one positional output "
            "artifact file."
        )

    try:
        import litellm
    except ImportError as exc:
        raise RuntimeError(
            "LiteLLM is not installed. Install it with: "
            "uv add litellm"
        ) from exc

    message_path = _require_file(
        args.message_file,
        "Message file",
    )

    worker_prompt = _read_text_file(
        message_path
    ).strip()

    if not worker_prompt:
        raise ValueError(
            f"Message file is empty: {message_path}"
        )

    settings_path = _resolve_model_settings_file(
        args.model_settings_file
    )

    settings = _load_model_settings(
        settings_path
    )

    extra_params = _get_extra_params(
        model=args.model,
        settings=settings,
    )

    context = _build_context(
        args.read
    )

    user_parts: list[str] = []

    if context:
        user_parts.append(
            "The following files are provided as read-only context.\n\n"
            + context
        )

    user_parts.append(
        "Produce the requested artifact now. "
        "Return only the artifact content."
    )

    user_message = "\n\n".join(
        user_parts
    )

    messages = [
        {
            "role": "system",
            "content": worker_prompt,
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]

    output_path = Path(
        args.files[0]
    ).expanduser().resolve()

    LOGGER.info(
        "Invoking LiteLLM backend: "
        "model=%s read_files=%d output=%s",
        args.model,
        len(args.read),
        output_path,
    )

    if settings_path is not None:
        LOGGER.info(
            "Using model settings: %s",
            settings_path,
        )

    if extra_params:
        LOGGER.info(
            "LiteLLM extra params for %s: %s",
            args.model,
            extra_params,
        )
    else:
        LOGGER.debug(
            "No LiteLLM extra params configured for %s",
            args.model,
        )

    LOGGER.debug(
        "Message file: %s",
        message_path,
    )

    LOGGER.debug(
        "Context files: %s",
        args.read,
    )

    completion_kwargs: dict[str, Any] = {
        "model": args.model,
        "messages": messages,
        "timeout": args.timeout,
    }

    completion_kwargs.update(
        extra_params
    )

    response = litellm.completion(
        **completion_kwargs
    )

    content = _extract_response_content(
        response
    )

    content = _strip_markdown_fence(
        content
    )

    if not content:
        raise RuntimeError(
            "LiteLLM returned an empty artifact."
        )

    _write_artifact(
        output_path=output_path,
        content=content,
    )

    _log_litellm_usage(
        response
    )

    LOGGER.info(
        "Artifact written: %s (%d bytes)",
        output_path,
        output_path.stat().st_size,
    )

    return 0


def _build_aider_command(
    args: argparse.Namespace,
) -> list:
    command = [
        "aider",
        "--model",
        args.model,
    ]

    if args.model_settings_file:
        command.extend(
            [
                "--model-settings-file",
                args.model_settings_file,
            ]
        )

    if args.edit_format:
        command.extend(
            [
                "--edit-format",
                args.edit_format,
            ]
        )

    if args.map_tokens is not None:
        command.extend(
            [
                "--map-tokens",
                str(args.map_tokens),
            ]
        )

    for path_value in args.read:
        command.extend(
            [
                "--read",
                path_value,
            ]
        )

    if args.yes_always:
        command.append(
            "--yes-always"
        )

    if args.no_auto_commits:
        command.append(
            "--no-auto-commits"
        )

    command.extend(
        [
            "--message-file",
            args.message_file,
        ]
    )

    command.extend(
        args.files
    )

    return command


def _run_aider_backend(
    args: argparse.Namespace,
) -> int:
    command = _build_aider_command(
        args
    )

    LOGGER.info(
        "Invoking Aider backend: "
        "model=%s read_files=%d editable_files=%d",
        args.model,
        len(args.read),
        len(args.files),
    )

    LOGGER.debug(
        "Aider command: %s",
        " ".join(command),
    )

    try:
        result = subprocess.run(
            command,
            timeout=args.timeout,
            check=False,
        )

    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Aider timed out after "
            f"{args.timeout} seconds."
        ) from exc

    except FileNotFoundError as exc:
        raise RuntimeError(
            "Unable to execute 'aider'. "
            "Ensure Aider is installed and available on PATH."
        ) from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"Aider exited with status "
            f"{result.returncode}."
        )

    return 0


def main(
    argv: Sequence[str] | None = None,
) -> int:
    args = _parse_args(
        argv
    )

    _configure_logging(
        args.verbose
    )

    try:
        if args.backend == "aider":
            return _run_aider_backend(
                args
            )

        if args.backend == "litellm":
            return _run_litellm_backend(
                args
            )

        raise ValueError(
            f"Unsupported backend: "
            f"{args.backend}"
        )

    except Exception:
        if args.verbose:
            LOGGER.exception(
                "Backend invocation failed."
            )
        else:
            LOGGER.error(
                "%s",
                sys.exc_info()[1],
            )

        return 1


if __name__ == "__main__":
    sys.exit(main())