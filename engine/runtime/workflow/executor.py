"""The workflow executor — drives a workflow from its current state to a terminal one.

Loop: invoke worker -> invoke supervisor -> compute transition -> persist
state -> repeat. Every iteration is a single, atomically-saved step, so a
crash between iterations loses at most the in-flight step (resumable via
`resume()`, which just re-reads the last saved state and continues).
"""

from __future__ import annotations

from runtime.backends.base import LLMBackend
from runtime.workflow import transitions
from runtime.workflow.loader import RuntimeProject
from runtime.workflow.state_manager import StateManager, WorkflowState
from runtime.workflow.supervisor_invoker import invoke_supervisor
from runtime.workflow.worker_invoker import invoke_worker


class WorkflowExecutor:
    def __init__(self, project: RuntimeProject, backend: LLMBackend) -> None:
        self._project = project
        self._backend = backend
        self._state_manager = StateManager(project.core_dir)

    def start(self, workflow_name: str, ticket_key: str) -> WorkflowState:
        """Create fresh state for *ticket_key* and run to completion/escalation."""
        workflow = self._project.workflow(workflow_name)
        self._state_manager.create(ticket_key, workflow_name, workflow.initial_state)
        return self.run(ticket_key)

    def resume(self, ticket_key: str) -> WorkflowState:
        """Continue a previously started workflow from its saved state."""
        return self.run(ticket_key)

    def run(self, ticket_key: str) -> WorkflowState:
        state = self._state_manager.load(ticket_key)
        workflow = self._project.workflow(state.workflow)
        policy = self._project.execution_policy

        while True:
            current = workflow.states[state.current_state]
            if current.terminal:
                state.status = "completed" if current.outcome == "success" else "escalated"
                self._state_manager.save(ticket_key, state)
                return state

            max_total_iterations = (
                workflow.max_total_iterations
                if workflow.max_total_iterations is not None
                else policy.max_total_iterations
            )
            if state.total_iterations >= max_total_iterations:
                # Global safety net: bounds oscillation between ANY states (not just
                # self-looping ones), independent of every state's own max_attempts.
                state.record_escalation(
                    current.name,
                    f"global iteration cap ({max_total_iterations}) exceeded; "
                    "possible transition cycle",
                )
                state.current_state = policy.terminal_escalated_state
                self._state_manager.save(ticket_key, state)
                continue

            state.total_iterations += 1
            attempt = state.retry_counts.get(current.name, 0) + 1
            produced = invoke_worker(self._project, workflow, current, ticket_key, self._backend)
            result = invoke_supervisor(
                self._project, workflow, current, ticket_key, produced, self._backend
            )
            outcome = result["outcome"]

            for name in produced:
                if name not in state.artifacts:
                    state.artifacts.append(name)

            transition = transitions.next_state(
                workflow, current.name, outcome, state.retry_counts, policy
            )
            state.retry_counts = transition.retry_counts
            state.record_history(current.name, attempt, outcome, notes=result.get("reason", ""))
            if transition.escalated_due_to_retry_exhaustion:
                state.record_escalation(current.name, "retry attempts exhausted")
            elif outcome == "escalate":
                state.record_escalation(current.name, result.get("reason", ""))

            state.current_state = transition.next_state
            self._state_manager.save(ticket_key, state)
