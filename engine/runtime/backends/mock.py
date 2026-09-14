"""MockBackend — deterministic, offline stand-in for tests and dry-runs.

Used by `runtime/workflow/executor.py`'s test suite to run a full workflow
(feature: jira-ingest -> ... -> done/human-review) without any real LLM or
network calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from runtime.backends.base import LLMBackend

Responder = Callable[[str, str, str], str]


class MockBackend(LLMBackend):
    """Returns scripted or generic canned output and records every call made.

    *responder*, if given, is tried first and receives (system_prompt,
    user_prompt, model) for full control (e.g. a stateful counter that fails
    the first N attempts at a given agent, to exercise retry/escalation
    paths). *responses* is a simpler agent-title -> canned-text map used when
    *responder* is absent or returns None.
    """

    def __init__(
        self,
        responses: dict[str, str] | None = None,
        responder: Responder | None = None,
    ) -> None:
        self._responses = responses or {}
        self._responder = responder
        self.calls: list[dict] = []

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        files: list[Path] | None = None,
    ) -> str:
        self.calls.append(
            {"system_prompt": system_prompt, "user_prompt": user_prompt, "model": model}
        )
        if self._responder is not None:
            result = self._responder(system_prompt, user_prompt, model)
            if result is not None:
                return result
        key = _agent_title(system_prompt)
        if key in self._responses:
            return self._responses[key]
        return "# Mock Output\n\nGenerated deterministically for testing.\n"


def _agent_title(system_prompt: str) -> str:
    for line in system_prompt.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip().lower()
    return ""

