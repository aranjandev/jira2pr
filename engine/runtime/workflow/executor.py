"""The workflow executor — drives a workflow from its current state to a terminal one.

Loop: invoke worker -> invoke supervisor -> compute transition -> persist
state -> repeat. Every iteration is a single, atomically-saved step, so a
crash between iterations loses at most the in-flight step (resumable via
`resume()`, which just re-reads the last saved state and continues).
"""

from __future__ import annotations

from runtime.backends.base import LLMBackend
from runtime.logging_config import get_logger
from runtime.workflow import transitions
from runtime.workflow.loader import RuntimeProject
from runtime.workflow.state_manager import StateManager, WorkflowState
from runtime.workflow.supervisor_invoker import invoke_supervisor
from runtime.workflow.worker_invoker import invoke_worker

logger = get_logger("workflow.executor")


class WorkflowExecutor:
    def __init__(self, project: RuntimeProject, backend: LLMBackend) -> None:
        self._project = project
        self._backend = backend
        self._state_manager = StateManager(project.core_dir)
        logger.debug(f"WorkflowExecutor initialized with backend: {backend.__class__.__name__}")

    def start(self, workflow_name: str, ticket_key: str) -> WorkflowState:
        """Create fresh state for *ticket_key* and run to completion/escalation."""
        logger.info(f"Starting new workflow: {workflow_name} for ticket: {ticket_key}")
        workflow = self._project.workflow(workflow_name)
        self._state_manager.create(ticket_key, workflow_name, workflow.initial_state)
        logger.debug(f"Created initial state for {ticket_key} at state: {workflow.initial_state}")
        return self.run(ticket_key)

    def resume(self, ticket_key: str) -> WorkflowState:
        """Continue a previously started workflow from its saved state."""
        logger.info(f"Resuming workflow for ticket: {ticket_key}")
        return self.run(ticket_key)

    def run(self, ticket_key: str) -> WorkflowState:
        logger.info(f"Running workflow for ticket: {ticket_key}")
        state = self._state_manager.load(ticket_key)
        logger.info(f"Loaded state for {ticket_key}: workflow={state.workflow}, current_state={state.current_state}")
        workflow = self._project.workflow(state.workflow)
        policy = self._project.execution_policy

        iteration = 0
        while True:
            iteration += 1
            current = workflow.states[state.current_state]
            logger.debug(f"[Iteration {iteration}] Current state: {current.name}, Terminal: {current.terminal}")

            if current.terminal:
                state.status = "completed" if current.outcome == "success" else "escalated"
                self._state_manager.save(ticket_key, state)
                logger.info(f"Workflow reached terminal state: {current.name} (outcome={current.outcome})")
                logger.info(f"Final status: {state.status}")
                return state

            max_total_iterations = (
                workflow.max_total_iterations
                if workflow.max_total_iterations is not None
                else policy.max_total_iterations
            )
            if state.total_iterations >= max_total_iterations:
                # Global safety net: bounds oscillation between ANY states (not just
                # self-looping ones), independent of every state's own max_attempts.
                logger.warning(
                    f"Global iteration cap ({max_total_iterations}) exceeded at state {current.name}. "
                    "Escalating due to possible transition cycle."
                )
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
            logger.info(
                f"[Iteration {iteration}] Processing state: {current.name} (attempt {attempt}, "
                f"total iterations: {state.total_iterations})"
            )

            try:
                logger.debug(f"Invoking worker for state: {current.name}")
                produced = invoke_worker(
                    self._project, workflow, current, ticket_key, self._backend
                )
                logger.debug(f"Worker produced artifacts: {list(produced.keys())}")

                logger.debug(f"Invoking supervisor for state: {current.name}")
                result = invoke_supervisor(
                    self._project, workflow, current, ticket_key, produced, self._backend
                )
                outcome = result["outcome"]
                logger.info(f"Supervisor outcome: {outcome}, Reason: {result.get('reason', 'N/A')}")

                for name in produced:
                    if name not in state.artifacts:
                        state.artifacts.append(name)

                transition = transitions.next_state(
                    workflow, current.name, outcome, state.retry_counts, policy
                )
                state.retry_counts = transition.retry_counts
                state.record_history(current.name, attempt, outcome, notes=result.get("reason", ""))

                if transition.escalated_due_to_retry_exhaustion:
                    logger.warning(f"Escalating due to retry attempts exhausted for state: {current.name}")
                    state.record_escalation(current.name, "retry attempts exhausted")
                elif outcome == "escalate":
                    logger.warning(f"Escalating due to supervisor feedback: {result.get('reason', 'N/A')}")
                    state.record_escalation(current.name, result.get("reason", ""))

                state.current_state = transition.next_state
                logger.info(f"Transitioning to next state: {transition.next_state}")
                self._state_manager.save(ticket_key, state)
                logger.debug(f"State saved for ticket: {ticket_key}")

            except Exception as e:
                logger.exception(f"Error during workflow execution at state {current.name}: {e}")
                raise
