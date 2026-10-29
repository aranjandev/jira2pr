"""Structured review findings: parsed from the review-verdict block and checked against the plan."""

from pathlib import Path

import pytest
from runtime.workflow.review import ReviewDecisionError, load_review_decision

PLAN_FILES = frozenset({"tools/main.py", "tests/test_main.py"})


def _review(tmp_path: Path, block: str) -> Path:
    path = tmp_path / "review.md"
    path.write_text(f"# Review\n\nBody.\n\n```review-verdict\n{block}\n```\n", encoding="utf-8")
    return path


def test_valid_findings_are_parsed(tmp_path: Path):
    path = _review(
        tmp_path,
        "verdict: changes_requested\n"
        'reason: "Duplicates are not removed."\n'
        "findings:\n"
        "  - file: tools/main.py\n"
        "    instruction: Discard inputs of duplicate rows.\n",
    )

    decision = load_review_decision(path, allowed_files=PLAN_FILES)

    assert decision.verdict == "changes_requested"
    assert [(f.file, f.instruction) for f in decision.findings] == [
        ("tools/main.py", "Discard inputs of duplicate rows.")
    ]


def test_changes_requested_without_findings_is_rejected(tmp_path: Path):
    path = _review(tmp_path, 'verdict: changes_requested\nreason: "Needs work."')

    with pytest.raises(ReviewDecisionError, match="at least one finding"):
        load_review_decision(path, allowed_files=PLAN_FILES)


def test_finding_outside_the_plan_is_rejected(tmp_path: Path):
    path = _review(
        tmp_path,
        "verdict: changes_requested\n"
        'reason: "Needs work."\n'
        "findings:\n"
        "  - file: tools/other.py\n"
        "    instruction: Change it.\n",
    )

    with pytest.raises(ReviewDecisionError, match="not a file_path in plan.yaml"):
        load_review_decision(path, allowed_files=PLAN_FILES)


def test_finding_without_instruction_is_rejected(tmp_path: Path):
    path = _review(
        tmp_path,
        "verdict: changes_requested\n"
        'reason: "Needs work."\n'
        "findings:\n"
        "  - file: tools/main.py\n",
    )

    with pytest.raises(ReviewDecisionError, match="non-empty instruction"):
        load_review_decision(path, allowed_files=PLAN_FILES)


def test_approve_needs_no_findings(tmp_path: Path):
    path = _review(tmp_path, 'verdict: approve\nreason: "Fine."')

    decision = load_review_decision(path, allowed_files=PLAN_FILES)

    assert decision.verdict == "approve"
    assert decision.findings == ()


def test_without_plan_files_findings_are_not_checked(tmp_path: Path):
    path = _review(
        tmp_path,
        "verdict: changes_requested\n"
        'reason: "Needs work."\n'
        "findings:\n"
        "  - file: ./tools/main.py\n"
        "    instruction: Fix it.\n",
    )

    decision = load_review_decision(path)

    assert decision.findings[0].file == "tools/main.py"
