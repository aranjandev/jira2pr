"""Feedback produced when a workflow worker attempt does not succeed."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class WorkerFeedback:
    """Actionable feedback for the next attempt of a workflow state.

    ``resume_from`` names the repository task that failed. When set, a retry
    may resume at that task and keep the edits of the tasks before it.
    """

    source: str
    reason: str
    details: tuple[str, ...] = field(default_factory=tuple)
    resume_from: str | None = None
    # Review findings as (file, instruction) pairs. Persisted as a work list.
    findings: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "reason": self.reason,
            "details": list(self.details),
            "resume_from": self.resume_from,
        }


class WorkerOutputError(RuntimeError):
    """Raised when worker execution succeeds but its output is invalid."""

    def __init__(
        self,
        *,
        source: str,
        reason: str,
        details: list[str] | None = None,
        resume_from: str | None = None,
    ) -> None:
        self.feedback = WorkerFeedback(
            source=source,
            reason=reason,
            details=tuple(details or []),
            resume_from=resume_from,
        )

        super().__init__(reason)


def feedback_path(
    context_dir: Path,
    state_name: str,
) -> Path:
    """Return the feedback file for a workflow state."""

    return context_dir / f"{state_name}-feedback.json"


def write_feedback(
    *,
    context_dir: Path,
    state_name: str,
    attempt: int,
    feedback: WorkerFeedback,
) -> Path:
    """Persist feedback for the next attempt of a workflow state."""

    context_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = feedback_path(
        context_dir,
        state_name,
    )

    data = {
        "state": state_name,
        "attempt": attempt,
        **feedback.to_dict(),
    }

    path.write_text(
        json.dumps(
            data,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return path


def clear_feedback(
    *,
    context_dir: Path,
    state_name: str,
) -> None:
    """Clear retry feedback after a workflow state succeeds.

    Review findings are archived, not deleted, so each review cycle keeps its
    record.
    """

    feedback_path(
        context_dir,
        state_name,
    ).unlink(
        missing_ok=True,
    )
    archive_findings(context_dir=context_dir, state_name=state_name)


def findings_path(context_dir: Path, state_name: str) -> Path:
    """Return the review-findings work list for a workflow state."""

    return context_dir / f"{state_name}-findings.json"


FINDING_PENDING = "pending"
FINDING_ADDRESSED = "addressed"
FINDING_REOPENED = "reopened"
OPEN_FINDING_STATUSES = frozenset({FINDING_PENDING, FINDING_REOPENED})


def write_findings(
    *,
    context_dir: Path,
    state_name: str,
    findings: list[dict],
) -> Path:
    """Persist a new review cycle's findings with status ``pending``."""

    context_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    entries = [{**finding, "status": FINDING_PENDING} for finding in findings]
    path = findings_path(context_dir, state_name)
    path.write_text(
        json.dumps(
            {"state": state_name, "findings": entries},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def read_findings(context_dir: Path, state_name: str) -> list[dict]:
    """Return every finding of the current review cycle, with its status."""

    path = findings_path(context_dir, state_name)
    if not path.is_file():
        return []
    return list(json.loads(path.read_text(encoding="utf-8")).get("findings", []))


def open_findings(findings: list[dict]) -> list[dict]:
    """Return the findings that still need a change."""

    return [finding for finding in findings if finding.get("status") in OPEN_FINDING_STATUSES]


def set_finding_status(
    *,
    context_dir: Path,
    state_name: str,
    file: str,
    status: str,
    only_from: frozenset[str] | None = None,
) -> int:
    """Set the status of every finding for ``file``.

    When ``only_from`` is given, only findings currently in one of those
    statuses change. Returns how many findings changed.
    """

    path = findings_path(context_dir, state_name)
    if not path.is_file():
        return 0

    data = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for finding in data.get("findings", []):
        if finding.get("file") != file:
            continue
        if only_from is not None and finding.get("status") not in only_from:
            continue
        if finding.get("status") != status:
            finding["status"] = status
            changed += 1

    if changed:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changed


def archive_findings(*, context_dir: Path, state_name: str) -> Path | None:
    """Move the current review cycle's findings to the archive folder."""

    path = findings_path(context_dir, state_name)
    if not path.is_file():
        return None

    archive_dir = context_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    cycle = len(list(archive_dir.glob(f"{state_name}-findings-*.json"))) + 1
    target = archive_dir / f"{state_name}-findings-{cycle}.json"
    path.replace(target)
    return target


def reopen_addressed_findings(*, context_dir: Path, state_name: str) -> int:
    """Mark every addressed finding as reopened, e.g. after verification fails."""

    path = findings_path(context_dir, state_name)
    if not path.is_file():
        return 0

    data = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for finding in data.get("findings", []):
        if finding.get("status") == FINDING_ADDRESSED:
            finding["status"] = FINDING_REOPENED
            changed += 1

    if changed:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changed


def open_findings_summary(*, context_dir: Path, state_names: list[str]) -> list[dict]:
    """Summarize open findings across states for the workflow state file."""

    summary: list[dict] = []
    for name in state_names:
        for finding in open_findings(read_findings(context_dir, name)):
            summary.append(
                {
                    "state": name,
                    "file": finding["file"],
                    "instruction": finding["instruction"],
                    "status": finding["status"],
                }
            )
    return summary