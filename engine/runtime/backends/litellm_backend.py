"""Direct LiteLLM backend for non-mutating Jira2PR workers."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from runtime.backends.base import LLMBackend
from runtime.logging_config import get_logger

logger = get_logger("backends.litellm")

DEFAULT_MODEL_SETTINGS_FILE = (
    Path.home()
    / ".aider.model.settings.yml"
)


class LiteLLMBackend(LLMBackend):
    """Generate Jira2PR artifacts directly through LiteLLM."""

    def __init__(
        self,
        *,
        model_settings_file: Path | None = None,
        timeout: int = 600,
    ) -> None:
        self._model_settings_file = (
            model_settings_file
            or DEFAULT_MODEL_SETTINGS_FILE
        )

        self._timeout = timeout

    def produce_artifact(
        self,
        *,
        model: str,
        read_files: list[Path],
        output_file: Path,
        repo_root: Path,
        map_tokens: int | None = None,
    ) -> None:
        """Generate a workflow artifact directly through LiteLLM."""

        prompt_path = (
            repo_root
            / ".jira2pr"
            / "runtime"
            / "backends"
            / "prompts"
            / "litellm-artifact-worker.md"
        )

        self._generate(
            model=model,
            read_files=read_files,
            output_file=output_file,
            prompt_file=prompt_path,
        )

    def produce_structured(
        self,
        *,
        model: str,
        read_files: list[Path],
        output_file: Path,
        repo_root: Path,
        map_tokens: int | None = None,
    ) -> None:
        """Generate structured supervisor output through LiteLLM."""

        prompt_path = (
            repo_root
            / ".jira2pr"
            / "runtime"
            / "backends"
            / "prompts"
            / "litellm-supervisor.md"
        )

        self._generate(
            model=model,
            read_files=read_files,
            output_file=output_file,
            prompt_file=prompt_path,
        )

    def edit_repository(
        self,
        *,
        model: str,
        read_files: list[Path],
        edit_files: list[Path],
        repo_root: Path,
        map_tokens: int | None = None,
    ) -> None:
        """LiteLLM does not directly edit repository files."""

        raise NotImplementedError(
            "LiteLLMBackend does not support repository editing"
        )

    def _generate(
        self,
        *,
        model: str,
        read_files: list[Path],
        output_file: Path,
        prompt_file: Path,
    ) -> None:
        """Run one direct LiteLLM generation and persist the result."""

        try:
            import litellm
        except ImportError as exc:
            raise RuntimeError(
                "LiteLLM is not installed"
            ) from exc

        if not prompt_file.is_file():
            raise FileNotFoundError(
                f"LiteLLM worker prompt not found: {prompt_file}"
            )

        for path in read_files:
            if not path.is_file():
                raise FileNotFoundError(
                    f"Read-only context file does not exist: {path}"
                )

        system_prompt = prompt_file.read_text(
            encoding="utf-8"
        ).strip()

        context = _build_context(
            read_files
        )

        user_message = (
            "The following files are provided as read-only context.\n\n"
            f"{context}\n\n"
            "Produce the requested artifact now. "
            "Return only the artifact content."
        )

        extra_params = self._extra_params_for(
            model
        )

        completion_kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
            "timeout": self._timeout,
        }

        completion_kwargs.update(
            extra_params
        )

        logger.info(
            "Invoking LiteLLM: model=%s read_files=%d output=%s",
            model,
            len(read_files),
            output_file,
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
                "LiteLLM returned empty content"
            )

        _write_artifact(
            output_file,
            content,
        )

    def _extra_params_for(
        self,
        model: str,
    ) -> dict[str, Any]:
        """Load Aider-compatible extra_params for a model."""

        path = self._model_settings_file

        if not path.is_file():
            return {}

        raw = yaml.safe_load(
            path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(raw, list):
            return {}

        extra_params: dict[str, Any] = {}

        for entry in raw:
            if not isinstance(entry, dict):
                continue

            if entry.get("name") not in {
                "aider/extra_params",
                model,
            }:
                continue

            value = entry.get(
                "extra_params",
                {},
            )

            if isinstance(value, dict):
                extra_params.update(
                    value
                )

        return extra_params


def _build_context(
    read_files: Sequence[Path],
) -> str:
    sections: list[str] = []

    for path in read_files:
        content = path.read_text(
            encoding="utf-8"
        )

        sections.append(
            "\n".join(
                [
                    f'<context_file path="{path}">',
                    content,
                    "</context_file>",
                ]
            )
        )

    return "\n\n".join(
        sections
    )


def _extract_response_content(
    response: Any,
) -> str:
    try:
        content = (
            response
            .choices[0]
            .message
            .content
        )

    except (
        AttributeError,
        IndexError,
        TypeError,
    ) as exc:
        raise RuntimeError(
            "LiteLLM returned a response without message content"
        ) from exc

    if not isinstance(content, str):
        raise TypeError(
            "LiteLLM returned non-text message content"
        )

    return content


def _strip_markdown_fence(
    text: str,
) -> str:
    stripped = text.strip()

    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()

    if (
        len(lines) < 3
        or lines[-1].strip() != "```"
    ):
        return stripped

    return "\n".join(
        lines[1:-1]
    ).strip()


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

        temporary_path.replace(
            output_path
        )

    finally:
        temporary_path.unlink(
            missing_ok=True
        )