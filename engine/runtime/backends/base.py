"""LLMBackend — abstract interface for invoking a worker/supervisor agent."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class LLMBackend(ABC):
    """Runs one agent turn: system prompt + user prompt (+ file context) -> text."""

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        files: list[Path] | None = None,
    ) -> str:
        """Return the raw text response for a single agent turn."""
