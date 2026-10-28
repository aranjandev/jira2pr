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
class ReviewFinding:
    """A blocking issue the coder must fix in one planned file."""

    file: str
    instruction: str


@dataclass(frozen=True)
class ReviewDecision:
    verdict: str
    reason: str
    findings: tuple[ReviewFinding, ...] = ()


def planned_file_paths(plan_path: Path) -> frozenset[str]:
    """Return the file_path of every task in plan.yaml."""

    data = yaml.safe_load(plan_path.read_text(encoding="utf-8")) or {}
    return frozenset(
        str(task["file_path"])
        for task in data.get("tasks") or []
        if isinstance(task, dict) and task.get("file_path")
    )


def _parse_findings(
    raw: object,
    allowed_files: frozenset[str] | None,
) -> tuple[ReviewFinding, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ReviewDecisionError("review-verdict findings must be a list")

    findings: list[ReviewFinding] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ReviewDecisionError(f"finding {index} must be a mapping with file and instruction")

        file = item.get("file")
        instruction = item.get("instruction")
        if not isinstance(file, str) or not file.strip():
            raise ReviewDecisionError(f"finding {index} must name a non-empty file")
        if not isinstance(instruction, str) or not instruction.strip():
            raise ReviewDecisionError(f"finding {index} must include a non-empty instruction")

        normalized = file.strip().removeprefix("./")
        if allowed_files is not None and normalized not in allowed_files:
            raise ReviewDecisionError(
                f"finding {index} names {normalized!r}, which is not a file_path in plan.yaml"
            )
        findings.append(ReviewFinding(file=normalized, instruction=instruction.strip()))

    return tuple(findings)


def load_review_decision(
    review_path: Path,
    allowed_files: frozenset[str] | None = None,
) -> ReviewDecision:
    """Parse the trailing review-verdict block from review.md.

    When ``allowed_files`` is given, every finding must name one of them.
    A ``changes_requested`` verdict must include at least one finding.
    """

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

    findings = _parse_findings(data.get("findings"), allowed_files)
    if verdict == "changes_requested" and not findings:
        raise ReviewDecisionError(
            "changes_requested must include at least one finding with file and instruction"
        )

    return ReviewDecision(
        verdict=verdict,
        reason=reason.strip(),
        findings=findings,
    )