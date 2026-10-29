"""Abstract interface for LLM-backed agent execution."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BackendInvocationError(RuntimeError):
    """A backend call failed at run time (timeout, process exit, provider error).

    The workflow runtime treats this as a failed worker attempt, so it counts
    against the state's retry budget. Precondition or configuration errors
    should use a different exception type so they still stop the run.
    """


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

    def fix_repository(
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
        """Apply one fix attempt guided by feedback in ``read_files``.

        The engine calls this on a state re-entry that carries failure
        feedback (e.g. failing tests), and then re-runs verification itself.
        The engine owns the attempt budget, so a backend performs one attempt
        per call. Backends may override this to run their own in-session
        test loop. By default it is a plain edit attempt.
        """

        self.edit_repository(
            model=model,
            read_files=read_files,
            edit_files=edit_files,
            repo_root=repo_root,
            map_tokens=map_tokens,
        )
