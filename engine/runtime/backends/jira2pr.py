"""Jira2PR composite backend.

Routes content-generation operations through LiteLLM and repository-editing
operations through Aider.
"""

from __future__ import annotations

from pathlib import Path

from runtime.backends.aider import AiderBackend
from runtime.backends.base import LLMBackend
from runtime.backends.litellm_backend import LiteLLMBackend
from runtime.logging_config import get_logger

logger = get_logger("backends.jira2pr")


class Jira2PRBackend(LLMBackend):
    """Route Jira2PR operations to the appropriate execution backend.

    Artifact and structured generation use LiteLLM directly.

    Repository editing uses Aider because it provides repository mapping,
    edit-format handling, and filesystem mutation.
    """

    def __init__(
        self,
        *,
        litellm_backend: LiteLLMBackend | None = None,
        aider_backend: AiderBackend | None = None,
    ) -> None:
        self._litellm = (
            litellm_backend
            or LiteLLMBackend()
        )

        self._aider = (
            aider_backend
            or AiderBackend()
        )

    def produce_artifact(
        self,
        *,
        model: str,
        read_files: list[Path],
        output_file: Path,
        repo_root: Path,
        map_tokens: int | None = None,
    ) -> None:
        """Produce an artifact through direct LiteLLM generation."""

        logger.info(
            "Routing artifact generation to LiteLLM: output=%s",
            output_file,
        )

        self._litellm.produce_artifact(
            model=model,
            read_files=read_files,
            output_file=output_file,
            repo_root=repo_root,
            map_tokens=map_tokens,
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
        """Produce structured output through direct LiteLLM generation."""

        logger.info(
            "Routing structured generation to LiteLLM: output=%s",
            output_file,
        )

        self._litellm.produce_structured(
            model=model,
            read_files=read_files,
            output_file=output_file,
            repo_root=repo_root,
            map_tokens=map_tokens,
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
        """Perform repository edits through Aider."""

        logger.info(
            "Routing repository editing to Aider: files=%d",
            len(edit_files),
        )

        self._aider.edit_repository(
            model=model,
            read_files=read_files,
            edit_files=edit_files,
            repo_root=repo_root,
            map_tokens=map_tokens,
        )

    def repair_repository(
        self,
        *,
        model: str,
        read_files: list[Path],
        edit_files: list[Path],
        repo_root: Path,
        test_command: str,
        lint_command: str,
        map_tokens: int | None = None,
    ) -> None:
        """Route repository repair to Aider."""

        logger.info(
            "Routing repository repair to Aider: "
            "model=%s edit_files=%d",
            model,
            len(edit_files),
        )

        self._aider.repair_repository(
            model=model,
            read_files=read_files,
            edit_files=edit_files,
            repo_root=repo_root,
            test_command=test_command,
            lint_command=lint_command,
            map_tokens=map_tokens,
        )

    def remediate_review(
        self,
        *,
        model: str,
        read_files: list[Path],
        edit_files: list[Path],
        repo_root: Path,
        test_command: str,
        lint_command: str,
        map_tokens: int | None = None,
    ) -> None:
        """Route review remediation to Aider."""

        logger.info(
            "Routing review remediation to Aider: "
            "model=%s edit_files=%d",
            model,
            len(edit_files),
        )

        self._aider.remediate_review(
            model=model,
            read_files=read_files,
            edit_files=edit_files,
            repo_root=repo_root,
            test_command=test_command,
            lint_command=lint_command,
            map_tokens=map_tokens,
        )