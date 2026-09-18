"""Table-driven tests for runtime.workflow.transitions.next_state over the
`feature` workflow's states x outcomes.
"""

from pathlib import Path

import pytest

from assembler.dsl_parser import parse_execution_policy, parse_workflow_file
from runtime.workflow import transitions

CANONICAL_DIR = Path(__file__).resolve().parent.parent.parent / "canonical"
FEATURE_PATH = CANONICAL_DIR / "workflows" / "feature.workflow.yaml"
POLICY_PATH = CANONICAL_DIR / "workflows" / "shared" / "execution-policy.yaml"


@pytest.fixture
def workflow():
    return parse_workflow_file(FEATURE_PATH, CANONICAL_DIR)


@pytest.fixture
def policy():
    return parse_execution_policy(POLICY_PATH)


def test_success_advances_to_next_state(workflow, policy):
    result = transitions.next_state(workflow, "jira-ingest", "success", {}, policy)
    assert result.next_state == "plan"
    assert result.retry_counts == {}


def test_self_loop_failure_retries_until_exhaustion(workflow, policy):
    # plan: max_attempts=2, failure target is itself -> a real retry loop.
    result = transitions.next_state(workflow, "plan", "failure", {}, policy)
    assert result.next_state == "plan"
    assert result.retry_counts == {"plan": 1}
    assert not result.escalated_due_to_retry_exhaustion

    result2 = transitions.next_state(workflow, "plan", "failure", result.retry_counts, policy)
    assert result2.next_state == "human-review"
    assert result2.retry_counts == {"plan": 2}
    assert result2.escalated_due_to_retry_exhaustion


def test_review_failure_routes_to_implement_without_counting(workflow, policy):
    # review: failure target != "review" -> forward routing, not a retry;
    # review's own max_attempts is not consulted here (see docstring above).
    result = transitions.next_state(workflow, "review", "failure", {}, policy)
    assert result.next_state == "implement"
    assert result.retry_counts == {}
    assert not result.escalated_due_to_retry_exhaustion


def test_workflow_level_max_total_iterations_parsed(workflow):
    assert workflow.max_total_iterations == 20


def test_explicit_escalate_outcome(workflow, policy):
    result = transitions.next_state(workflow, "plan", "escalate", {}, policy)
    assert result.next_state == "human-review"


def test_terminal_state_raises(workflow, policy):
    with pytest.raises(ValueError):
        transitions.next_state(workflow, "done", "success", {}, policy)


def test_unknown_outcome_raises(workflow, policy):
    with pytest.raises(ValueError):
        transitions.next_state(workflow, "plan", "maybe", {}, policy)


@pytest.mark.parametrize(
    "state_name,outcome,expected_next",
    [
        ("jira-ingest", "success", "plan"),
        ("plan", "success", "implement"),
        ("implement", "success", "review"),
        ("review", "success", "submit"),
        ("submit", "success", "done"),
    ],
)
def test_happy_path_progression(workflow, policy, state_name, outcome, expected_next):
    result = transitions.next_state(workflow, state_name, outcome, {}, policy)
    assert result.next_state == expected_next
