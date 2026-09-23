"""Abstract interface for LLM-backed agent execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class LLMBackend(ABC):
    """Platform backend for invoking jira2pr agents."""

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        files: list[Path] | None = None,
    ) -> str:
        """Run a text-producing agent turn and return its raw response."""

    @abstractmethod
    def produce_artifact(
        self,
        *,
        model: str,
        read_files: list[Path],
        output_file: Path,
        repo_root: Path,
    ) -> None :
        """Run an artifact-producing worker.

        The backend must use *read_files* as read-only context and produce
        *output_file* as the authoritative result.

        Returns nothing.
        """

    @abstractmethod
    def produce_structured(
        self,
        *,
        model:str,
        read_files: list[Path],
        output_file: Path,
        repo_root: Path,
    ) -> None:
        """Run a structured artifact-producing worker.

        The backend must use *read_files* as read-only context and produce
        *output_file* as the authoritative result.

        Returns nothing.
        """