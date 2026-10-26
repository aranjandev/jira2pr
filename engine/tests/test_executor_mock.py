"""End-to-end tests for the workflow executor, driven entirely by MockBackend
(no network, no real LLM/aider calls, no real git/test/lint subprocesses).
"""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from assembler.platforms.runtime import RuntimeAssembler
from assembler.registry import CanonicalRegistry
from assembler.writer import FileWriter
from runtime.backends.mock import DEFAULT_PLAN, MockBackend
from runtime.workflow.executor import WorkflowExecutor
from runtime.workflow.loader import RuntimeProject
from runtime.workflow.state_manager import StateManager

CANONICAL_DIR = Path(__file__).resolve().parent.parent.parent / "canonical"

FAILURE_DECISION = json.dumps(
    {
        "outcome": "failure",
        "reason": "broken",
        "feedback": "fix it",
        "violations": ["requirements_covered"],
    }
)

CHANGES_REQUESTED_REVIEW = """\
# Review

Needs work.

```review-verdict
verdict: changes_requested
reason: Missing error handling.
```
"""


class FakeSubprocess:
    """Stand-in for subprocess.run covering capabilities, git, and verification."""

    def __init__(self) -> None:
        # Exit codes returned (in order) for `make test`; 0 once exhausted.
        self.test_exit_codes: list[int] = []

    def __call__(self, argv, *args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        result.stdout = ""

        text = argv if isinstance(argv, str) else " ".join(str(a) for a in argv)

        if "ls-files" in text:
            result.stdout = b"README.md\0"
        elif "jira.py" in text:
            result.stdout = "key: PROJ-1\nsummary: Test ticket\n"
        elif "git.py" in text:
            result.stdout = "On branch main\nNothing to commit\n"
        elif "github.py" in text:
            result.stdout = "PR_URL=https://github.com/test/test/pull/1\nPR_NUMBER=1\n"
        elif text == "make test" and self.test_exit_codes:
            result.returncode = self.test_exit_codes.pop(0)

        return result


@pytest.fixture
def project(tmp_path):
    reg = CanonicalRegistry.load(CANONICAL_DIR)
    writer = FileWriter(tmp_path)
    RuntimeAssembler().assemble(reg, writer)
    writer.finalize()
    return RuntimeProject.load(tmp_path)


@pytest.fixture
def fake_subprocess():
    fake = FakeSubprocess()
    with patch("subprocess.run", side_effect=fake):
        yield fake


def test_happy_path_reaches_done(project, fake_subprocess):
    backend = MockBackend()
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-1")
    assert state.status == "completed"
    assert state.current_state == "done"
    assert [h["state"] for h in state.history] == [
        "jira-ingest", "plan", "implement", "review", "submit",
    ]
    assert set(state.artifacts) == {"requirements.md", "plan.yaml", "review.md", "pr-description.md"}

    ops = [c["op"] for c in backend.calls]
    # One edit per plan task/test; implement and review need no supervisor call.
    assert ops.count("edit_repository") == 2
    assert [c["state"] for c in backend.calls if c["op"] == "produce_structured"] == [
        "jira-ingest", "plan", "submit",
    ]


def test_retry_then_escalation(project, fake_subprocess):
    backend = MockBackend(
        decision_responder=lambda s: FAILURE_DECISION if s == "plan" else None,
    )
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-2")
    assert state.status == "escalated"
    assert state.current_state == "human-review"
    assert state.retry_counts == {"plan": 2}
    assert state.escalations[0]["state"] == "plan"
    assert [h["outcome"] for h in state.history] == ["success", "failure", "failure"]


def test_global_iteration_cap_forces_escalation(project, fake_subprocess):
    # Every state succeeds, so no per-state retry cap can trip. Only the
    # workflow-level max_total_iterations should stop the run.
    project.workflows["feature"] = replace(project.workflows["feature"], max_total_iterations=3)

    state = WorkflowExecutor(project, MockBackend()).start("feature", "PROJ-5")
    assert state.status == "escalated"
    assert state.current_state == "human-review"
    assert state.total_iterations == 3
    assert state.retry_counts == {}
    assert "iteration cap" in state.escalations[-1]["reason"]


def test_malformed_supervisor_output_treated_as_failure(project, fake_subprocess):
    backend = MockBackend(decision_responder=lambda s: "not json")
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-3")
    # jira-ingest allows 2 attempts; both fail, so it escalates.
    assert state.status == "escalated"
    assert state.history[0]["outcome"] == "failure"
    assert state.retry_counts == {"jira-ingest": 2}


def test_failed_verification_triggers_one_repair(project, fake_subprocess):
    # First `make test` fails; after one repair it passes.
    fake_subprocess.test_exit_codes = [1]
    backend = MockBackend()
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-6")
    assert state.status == "completed"
    assert [c["op"] for c in backend.calls].count("repair_repository") == 1


def test_verification_still_failing_after_repair_retries_implement(project, fake_subprocess):
    # Fails before and after repair on the first attempt, then passes.
    fake_subprocess.test_exit_codes = [1, 1]
    backend = MockBackend()
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-7")
    assert state.status == "completed"
    assert state.retry_counts == {"implement": 1}
    assert [h["state"] for h in state.history].count("implement") == 2


def test_review_changes_requested_remediates_then_rereviews(project, fake_subprocess):
    reviews = iter([CHANGES_REQUESTED_REVIEW])
    backend = MockBackend(
        artifact_responder=lambda name: next(reviews, None) if name == "review.md" else None,
    )
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-8")
    assert state.status == "completed"
    assert [c["op"] for c in backend.calls].count("remediate_review") == 1
    assert [h["state"] for h in state.history].count("review") == 2


def test_resume_continues_from_saved_state(project, fake_subprocess):
    sm = StateManager(project.core_dir)
    sm.create("PROJ-4", "feature", "implement")
    seeded = sm.load("PROJ-4")
    seeded.history = [
        {"timestamp": "t", "state": "jira-ingest", "attempt": 1, "outcome": "success", "notes": ""}
    ]
    seeded.artifacts = ["requirements.md", "plan.yaml"]
    sm.save("PROJ-4", seeded)

    artifacts = project.artifacts_dir("PROJ-4")
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "requirements.md").write_text("# Requirements\n", encoding="utf-8")
    (artifacts / "plan.yaml").write_text(DEFAULT_PLAN, encoding="utf-8")

    state = WorkflowExecutor(project, MockBackend()).resume("PROJ-4")
    assert [h["state"] for h in state.history] == ["jira-ingest", "implement", "review", "submit"]
    assert state.status == "completed"
