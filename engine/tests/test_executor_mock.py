"""End-to-end tests for the workflow executor, driven entirely by MockBackend
(no network, no real LLM/aider calls).
"""

from pathlib import Path

import pytest

from assembler.platforms.aider import AiderAssembler
from assembler.registry import CanonicalRegistry
from assembler.writer import FileWriter
from runtime.backends.mock import MockBackend
from runtime.workflow.executor import WorkflowExecutor
from runtime.workflow.loader import RuntimeProject
from runtime.workflow.state_manager import StateManager

CANONICAL_DIR = Path(__file__).resolve().parent.parent.parent / "canonical"

SUCCESS_YAML = "outcome: success\nreason: ok\nfeedback: ''\nviolations: []\n"


@pytest.fixture
def project(tmp_path):
    reg = CanonicalRegistry.load(CANONICAL_DIR)
    writer = FileWriter(tmp_path)
    AiderAssembler().assemble(reg, writer)
    writer.finalize()
    return RuntimeProject.load(tmp_path)


def _always_succeed(system_prompt, user_prompt, model):
    if "Required success criteria" in user_prompt:
        return SUCCESS_YAML
    return "# Content\n\nGenerated.\n"


def test_happy_path_reaches_done(project):
    backend = MockBackend(responder=_always_succeed)
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-1")
    assert state.status == "completed"
    assert state.current_state == "done"
    assert [h["state"] for h in state.history] == [
        "jira-ingest", "plan", "implement", "review", "submit",
    ]
    assert set(state.artifacts) == {"requirements.md", "plan.md", "review.md"}


def test_retry_then_escalation(project):
    def responder(system_prompt, user_prompt, model):
        if "State: implement" in user_prompt and "Required success criteria" in user_prompt:
            return "outcome: failure\nreason: broken\nfeedback: fix\nviolations: [tests_pass]\n"
        if "Required success criteria" in user_prompt:
            return SUCCESS_YAML
        return "# Content\n"

    backend = MockBackend(responder=responder)
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-2")
    assert state.status == "escalated"
    assert state.current_state == "human-review"
    assert state.retry_counts == {"implement": 2}
    assert state.escalations[0]["state"] == "implement"
    assert [h["outcome"] for h in state.history] == ["success", "success", "failure", "failure"]


def test_global_iteration_cap_forces_escalation_on_unbounded_rework_loop(project):
    # implement always succeeds but review always rejects it: implement's own
    # retry_counts never increments (it only fails on its OWN failure), and
    # review's failure routes to implement (not itself), so no per-state cap
    # ever trips. Only the workflow-level max_total_iterations (20) should
    # stop this from looping forever.
    def responder(system_prompt, user_prompt, model):
        if "State: review" in user_prompt and "Required success criteria" in user_prompt:
            return "outcome: failure\nreason: needs more work\nfeedback: fix\nviolations: [no_critical_findings]\n"
        if "Required success criteria" in user_prompt:
            return SUCCESS_YAML
        return "# Content\n"

    backend = MockBackend(responder=responder)
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-5")
    assert state.status == "escalated"
    assert state.current_state == "human-review"
    assert state.total_iterations == 20
    assert state.retry_counts == {}
    assert "iteration cap" in state.escalations[-1]["reason"]


def test_malformed_supervisor_output_treated_as_failure(project):
    backend = MockBackend()  # default response is not valid supervisor YAML
    state = WorkflowExecutor(project, backend).start("feature", "PROJ-3")
    # jira-ingest's default max_attempts is 1 -> immediate escalation on first failure.
    assert state.status == "escalated"
    assert state.history[0]["outcome"] == "failure"


def test_resume_continues_from_saved_state(project):
    sm = StateManager(project.core_dir)
    sm.create("PROJ-4", "feature", "implement")
    seeded = sm.load("PROJ-4")
    seeded.history = [
        {"timestamp": "t", "state": "jira-ingest", "attempt": 1, "outcome": "success", "notes": ""}
    ]
    seeded.artifacts = ["requirements.md"]
    sm.save("PROJ-4", seeded)

    backend = MockBackend(responder=_always_succeed)
    state = WorkflowExecutor(project, backend).resume("PROJ-4")
    assert [h["state"] for h in state.history] == ["jira-ingest", "implement", "review", "submit"]
    assert state.status == "completed"
