"""Feedback produced when a workflow worker attempt does not succeed."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class WorkerFeedback:
    """Actionable feedback for the next attempt of a workflow state."""

    source: str
    reason: str
    details: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "reason": self.reason,
            "details": list(self.details),
        }


class WorkerOutputError(RuntimeError):
    """Raised when worker execution succeeds but its output is invalid."""

    def __init__(
        self,
        *,
        source: str,
        reason: str,
        details: list[str] | None = None,
    ) -> None:
        self.feedback = WorkerFeedback(
            source=source,
            reason=reason,
            details=tuple(details or []),
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
    """Remove feedback after a workflow state succeeds."""

    feedback_path(
        context_dir,
        state_name,
    ).unlink(
        missing_ok=True,
    )