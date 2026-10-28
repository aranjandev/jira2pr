"""Table-driven tests for runtime.workflow.transitions.next_state over the
`feature` workflow's states x outcomes.
"""

from pathlib import Path

import pytest
from assembler.dsl_parser import parse_execution_policy, parse_workflow_file
from assembler.model import StateSpec, TransitionSpec, WorkflowSpec
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
    # plan: max_attempts=3, failure target is itself -> a real retry loop.
    result = transitions.next_state(workflow, "plan", "failure", {}, policy)
    assert result.next_state == "plan"
    assert result.retry_counts == {"plan": 1}
    assert not result.escalated_due_to_retry_exhaustion

    result2 = transitions.next_state(workflow, "plan", "failure", result.retry_counts, policy)
    assert result2.next_state == "plan"
    assert result2.retry_counts == {"plan": 2}
    assert not result2.escalated_due_to_retry_exhaustion

    result3 = transitions.next_state(workflow, "plan", "failure", result2.retry_counts, policy)
    assert result3.next_state == "human-review"
    assert result3.retry_counts == {"plan": 3}
    assert result3.escalated_due_to_retry_exhaustion


def test_review_failure_routes_to_implement_and_counts_attempts(workflow, policy):
    # review changes_requested routes to implement and draws from the shared
    # implement-cycle budget.
    result = transitions.next_state(workflow, "review", "failure", {}, policy)
    assert result.next_state == "implement"
    assert result.retry_counts == {"implement-cycle": 1}


def test_run_tests_failure_routes_to_implement_and_counts_attempts(workflow, policy):
    result = transitions.next_state(workflow, "run-tests", "failure", {}, policy)
    assert result.next_state == "implement"
    assert result.retry_counts == {"implement-cycle": 1}
    assert not result.escalated_due_to_retry_exhaustion


def test_run_tests_and_review_share_implement_cycle_budget(workflow, policy):
    # Four cycles already used, by any mix of run-tests and review failures.
    # The fifth failure, from either state, exhausts the shared budget.
    used = {"implement-cycle": 4}
    result = transitions.next_state(workflow, "run-tests", "failure", used, policy)
    assert result.next_state == "human-review"
    assert result.retry_counts == {"implement-cycle": 5}
    assert result.escalated_due_to_retry_exhaustion

    result = transitions.next_state(workflow, "review", "failure", used, policy)
    assert result.next_state == "human-review"
    assert result.escalated_due_to_retry_exhaustion


def test_per_task_counter_name_is_independent(workflow, policy):
    # implement's own failures count under the per-task name, not the state name.
    result = transitions.next_state(
        workflow, "implement", "failure", {"implement:T1": 3}, policy, counter_name="implement:T4"
    )
    assert result.next_state == "implement"
    assert result.retry_counts == {"implement:T1": 3, "implement:T4": 1}
    assert not result.escalated_due_to_retry_exhaustion


def test_review_invalid_output_retries_review_not_implement(workflow, policy):
    # A malformed review.md is the reviewer's problem, not the coder's.
    result = transitions.next_state(workflow, "review", "invalid_output", {}, policy)
    assert result.next_state == "review"
    assert result.retry_counts == {"review": 1}


def test_cross_state_failure_without_max_attempts_is_plain_routing(policy):
    # A cross-state failure from a state without explicit max_attempts must not
    # consume any budget (forward routing, not a cycle).
    workflow = WorkflowSpec(
        name="t",
        version=1,
        initial_state="a",
        states={
            "a": StateSpec(
                name="a",
                worker="w",
                transitions=TransitionSpec(success="b", failure="b", escalate="h"),
            ),
            "b": StateSpec(name="b", worker="w"),
            "h": StateSpec(name="h", terminal=True, outcome="escalated"),
        },
    )
    result = transitions.next_state(workflow, "a", "failure", {}, policy)
    assert result.next_state == "b"
    assert result.retry_counts == {}


def test_workflow_level_max_total_iterations_parsed(workflow):
    assert workflow.max_total_iterations == 30


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
        ("implement", "success", "run-tests"),
        ("run-tests", "success", "review"),
        ("review", "success", "submit"),
        ("submit", "success", "done"),
    ],
)
def test_happy_path_progression(workflow, policy, state_name, outcome, expected_next):
    result = transitions.next_state(workflow, state_name, outcome, {}, policy)
    assert result.next_state == expected_next
