"""Pure state-transition logic — no I/O, fully unit-testable.

Retry/escalation semantics (documented in
`canonical/workflows/shared/execution-policy.yaml`):

- `retry.max_attempts` only bounds *self-looping* failures, i.e. states whose
  `transitions.failure` target is the state itself (jira-ingest, plan,
  implement all retry themselves this way). Exhausting the bound escalates
  instead of retrying again.
- States whose failure transition points at a *different* state (e.g.
  `review` failing routes to `implement`) are plain forward routing, not a
  retry loop — nothing to exhaust. Any effective bound on how many times that
  cycle can repeat comes from the downstream self-looping state's own
  max_attempts (e.g. `implement`'s), not from `review`'s.
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
) -> TransitionResult:
    """Compute the next state name given a supervisor *outcome*.

    *outcome* is one of "success", "failure", "escalate".
    """
    if outcome not in ("success", "failure", "escalate"):
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

    # outcome == "failure"
    failure_target = state.transitions.failure
    if failure_target is None:
        raise ValueError(f"State {current_state_name!r} has no failure transition")

    is_self_loop = failure_target == current_state_name
    if not is_self_loop:
        # Plain forward routing (e.g. review -> implement) — not a retry.
        return TransitionResult(next_state=failure_target, retry_counts=counts)

    attempts_so_far = counts.get(current_state_name, 0) + 1
    counts[current_state_name] = attempts_so_far
    max_attempts = (
        state.max_attempts if state.max_attempts is not None else policy.default_max_attempts
    )

    if attempts_so_far >= max_attempts and policy.on_exhaustion == "escalate":
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
