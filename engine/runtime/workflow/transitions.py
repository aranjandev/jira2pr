"""Pure state-transition logic — no I/O, fully unit-testable.

Retry/escalation semantics (documented in
`canonical/workflows/shared/execution-policy.yaml`):

- `retry.max_attempts` bounds *cycle* failures. A state whose failure target is
  itself (jira-ingest, plan, implement, review) retries itself. A state that
  declares an explicit `retry.max_attempts` but fails into a different state
  (e.g. `run-tests` -> `implement`, `review` -> `implement`) is a counted cycle
  edge: each failure consumes its own budget, and exhaustion escalates.
- States whose failure transition points at a *different* state and that do not
  declare `max_attempts` are plain forward routing, not a retry loop. Any bound on
  such a cycle then comes from the downstream state's own max_attempts.
- A state with `retry.budget: <name>` draws its failures from the workflow-level
  budget `<name>` (`budgets:`), shared with any other state naming it. Budgets
  are cumulative for the run and are not reset on forward progress.
"""

from __future__ import annotations

from dataclasses import dataclass

from assembler.model import ExecutionPolicy, WorkflowSpec


@dataclass(frozen=True)
class TransitionResult:
    next_state: str
    retry_counts: dict[str, int]
    escalated_due_to_retry_exhaustion: bool = False


def next_state(
    workflow: WorkflowSpec,
    current_state_name: str,
    outcome: str,
    retry_counts: dict[str, int],
    policy: ExecutionPolicy,
    counter_name: str | None = None,
) -> TransitionResult:
    """Compute the next state name given a supervisor *outcome*.

    *counter_name* names the counter for a state's own cycle failures. It
    defaults to the state name. The runtime passes ``<state>:<task>`` so each
    implementation task gets its own attempt budget.

    *outcome* is one of "success", "failure", "invalid_output", "escalate".
    "invalid_output" is a failure caused by unusable worker output. It routes to
    ``transitions.invalid_output`` when declared, otherwise it behaves as "failure".
    """
    if outcome not in ("success", "failure", "invalid_output", "escalate"):
        raise ValueError(f"Unknown outcome: {outcome!r}")

    state = workflow.states.get(current_state_name)
    if state is None:
        raise ValueError(f"Unknown state: {current_state_name!r}")
    if state.terminal:
        raise ValueError(f"State {current_state_name!r} is terminal; no transitions apply")

    counts = dict(retry_counts)

    if outcome == "success":
        target = state.transitions.success
        if target is None:
            raise ValueError(f"State {current_state_name!r} has no success transition")
        return TransitionResult(next_state=target, retry_counts=counts)

    if outcome == "escalate":
        target = state.transitions.escalate or _fallback_escalation_state(workflow, policy)
        return TransitionResult(next_state=target, retry_counts=counts)

    # outcome is "failure" or "invalid_output"
    failure_target = state.transitions.failure
    if outcome == "invalid_output" and state.transitions.invalid_output is not None:
        failure_target = state.transitions.invalid_output
    if failure_target is None:
        raise ValueError(f"State {current_state_name!r} has no failure transition")

    is_self_loop = failure_target == current_state_name

    # A failure from a state that names a shared budget consumes that budget,
    # regardless of its target (e.g. run-tests and review -> implement share
    # "implement-cycle"). Unusable output keeps the state's own counter.
    if outcome == "failure" and state.budget is not None:
        counter_key = state.budget
        limit = workflow.budgets[state.budget]
    else:
        # A state with an explicit max_attempts that fails into another state is
        # a bounded cycle edge. Without one, cross-state failures are plain routing.
        is_counted_cycle = is_self_loop or state.max_attempts is not None
        if not is_counted_cycle:
            return TransitionResult(next_state=failure_target, retry_counts=counts)
        counter_key = counter_name or current_state_name
        limit = state.max_attempts if state.max_attempts is not None else policy.default_max_attempts

    attempts_so_far = counts.get(counter_key, 0) + 1
    counts[counter_key] = attempts_so_far

    if attempts_so_far >= limit and policy.on_exhaustion == "escalate":
        target = state.transitions.escalate or _fallback_escalation_state(workflow, policy)
        return TransitionResult(
            next_state=target, retry_counts=counts, escalated_due_to_retry_exhaustion=True
        )

    return TransitionResult(next_state=failure_target, retry_counts=counts)


def _fallback_escalation_state(workflow: WorkflowSpec, policy: ExecutionPolicy) -> str:
    if policy.terminal_escalated_state in workflow.states:
        return policy.terminal_escalated_state
    for state in workflow.states.values():
        if state.terminal and state.outcome == "escalated":
            return state.name
    raise ValueError("No escalation terminal state found in workflow")
