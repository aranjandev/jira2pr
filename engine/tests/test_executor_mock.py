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
from runtime.backends.base import BackendInvocationError
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
        "jira-ingest", "plan", "implement", "run-tests", "review", "submit",
    ]
    assert set(state.artifacts) == {"requirements.md", "plan.yaml", "review.md", "pr-description.md"}

    ops = [c["op"] for c in backend.calls]
    # One edit per plan task/test; implement and review need no supervisor call.
    assert ops.count("edit_repository") == 2
    assert "fix_repository" not in ops
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


def test_failed_verification_routes_fix_back_to_implement(project, fake_subprocess):
    # First `make test` fails. The coder gets the failure as feedback on
    # re-entry and fixes it. The second verification passes.
    fake_subprocess.test_exit_codes = [1]
    backend = MockBackend()
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-6")
    assert state.status == "completed"
    assert state.retry_counts == {"implement-cycle": 1}
    assert [c["op"] for c in backend.calls].count("fix_repository") == 1
    assert [h["state"] for h in state.history] == [
        "jira-ingest", "plan", "implement", "run-tests",
        "implement", "run-tests", "review", "submit",
    ]


def test_verification_failing_twice_then_passes(project, fake_subprocess):
    fake_subprocess.test_exit_codes = [1, 1]
    backend = MockBackend()
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-7")
    assert state.status == "completed"
    assert state.retry_counts == {"implement-cycle": 2}
    assert [c["op"] for c in backend.calls].count("fix_repository") == 2
    assert [h["state"] for h in state.history].count("implement") == 3


def test_verification_budget_exhausted_escalates(project, fake_subprocess):
    # run-tests allows 3 attempts. Three failed verifications escalate.
    fake_subprocess.test_exit_codes = [1, 1, 1, 1, 1]
    backend = MockBackend()
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-9")
    assert state.status == "escalated"
    assert state.current_state == "human-review"
    assert state.retry_counts == {"implement-cycle": 5}
    assert state.escalations[-1]["state"] == "run-tests"
    assert "retry attempts exhausted" in state.escalations[-1]["reason"]


def test_review_changes_requested_routes_to_implement_then_rereviews(project, fake_subprocess):
    reviews = iter([CHANGES_REQUESTED_REVIEW])
    backend = MockBackend(
        artifact_responder=lambda name: next(reviews, None) if name == "review.md" else None,
    )
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-8")
    assert state.status == "completed"
    ops = [c["op"] for c in backend.calls]
    assert "remediate_review" not in ops
    # Review findings use the coder edit path (2 tasks first pass, 2 on re-entry).
    assert "fix_repository" not in ops
    assert ops.count("edit_repository") == 4
    assert state.retry_counts == {"implement-cycle": 1}
    assert [h["state"] for h in state.history].count("review") == 2


def test_malformed_review_artifact_reruns_review_not_implement(project, fake_subprocess):
    reviews = iter(["# Review\n\nNo verdict block here.\n"])
    backend = MockBackend(
        artifact_responder=lambda name: next(reviews, None) if name == "review.md" else None,
    )
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-10")
    assert state.status == "completed"
    assert [h["state"] for h in state.history if h["state"] in ("review", "implement")] == [
        "implement", "review", "review",
    ]
    assert [c["op"] for c in backend.calls].count("fix_repository") == 0
    assert state.retry_counts == {"review": 1}


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
    assert [h["state"] for h in state.history] == ["jira-ingest", "implement", "run-tests", "review", "submit"]
    assert state.status == "completed"


class NoEditBackend(MockBackend):
    """Accepts edit and fix calls but leaves every file untouched."""

    def edit_repository(self, **kwargs):
        self.calls.append({"op": "edit_repository", "files": [str(p) for p in kwargs["edit_files"]]})

    def fix_repository(self, **kwargs):
        self.calls.append({"op": "fix_repository", "files": [str(p) for p in kwargs["edit_files"]]})


class FlakyBackend(MockBackend):
    """Raises a backend invocation error on the first coder call, then works."""

    def __init__(self) -> None:
        super().__init__()
        self.failures_left = 1

    def _maybe_fail(self) -> None:
        if self.failures_left:
            self.failures_left -= 1
            raise BackendInvocationError("Aider timed out after 600s")

    def edit_repository(self, **kwargs):
        self._maybe_fail()
        return super().edit_repository(**kwargs)

    def fix_repository(self, **kwargs):
        self._maybe_fail()
        return super().fix_repository(**kwargs)


def test_empty_diff_counts_as_implement_failure_and_escalates(project, fake_subprocess):
    # implement allows 2 attempts. Both produce no change, so it escalates.
    backend = NoEditBackend()
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-11")
    assert state.status == "escalated"
    assert state.current_state == "human-review"
    assert state.retry_counts == {"implement": 2}
    implement_history = [h for h in state.history if h["state"] == "implement"]
    assert [h["outcome"] for h in implement_history] == ["failure", "failure"]
    assert all("no changes" in h["notes"] for h in implement_history)
    assert "run-tests" not in [h["state"] for h in state.history]


def test_backend_error_counts_as_implement_failure_then_recovers(project, fake_subprocess):
    backend = FlakyBackend()
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-12")
    assert state.status == "completed"
    assert state.retry_counts == {"implement": 1}
    failed = [h for h in state.history if h["state"] == "implement" and h["outcome"] == "failure"]
    assert len(failed) == 1
    assert "coder backend call failed" in failed[0]["notes"]
    assert "Aider timed out" in failed[0]["notes"]
    # Backend failures retry through the coder edit path, not the test-repair mode.
    assert "fix_repository" not in [c["op"] for c in backend.calls]


class SecondTaskNoOpBackend(MockBackend):
    """The second edit call of the first attempt changes nothing."""

    def __init__(self) -> None:
        super().__init__()
        self.edit_calls = 0

    def edit_repository(self, **kwargs):
        self.edit_calls += 1
        if self.edit_calls == 2:
            self.calls.append({"op": "edit_repository", "files": [str(p) for p in kwargs["edit_files"]]})
            return
        return super().edit_repository(**kwargs)


def test_task_without_change_fails_attempt_at_that_task(project, fake_subprocess):
    backend = SecondTaskNoOpBackend()
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-13")
    assert state.status == "completed"
    assert state.retry_counts == {"implement": 1}
    failed = [h for h in state.history if h["state"] == "implement" and h["outcome"] == "failure"]
    assert len(failed) == 1
    assert "made no changes" in failed[0]["notes"]
    # Attempt 2 resumes at T2. T1's edit from attempt 1 is kept and not re-run.
    assert backend.edit_calls == 3
    edited = [c["files"][0] for c in backend.calls if c["op"] == "edit_repository"]
    assert edited[0] != edited[1]
    assert edited[2] == edited[1]


class SecondTaskFailsOnceBackend(MockBackend):
    """The second task's first edit call raises a backend error."""

    def __init__(self) -> None:
        super().__init__()
        self.edit_calls = 0

    def edit_repository(self, **kwargs):
        self.edit_calls += 1
        if self.edit_calls == 2:
            raise BackendInvocationError("Aider timed out after 600s")
        return super().edit_repository(**kwargs)


def test_backend_error_resumes_at_failed_task(project, fake_subprocess):
    backend = SecondTaskFailsOnceBackend()
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-14")
    assert state.status == "completed"
    assert state.retry_counts == {"implement": 1}
    # Attempt 1 made two calls (T1, then T2 failing). Attempt 2 made one call, for T2 only.
    assert backend.edit_calls == 3
    edited = [c["files"][0] for c in backend.calls if c["op"] == "edit_repository"]
    assert len(edited) == 2 and edited[0] != edited[1]
