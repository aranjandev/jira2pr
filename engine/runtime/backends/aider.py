"""Aider backend for jira2pr worker execution."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from runtime.backends.base import LLMBackend
from runtime.logging_config import get_logger


logger = get_logger("backends.aider")

DEFAULT_TIMEOUT_SECONDS = 600


class AiderInvocationError(RuntimeError):
    """Raised when an Aider invocation cannot complete successfully."""


class AiderBackend(LLMBackend):
    """Invoke Aider as a subprocess.

    Text-producing calls use ``complete()``.

    Artifact-producing workers use ``produce_artifact()`` and treat the
    resulting filesystem artifact as authoritative. Aider stdout is diagnostic
    output only for artifact-producing workers.
    """

    def __init__(
        self,
        base_args: list[str] | None = None,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_args = base_args or [
            "--yes-always",
            "--no-auto-commits",
        ]
        self._timeout = timeout

        logger.debug(
            "AiderBackend initialized with timeout=%ss, base_args=%s",
            timeout,
            self._base_args,
        )

    # ------------------------------------------------------------------
    # Text-producing invocation
    # ------------------------------------------------------------------
    # TODO:
    # Replace complete() with an explicit repository-editing backend operation.
    # Context files must remain read-only; only source/test files selected for the
    # current implementation task should be editable.
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str,
        files: list[Path] | None = None,
    ) -> str:
        """Run one text-producing Aider turn."""

        files = files or []

        logger.info(
            "Invoking Aider text worker: model=%s, files=%d",
            model,
            len(files),
        )

        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".md",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(system_prompt.rstrip())
            f.write("\n\n---\n\n")
            f.write(user_prompt)
            message_file = Path(f.name)

        logger.debug("Created temporary message file: %s", message_file)

        try:
            argv = [
                "aider",
                "--model",
                model,
                "--message-file",
                str(message_file),
                *self._base_args,
                *[str(path) for path in files],
            ]

            result = self._run(
                argv,
                model=model,
            )

            logger.info(
                "Aider text invocation successful, response length=%d",
                len(result.stdout),
            )

            return result.stdout

        finally:
            message_file.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Artifact-producing invocation
    # ------------------------------------------------------------------
    def produce_artifact(
        self,
        *,
        model: str,
        read_files: list[Path],
        output_file: Path,
        repo_root: Path,
    ) -> None:
        """Run an artifact-producing worker.

        All context is supplied to Aider through ``--read`` files. The output
        artifact is the only editable file.

        The filesystem artifact, not Aider stdout, is the authoritative result.
        """

        repo_root = repo_root.resolve()
        output_file = output_file.resolve()

        logger.info(
            "Invoking Aider artifact worker: model=%s, read_files=%d, output=%s",
            model,
            len(read_files),
            output_file,
        )

        # Validate input context before launching Aider.
        for path in read_files:
            if not path.is_file():
                raise AiderInvocationError(
                    f"Read-only context file does not exist: {path}"
                )

        message_file = self._artifact_worker_prompt(repo_root)

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # The artifact must be produced by this invocation, not inherited
        # from a previous attempt.
        output_file.unlink(missing_ok=True)
        
        argv = [
            "aider",
            "--model",
            model,
        ]

        for path in read_files:
            argv.extend(
                [
                    "--read",
                    str(path.resolve()),
                ]
            )

        argv.extend(self._base_args)

        argv.extend(
            [
                "--message-file",
                str(message_file),
                str(output_file),
            ]
        )

        logger.info("Running: %s", " ".join(argv))

        result = self._run(
            argv,
            model=model,
            cwd=repo_root,
        )

        # Artifact producing workers should always leave a non-empty result.
        if not output_file.is_file():
            self._log_diagnostics(result)

            raise AiderInvocationError(
                f"Aider did not produce expected artifact: {output_file}"
            )

        content = output_file.read_text(
            encoding="utf-8"
        ).strip()

        if not content:
            self._log_diagnostics(result)

            raise AiderInvocationError(
                f"Aider produced an empty artifact: {output_file}"
            )

        logger.info(
            "Aider produced artifact %s (%d chars)",
            output_file,
            len(content),
        )

        return None


    # ------------------------------------------------------------------
    # Structured-output invocation
    # ------------------------------------------------------------------
    def produce_structured(
        self,
        *,
        model: str,
        read_files: list[Path],
        output_file: Path,
        repo_root: Path,
    ) -> None:
        """Run a structured-output Aider invocation.

        All context is supplied through ``--read`` files. The output file is the
        only editable file.

        The filesystem output, not Aider stdout, is authoritative. The resulting
        file must contain valid JSON.
        """
        import json

        repo_root = repo_root.resolve()
        output_file = output_file.resolve()

        logger.info(
            "Invoking Aider structured worker: model=%s, read_files=%d, output=%s",
            model,
            len(read_files),
            output_file,
        )

        # Validate input context before launching Aider.
        for path in read_files:
            if not path.is_file():
                raise AiderInvocationError(
                    f"Read-only context file does not exist: {path}"
                )

        message_file = self._structured_worker_prompt(repo_root)

        output_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Structured output must be produced by this invocation.
        output_file.unlink(missing_ok=True)

        argv = [
            "aider",
            "--model",
            model,
        ]

        for path in read_files:
            argv.extend(
                [
                    "--read",
                    str(path.resolve()),
                ]
            )

        argv.extend(self._base_args)

        argv.extend(
            [
                "--message-file",
                str(message_file),
                str(output_file),
            ]
        )

        logger.info(
            "Running: %s",
            " ".join(argv),
        )

        result = self._run(
            argv,
            model=model,
            cwd=repo_root,
        )

        if not output_file.is_file():
            self._log_diagnostics(result)

            raise AiderInvocationError(
                f"Aider did not produce expected structured output: "
                f"{output_file}"
            )

        content = output_file.read_text(
            encoding="utf-8"
        ).strip()

        if not content:
            self._log_diagnostics(result)

            raise AiderInvocationError(
                f"Aider produced empty structured output: "
                f"{output_file}"
            )

        # Validate transport-level structure here.
        #
        # Semantic validation such as allowed outcomes and required fields
        # belongs to supervisor_invoker / SupervisorContract.
        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            self._log_diagnostics(result)

            raise AiderInvocationError(
                f"Aider produced invalid JSON in {output_file}: {exc}"
            ) from exc

        logger.info(
            "Aider produced structured output %s (%d chars)",
            output_file,
            len(content),
        )

    # ------------------------------------------------------------------
    # Runtime prompt lookup
    # ------------------------------------------------------------------
    def _artifact_worker_prompt(
        self,
        repo_root: Path,
    ) -> Path:
        path = (
            repo_root
            / ".jira2pr"
            / "runtime"
            / "backends"
            / "prompts"
            / "aider-artifact-worker.md"
        )

        if not path.is_file():
            raise AiderInvocationError(
                f"Aider artifact worker prompt not found: {path}"
            )

        return path

    def _structured_worker_prompt(
        self,
        repo_root: Path,
    ) -> Path:
        path = (
            repo_root
            / ".jira2pr"
            / "runtime"
            / "backends"
            / "prompts"
            / "aider-supervisor.md"
        )

        if not path.is_file():
            raise AiderInvocationError(
                f"Aider supervisor prompt not found: {path}"
            )

        return path

    # ------------------------------------------------------------------
    # Subprocess handling
    # ------------------------------------------------------------------
    def _run(
        self,
        argv: list[str],
        *,
        model: str,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run Aider and normalize timeout/process errors."""

        logger.debug(
            "Starting Aider subprocess: timeout=%ss cwd=%s",
            self._timeout,
            cwd,
        )

        try:
            result = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )

        except subprocess.TimeoutExpired as exc:
            logger.error(
                "Aider timed out after %ss with model=%s",
                self._timeout,
                model,
            )

            raise AiderInvocationError(
                f"Aider timed out after {self._timeout}s "
                f"(model={model})"
            ) from exc

        logger.debug(
            "Aider subprocess exited with code=%d",
            result.returncode,
        )

        if result.returncode != 0:
            self._log_diagnostics(result)

            raise AiderInvocationError(
                f"Aider exited {result.returncode}: "
                f"{result.stderr.strip()}"
            )

        return result

    @staticmethod
    def _log_diagnostics(
        result: subprocess.CompletedProcess[str],
    ) -> None:
        """Log Aider output when an invocation fails semantically."""

        if result.stdout:
            logger.error(
                "Aider stdout:\n%s",
                result.stdout,
            )

        if result.stderr:
            logger.error(
                "Aider stderr:\n%s",
                result.stderr,
            )