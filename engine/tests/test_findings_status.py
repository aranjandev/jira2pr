"""Review findings carry a status, are archived per cycle, and show up in the state."""

import json
from pathlib import Path

from runtime.workflow.feedback import (
    FINDING_ADDRESSED,
    FINDING_PENDING,
    FINDING_REOPENED,
    archive_findings,
    open_findings,
    open_findings_summary,
    read_findings,
    reopen_addressed_findings,
    set_finding_status,
    write_findings,
)


def _findings(tmp_path: Path) -> Path:
    write_findings(
        context_dir=tmp_path,
        state_name="implement",
        findings=[
            {"file": "src/a.py", "instruction": "Fix A."},
            {"file": "src/b.py", "instruction": "Fix B."},
        ],
    )
    return tmp_path


def test_new_findings_start_pending(tmp_path: Path):
    context = _findings(tmp_path)

    statuses = [f["status"] for f in read_findings(context, "implement")]

    assert statuses == [FINDING_PENDING, FINDING_PENDING]
    assert len(open_findings(read_findings(context, "implement"))) == 2


def test_completing_a_task_addresses_only_its_file(tmp_path: Path):
    context = _findings(tmp_path)

    changed = set_finding_status(
        context_dir=context,
        state_name="implement",
        file="src/a.py",
        status=FINDING_ADDRESSED,
        only_from=frozenset({FINDING_PENDING, FINDING_REOPENED}),
    )

    by_file = {f["file"]: f["status"] for f in read_findings(context, "implement")}
    assert changed == 1
    assert by_file == {"src/a.py": FINDING_ADDRESSED, "src/b.py": FINDING_PENDING}
    assert [f["file"] for f in open_findings(read_findings(context, "implement"))] == ["src/b.py"]


def test_failing_verification_reopens_addressed_findings(tmp_path: Path):
    context = _findings(tmp_path)
    set_finding_status(
        context_dir=context,
        state_name="implement",
        file="src/a.py",
        status=FINDING_ADDRESSED,
        only_from=frozenset({FINDING_PENDING}),
    )

    reopened = reopen_addressed_findings(context_dir=context, state_name="implement")

    by_file = {f["file"]: f["status"] for f in read_findings(context, "implement")}
    assert reopened == 1
    assert by_file == {"src/a.py": FINDING_REOPENED, "src/b.py": FINDING_PENDING}


def test_archive_moves_the_cycle_and_numbers_it(tmp_path: Path):
    context = _findings(tmp_path)
    first = archive_findings(context_dir=context, state_name="implement")

    write_findings(
        context_dir=context,
        state_name="implement",
        findings=[{"file": "src/c.py", "instruction": "Fix C."}],
    )
    second = archive_findings(context_dir=context, state_name="implement")

    assert first is not None and first.name == "implement-findings-1.json"
    assert second is not None and second.name == "implement-findings-2.json"
    assert not (context / "implement-findings.json").exists()
    assert json.loads(second.read_text())["findings"][0]["file"] == "src/c.py"


def test_state_summary_lists_only_open_findings(tmp_path: Path):
    context = _findings(tmp_path)
    set_finding_status(
        context_dir=context,
        state_name="implement",
        file="src/a.py",
        status=FINDING_ADDRESSED,
        only_from=frozenset({FINDING_PENDING}),
    )

    summary = open_findings_summary(context_dir=context, state_names=["implement", "review"])

    assert summary == [
        {"state": "implement", "file": "src/b.py", "instruction": "Fix B.", "status": FINDING_PENDING}
    ]
