"""AiderBackend — invokes `aider` as a subprocess for one worker turn."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from runtime.backends.base import LLMBackend

DEFAULT_TIMEOUT_SECONDS = 600


class AiderInvocationError(RuntimeError):
    """Raised when the `aider` subprocess exits non-zero or times out."""


class AiderBackend(LLMBackend):
    """Shells out to the `aider` CLI. Requires `aider` to be on PATH."""

    def __init__(
        self,
        base_args: list[str] | None = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_args = base_args or ["--yes-always", "--no-auto-commits"]
        self._timeout = timeout

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        files: list[Path] | None = None,
    ) -> str:
        files = files or []
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(system_prompt.rstrip() + "\n\n---\n\n" + user_prompt)
            message_file = f.name
        try:
            argv = [
                "aider",
                "--model", model,
                "--message-file", message_file,
                *self._base_args,
                *[str(p) for p in files],
            ]
            try:
                result = subprocess.run(
                    argv, capture_output=True, text=True, timeout=self._timeout, check=False
                )
            except subprocess.TimeoutExpired as exc:
                raise AiderInvocationError(
                    f"aider timed out after {self._timeout}s (model={model})"
                ) from exc
            if result.returncode != 0:
                raise AiderInvocationError(
                    f"aider exited {result.returncode}: {result.stderr.strip()}"
                )
            return result.stdout
        finally:
            Path(message_file).unlink(missing_ok=True)
