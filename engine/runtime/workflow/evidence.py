"""Collect deterministic implementation evidence for workflow evaluation.

Implementation evidence is collected after repository-editing workers have
completed and before supervisor or reviewer evaluation.

Evidence is materialized under::

    .jira2pr/context/<TICKET-KEY>/

The evidence files contain:

- the Git diff for files authorized by the implementation plan
- test command results
- lint command results

Evidence is intentionally bounded so large command output does not overwhelm
LLM context windows.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

from runtime.logging_config import get_logger
from runtime.workflow.loader import RuntimeProject

logger = get_logger("workflow.evidence")

DEFAULT_COMMAND_TIMEOUT_SECONDS = 600

MAX_SUCCESS_OUTPUT_LINES = 30
MAX_FAILURE_OUTPUT_CHARS = 20_000


class EvidenceCollectionError(RuntimeError):
    """Raised when implementation evidence cannot be collected."""


@dataclass(frozen=True)
class ImplementationEvidence:
    """Materialized evidence from a completed implementation attempt."""

    diff_path: Path
    test_results_path: Path
    lint_results_path: Path
    tests_passed: bool
    lint_passed: bool

    def files(self) -> list[Path]:
        """Return all evidence files in stable order."""

        return [
            self.diff_path,
            self.test_results_path,
            self.lint_results_path,
        ]

    @property
    def verification_passed(self) -> bool:
        """Return True when all deterministic verification passed."""

        return self.tests_passed and self.lint_passed

@dataclass(frozen=True)
class CommandResult:
    """Result of a deterministic verification command."""

    command: str
    exit_code: int
    stdout: str
    stderr: str

    @property
    def passed(self) -> bool:
        """Return True when the verification command succeeded."""

        return self.exit_code == 0


def planned_changed_files(
    *,
    plan_path: Path,
    repo_root: Path,
) -> list[Path]:
    """Return create/modify targets declared by a validated plan.yaml.

    Includes both implementation tasks and planned test tasks.

    The plan is assumed to have already passed artifact validation.
    Returned paths are absolute repository paths in plan order
    """

    data = yaml.safe_load(
        plan_path.read_text(
            encoding="utf-8"
        )
    )

    repo_root = repo_root.resolve()

    changed_files: list[Path] = []
    seen: set[Path] = set()

    for section in ("tasks", "tests"):
        for task in data[section]:
            if task["edit_mode"] not in ["create", "modify"]:
                continue

            path = (
                repo_root
                / task["file_path"]
            ).resolve()

            if path in seen:
                continue

            seen.add(path)
            changed_files.append(path)

    return changed_files

def collect_implementation_evidence(
    *,
    project: RuntimeProject,
    ticket_key: str,
    changed_files: list[Path],
    test_command: str,
    lint_command: str,
    timeout: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
) -> ImplementationEvidence:
    """Collect diff, test, and lint evidence for an implementation.

    The Git diff is restricted to files authorized by the validated
    implementation plan.

    Test and lint failures are recorded as evidence rather than raised as
    exceptions. A non-zero exit code is a valid verification result that
    downstream supervisor or reviewer agents may inspect.

    Infrastructure failures, such as timeouts or inability to launch a
    command, raise EvidenceCollectionError.
    """

    repo_root = project.core_dir.parent.resolve()

    context_dir = project.context_dir(ticket_key)
    context_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    diff_path = context_dir / "implementation-diff.patch"
    test_results_path = context_dir / "test-results.txt"
    lint_results_path = context_dir / "lint-results.txt"

    logger.info(
        "Collecting implementation evidence for ticket: %s",
        ticket_key,
    )

    normalized_changed_files = _normalize_repository_files(
        repo_root=repo_root,
        files=changed_files,
    )

    _collect_git_diff(
        repo_root=repo_root,
        output_path=diff_path,
        changed_files=normalized_changed_files,
        timeout=timeout,
    )

    test_result = _run_verification_command(
        command=test_command,
        repo_root=repo_root,
        timeout=timeout,
        label="tests",
    )

    _write_command_result(
        path=test_results_path,
        result=test_result,
    )

    lint_result = _run_verification_command(
        command=lint_command,
        repo_root=repo_root,
        timeout=timeout,
        label="lint",
    )

    _write_command_result(
        path=lint_results_path,
        result=lint_result,
    )

    evidence = ImplementationEvidence(
        diff_path=diff_path,
        test_results_path=test_results_path,
        lint_results_path=lint_results_path,
        tests_passed=test_result.passed,
        lint_passed=lint_result.passed,
    )

    logger.info(
        "Implementation evidence collected: "
        "diff=%s, tests_passed=%s, lint_passed=%s",
        diff_path,
        test_result.passed,
        lint_result.passed,
    )

    return evidence


def load_implementation_evidence(
    *,
    project: RuntimeProject,
    ticket_key: str,
) -> ImplementationEvidence:
    """Load previously collected implementation evidence."""

    context_dir = project.context_dir(ticket_key)

    diff_path = (
        context_dir
        / "implementation-diff.patch"
    )

    test_results_path = (
        context_dir
        / "test-results.txt"
    )

    lint_results_path = (
        context_dir
        / "lint-results.txt"
    )

    required_paths = [
        diff_path,
        test_results_path,
        lint_results_path,
    ]

    missing = [
        path
        for path in required_paths
        if not path.is_file()
    ]

    if missing:
        raise EvidenceCollectionError(
            "Missing implementation evidence: "
            + ", ".join(
                str(path)
                for path in missing
            )
        )

    tests_passed = _evidence_result_passed(
        test_results_path
    )

    lint_passed = _evidence_result_passed(
        lint_results_path
    )

    evidence = ImplementationEvidence(
        diff_path=diff_path,
        test_results_path=test_results_path,
        lint_results_path=lint_results_path,
        tests_passed=tests_passed,
        lint_passed=lint_passed,
    )

    logger.debug(
        "Loaded implementation evidence: "
        "tests_passed=%s lint_passed=%s",
        tests_passed,
        lint_passed,
    )

    return evidence


def _evidence_result_passed(
    path: Path,
) -> bool:
    """Return whether a persisted verification result represents success."""

    content = path.read_text(
        encoding="utf-8"
    )

    for line in content.splitlines():
        line = line.strip()

        if line.startswith("exit_code:"):
            value = line.partition(":")[2].strip()

            try:
                return int(value) == 0
            except ValueError as exc:
                raise EvidenceCollectionError(
                    f"Invalid exit_code in verification evidence "
                    f"{path}: {value!r}"
                ) from exc

    raise EvidenceCollectionError(
        f"Verification evidence does not contain exit_code: {path}"
    )

def _normalize_repository_files(
    *,
    repo_root: Path,
    files: list[Path],
) -> list[Path]:
    """Return unique repository-relative paths in stable order."""

    if not files:
        raise EvidenceCollectionError(
            "No implementation files supplied for evidence collection"
        )

    repo_root = repo_root.resolve()

    normalized: list[Path] = []
    seen: set[Path] = set()

    for path in files:
        absolute_path = (
            path.resolve()
            if path.is_absolute()
            else (repo_root / path).resolve()
        )

        try:
            relative_path = absolute_path.relative_to(repo_root)
        except ValueError as exc:
            raise EvidenceCollectionError(
                f"Evidence file is outside repository root: {path}"
            ) from exc

        if relative_path in seen:
            continue

        seen.add(relative_path)
        normalized.append(relative_path)

    return normalized


def _collect_git_diff(
    *,
    repo_root: Path,
    output_path: Path,
    changed_files: list[Path],
    timeout: int,
) -> None:
    """Capture the Git diff only for files authorized by the plan."""

    if not changed_files:
        raise EvidenceCollectionError(
            "No implementation files supplied for diff collection"
        )

    argv = [
        "git",
        "diff",
        "--no-ext-diff",
        "--",
        *[str(path) for path in changed_files],
    ]

    logger.debug(
        "Collecting implementation diff: %s",
        " ".join(argv),
    )

    try:
        result = subprocess.run(
            argv,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    except subprocess.TimeoutExpired as exc:
        raise EvidenceCollectionError(
            f"git diff timed out after {timeout}s"
        ) from exc

    except OSError as exc:
        raise EvidenceCollectionError(
            f"Unable to execute git diff: {exc}"
        ) from exc

    if result.returncode != 0:
        raise EvidenceCollectionError(
            f"git diff exited {result.returncode}: "
            f"{result.stderr.strip()}"
        )

    output_path.write_text(
        result.stdout,
        encoding="utf-8",
    )

    logger.info(
        "Implementation diff written to %s (%d chars)",
        output_path,
        len(result.stdout),
    )


def _run_verification_command(
    *,
    command: str,
    repo_root: Path,
    timeout: int,
    label: str,
) -> CommandResult:
    """Execute a test or lint command.

    A non-zero exit code does not raise. It represents a meaningful failed
    verification result and is recorded as evidence.
    """

    if not command.strip():
        raise EvidenceCollectionError(
            f"No {label} command configured"
        )

    logger.info(
        "Running %s command: %s",
        label,
        command,
    )

    try:
        result = subprocess.run(
            command,
            cwd=repo_root,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    except subprocess.TimeoutExpired as exc:
        raise EvidenceCollectionError(
            f"{label} command timed out after {timeout}s: "
            f"{command}"
        ) from exc

    except OSError as exc:
        raise EvidenceCollectionError(
            f"Unable to execute {label} command: {exc}"
        ) from exc

    logger.info(
        "%s command completed with exit code %d",
        label.capitalize(),
        result.returncode,
    )

    return CommandResult(
        command=command,
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _write_command_result(
    *,
    path: Path,
    result: CommandResult,
) -> None:
    """Write compact, human- and LLM-readable verification evidence."""

    status = "PASS" if result.passed else "FAIL"

    if result.passed:
        stdout = _tail_lines(
            result.stdout,
            max_lines=MAX_SUCCESS_OUTPUT_LINES,
        )

        stderr = _tail_lines(
            result.stderr,
            max_lines=MAX_SUCCESS_OUTPUT_LINES,
        )

    else:
        stdout = _truncate_output(
            result.stdout,
            max_chars=MAX_FAILURE_OUTPUT_CHARS,
        )

        stderr = _truncate_output(
            result.stderr,
            max_chars=MAX_FAILURE_OUTPUT_CHARS,
        )

    content = (
        f"status: {status}\n"
        f"exit_code: {result.exit_code}\n"
        f"command: {result.command}\n"
        "\n"
        "--- stdout ---\n"
        f"{stdout}\n"
        "\n"
        "--- stderr ---\n"
        f"{stderr}\n"
    )

    path.write_text(
        content,
        encoding="utf-8",
    )

    logger.debug(
        "Verification evidence written to %s (%d chars)",
        path,
        len(content),
    )


def _tail_lines(
    text: str,
    *,
    max_lines: int,
) -> str:
    """Return at most the final max_lines lines of output."""

    lines = text.splitlines()

    if len(lines) <= max_lines:
        return text.strip()

    omitted = len(lines) - max_lines

    tail = "\n".join(
        lines[-max_lines:]
    )

    return (
        f"[... {omitted} earlier lines omitted by jira2pr ...]\n"
        f"{tail}"
    )


def _truncate_output(
    text: str,
    *,
    max_chars: int,
) -> str:
    """Bound failed command output while preserving beginning and end."""

    text = text.strip()

    if len(text) <= max_chars:
        return text

    marker = "\n\n[... output truncated by jira2pr ...]\n\n"

    available = max_chars - len(marker)

    if available <= 0:
        return marker.strip()

    head_size = available // 2
    tail_size = available - head_size

    return (
        text[:head_size]
        + marker
        + text[-tail_size:]
    )