"""Parsing of machine-readable reviewer decisions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_REVIEW_VERDICT_RE = re.compile(
    r"```review-verdict\s*\n"
    r"(?P<content>.*?)"
    r"\n```\s*$",
    re.DOTALL,
)

_ALLOWED_VERDICTS = {
    "approve",
    "changes_requested",
    "escalate",
}


class ReviewDecisionError(RuntimeError):
    """Raised when review.md does not contain a valid verdict."""


@dataclass(frozen=True)
class ReviewDecision:
    verdict: str
    reason: str


def load_review_decision(
    review_path: Path,
) -> ReviewDecision:
    """Parse the trailing review-verdict block from review.md."""

    if not review_path.is_file():
        raise ReviewDecisionError(
            f"Review artifact not found: {review_path}"
        )

    content = review_path.read_text(
        encoding="utf-8",
    )

    match = _REVIEW_VERDICT_RE.search(
        content
    )

    if match is None:
        raise ReviewDecisionError(
            "review.md must end with a review-verdict block"
        )

    try:
        data = yaml.safe_load(
            match.group("content")
        )
    except yaml.YAMLError as exc:
        raise ReviewDecisionError(
            f"Invalid review-verdict YAML: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ReviewDecisionError(
            "review-verdict must contain a YAML mapping"
        )

    verdict = data.get(
        "verdict"
    )

    reason = data.get(
        "reason"
    )

    if verdict not in _ALLOWED_VERDICTS:
        raise ReviewDecisionError(
            f"Invalid review verdict: {verdict!r}"
        )

    if not isinstance(reason, str) or not reason.strip():
        raise ReviewDecisionError(
            "review-verdict must contain a non-empty reason"
        )

    return ReviewDecision(
        verdict=verdict,
        reason=reason.strip(),
    )