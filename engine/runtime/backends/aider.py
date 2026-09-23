"""AiderBackend — invokes `aider` as a subprocess for one worker turn."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from runtime.backends.base import LLMBackend
from runtime.logging_config import get_logger

logger = get_logger("backends.aider")

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
        logger.debug(f"AiderBackend initialized with timeout={timeout}s, base_args={self._base_args}")

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        files: list[Path] | None = None,
    ) -> str:
        files = files or []
        logger.info(f"Invoking aider with model={model}, files={len(files)}")
        logger.debug(f"System prompt length: {len(system_prompt)}, User prompt length: {len(user_prompt)}")

        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write(system_prompt.rstrip() + "\n\n---\n\n" + user_prompt)
            message_file = f.name
        logger.debug(f"Created message file: {message_file}")

        try:
            argv = [
                "aider",
                "--model", model,
                "--message-file", message_file,
                *self._base_args,
                *[str(p) for p in files],
            ]
            logger.debug(f"Running command: {' '.join(argv)}")
            logger.info(f"Starting aider subprocess with timeout={self._timeout}s")

            try:
                result = subprocess.run(
                    argv, capture_output=True, text=True, timeout=self._timeout, check=False
                )
                logger.debug(f"Aider subprocess completed with return code: {result.returncode}")
                logger.debug(f"Aider stdout length: {len(result.stdout)}")
                if result.stderr:
                    logger.debug(f"Aider stderr: {result.stderr[:500]}")
            except subprocess.TimeoutExpired as exc:
                logger.error(f"Aider timed out after {self._timeout}s with model={model}")
                raise AiderInvocationError(
                    f"aider timed out after {self._timeout}s (model={model})"
                ) from exc

            if result.returncode != 0:
                logger.error(f"Aider exited with non-zero code: {result.returncode}")
                logger.error(f"Aider error output: {result.stderr.strip()}")
                raise AiderInvocationError(
                    f"aider exited {result.returncode}: {result.stderr.strip()}"
                )

            logger.info(f"Aider invocation successful, response length: {len(result.stdout)}")
            return result.stdout
        finally:
            Path(message_file).unlink(missing_ok=True)
            logger.debug(f"Cleaned up message file: {message_file}")
