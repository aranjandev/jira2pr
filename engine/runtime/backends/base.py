"""Abstract interface for LLM-backed agent execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class LLMBackend(ABC):
    """Execution backend used by the Jira2PR workflow runtime."""

    @abstractmethod
    def produce_artifact(
        self,
        *,
        model: str,
        read_files: list[Path],
        output_file: Path,
        repo_root: Path,
        map_tokens: int | None = None,
    ) -> None:
        """Produce a workflow artifact."""

    @abstractmethod
    def produce_structured(
        self,
        *,
        model: str,
        read_files: list[Path],
        output_file: Path,
        repo_root: Path,
        map_tokens: int | None = None,
    ) -> None:
        """Produce structured machine-readable output."""

    @abstractmethod
    def edit_repository(
        self,
        *,
        model: str,
        read_files: list[Path],
        edit_files: list[Path],
        repo_root: Path,
        map_tokens: int | None = None,
    ) -> None:
        """Modify repository files."""

    @abstractmethod
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
        """Repair repository changes using verification feedback."""