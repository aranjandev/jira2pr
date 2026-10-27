"""Drive a workflow from its current state to a terminal state.

Objective implementation verification is performed deterministically using
test and lint commands.

The reviewer owns semantic implementation evaluation through review.md and
its trailing review-verdict block.

Supervisor evaluation remains available for workflow states other than
implement and review.
"""

from __future__ import annotations

from runtime.backends.base import LLMBackend
from runtime.logging_config import get_logger
from runtime.workflow import transitions
from runtime.workflow.action_executor import (
    ActionExecutionError,
    execute_actions,
)
from runtime.workflow.evidence import (
    ImplementationEvidence,
    collect_implementation_evidence,
    planned_changed_files,
)
from runtime.workflow.feedback import (
    WorkerFeedback,
    WorkerOutputError,
    clear_feedback,
    write_feedback,
)
from runtime.workflow.loader import RuntimeProject
from runtime.workflow.review import (
    ReviewDecisionError,
    load_review_decision,
)
from runtime.workflow.state_manager import (
    StateManager,
    WorkflowState,
)
from runtime.workflow.supervisor_invoker import (
    invoke_supervisor,
)
from runtime.workflow.worker_invoker import (
    invoke_worker,
)

logger = get_logger("workflow.executor")


class WorkflowExecutor:
    def __init__(
        self,
        project: RuntimeProject,
        backend: LLMBackend,
    ) -> None:
        self._project = project
        self._backend = backend
        self._state_manager = StateManager(
            project.core_dir
        )

        logger.debug(
            "WorkflowExecutor initialized with backend: %s",
            backend.__class__.__name__,
        )

    def start(
        self,
        workflow_name: str,
        ticket_key: str,
    ) -> WorkflowState:
        """Create fresh state for a ticket and run the workflow."""

        logger.info(
            "Starting new workflow: %s for ticket: %s",
            workflow_name,
            ticket_key,
        )

        workflow = self._project.workflow(
            workflow_name
        )

        self._state_manager.create(
            ticket_key,
            workflow_name,
            workflow.initial_state,
        )

        logger.debug(
            "Created initial state for %s at state: %s",
            ticket_key,
            workflow.initial_state,
        )

        return self.run(
            ticket_key
        )

    def resume(
        self,
        ticket_key: str,
    ) -> WorkflowState:
        """Continue a previously started workflow from saved state."""

        logger.info(
            "Resuming workflow for ticket: %s",
            ticket_key,
        )

        return self.run(
            ticket_key
        )

    def _collect_implementation_evidence(
        self,
        *,
        ticket_key: str,
    ) -> ImplementationEvidence:
        """Collect deterministic evidence for the implementation."""

        verification = (
            self._project.backend_config.get(
                "verification",
                {},
            )
        )

        test_command = verification.get(
            "test_command",
            "",
        )

        lint_command = verification.get(
            "lint_command",
            "",
        )

        lint_fix_command = verification.get(
            "lint_fix_command",
            "",
        )

        repo_root = (
            self._project.core_dir.parent.resolve()
        )

        plan_path = (
            self._project.artifacts_dir(ticket_key)
            / "plan.yaml"
        )

        changed_files = planned_changed_files(
            plan_path=plan_path,
            repo_root=repo_root,
        )

        logger.debug(
            "Collecting implementation evidence for planned files:\n%s",
            "\n".join(
                f"  - {path}"
                for path in changed_files
            ),
        )

        evidence = collect_implementation_evidence(
            project=self._project,
            ticket_key=ticket_key,
            changed_files=changed_files,
            test_command=test_command,
            lint_command=lint_command,
            lint_fix_command=lint_fix_command,
        )

        logger.info(
            "Implementation verification: tests=%s lint=%s",
            "PASS"
            if evidence.tests_passed
            else "FAIL",
            "PASS"
            if evidence.lint_passed
            else "FAIL",
        )

        return evidence

    def _evaluate_verification(
        self,
        *,
        ticket_key: str,
    ) -> tuple[
        str,
        dict,
        WorkerFeedback | None,
        ImplementationEvidence,
    ]:
        """Run deterministic test and lint checks. Repair is the coder's job."""

        evidence = (
            self._collect_implementation_evidence(
                ticket_key=ticket_key,
            )
        )

        if evidence.verification_passed:
            logger.info(
                "Deterministic verification passed: tests and lint succeeded"
            )

            return (
                "success",
                {
                    "outcome": "success",
                    "reason": (
                        "Deterministic verification passed: "
                        "tests and lint succeeded."
                    ),
                    "violations": [],
                },
                None,
                evidence,
            )

        reason = (
            "Deterministic verification failed: "
            f"tests={'PASS' if evidence.tests_passed else 'FAIL'}, "
            f"lint={'PASS' if evidence.lint_passed else 'FAIL'}."
        )

        feedback = WorkerFeedback(
            source="verification",
            reason=reason,
            details=(
                f"Test results: {evidence.test_results_path}",
                f"Lint results: {evidence.lint_results_path}",
            ),
        )

        return (
            "failure",
            {
                "outcome": "failure",
                "reason": reason,
                "violations": [
                    name
                    for name, passed in (
                        ("tests_pass", evidence.tests_passed),
                        ("lint_pass", evidence.lint_passed),
                    )
                    if not passed
                ],
            },
            feedback,
            evidence,
        )


    def _evaluate_review(
        self,
        *,
        ticket_key: str,
    ) -> tuple[
        str,
        dict,
        WorkerFeedback | None,
        ImplementationEvidence | None,
    ]:
        """Use the reviewer's own verdict to determine the review outcome."""

        review_path = (
            self._project.artifacts_dir(ticket_key)
            / "review.md"
        )

        try:
            decision = load_review_decision(
                review_path
            )
        except ReviewDecisionError as exc:
            reason = str(exc)

            feedback = WorkerFeedback(
                source="review-validation",
                reason=reason,
                details=(),
            )

            return (
                "invalid_output",
                {
                    "outcome": "invalid_output",
                    "reason": reason,
                    "violations": [],
                },
                feedback,
                None,
            )

        logger.info(
            "Reviewer verdict: %s",
            decision.verdict,
        )

        logger.info(
            "Reviewer reason: %s",
            decision.reason,
        )

        if decision.verdict == "approve":
            return (
                "success",
                {
                    "outcome": "success",
                    "reason": decision.reason,
                    "violations": [],
                },
                None,
                None,
            )

        if decision.verdict == "escalate":
            return (
                "escalate",
                {
                    "outcome": "escalate",
                    "reason": decision.reason,
                    "violations": [],
                },
                None,
                None,
            )

        if decision.verdict != "changes_requested":
            raise RuntimeError(
                "Unsupported review verdict: "
                f"{decision.verdict}"
            )

        logger.info(
            "Reviewer requested implementation changes; "
            "routing review findings to implement"
        )

        return (
            "failure",
            {
                "outcome": "failure",
                "reason": decision.reason,
                "violations": [],
            },
            WorkerFeedback(
                source="review",
                reason=decision.reason,
                details=("Blocking findings are in the review artifact: review.md",),
            ),
            None,
        )

    def run(
        self,
        ticket_key: str,
    ) -> WorkflowState:
        """Run or resume a workflow until it reaches a terminal state."""

        logger.info(
            "Running workflow for ticket: %s",
            ticket_key,
        )

        state = self._state_manager.load(
            ticket_key
        )

        logger.info(
            "Loaded state for %s: "
            "workflow=%s, current_state=%s",
            ticket_key,
            state.workflow,
            state.current_state,
        )

        workflow = self._project.workflow(
            state.workflow
        )

        policy = (
            self._project.execution_policy
        )

        iteration = 0

        while True:
            iteration += 1

            current = workflow.states[
                state.current_state
            ]

            logger.debug(
                "[Iteration %d] Current state: %s, Terminal: %s",
                iteration,
                current.name,
                current.terminal,
            )

            # ----------------------------------------------------------
            # Terminal state
            # ----------------------------------------------------------

            if current.terminal:
                state.status = (
                    "completed"
                    if current.outcome == "success"
                    else "escalated"
                )

                self._state_manager.save(
                    ticket_key,
                    state,
                )

                logger.info(
                    "Workflow reached terminal state: %s "
                    "(outcome=%s)",
                    current.name,
                    current.outcome,
                )

                logger.info(
                    "Final status: %s",
                    state.status,
                )

                return state

            # ----------------------------------------------------------
            # Global iteration limit
            # ----------------------------------------------------------

            max_total_iterations = (
                workflow.max_total_iterations
                if workflow.max_total_iterations is not None
                else policy.max_total_iterations
            )

            if (
                state.total_iterations
                >= max_total_iterations
            ):
                logger.warning(
                    "Global iteration cap (%d) exceeded "
                    "at state %s. Escalating due to "
                    "possible transition cycle.",
                    max_total_iterations,
                    current.name,
                )

                state.record_escalation(
                    current.name,
                    (
                        "global iteration cap "
                        f"({max_total_iterations}) exceeded; "
                        "possible transition cycle"
                    ),
                )

                state.current_state = (
                    policy.terminal_escalated_state
                )

                self._state_manager.save(
                    ticket_key,
                    state,
                )

                continue

            # ----------------------------------------------------------
            # Begin state attempt
            # ----------------------------------------------------------

            state.total_iterations += 1

            # Visit number of this state in the run (budgets may be shared, so
            # retry_counts is not a per-state attempt counter).
            attempt = (
                sum(
                    1
                    for entry in state.history
                    if entry.get("state") == current.name
                )
                + 1
            )

            logger.info(
                "[Iteration %d] Processing state: %s "
                "(attempt %d, total iterations: %d)",
                iteration,
                current.name,
                attempt,
                state.total_iterations,
            )

            context_dir = (
                self._project.context_dir(
                    ticket_key
                )
            )

            try:
                produced: dict[str, str] = {}
                action_metadata: dict[str, str] = {}
                feedback: WorkerFeedback | None = None
                evidence: ImplementationEvidence | None = None

                # ------------------------------------------------------
                # Worker execution
                # ------------------------------------------------------

                try:
                    if current.kind == "worker":
                        logger.debug(
                            "Invoking worker for state: %s",
                            current.name,
                        )

                        (
                            produced,
                            action_metadata,
                        ) = invoke_worker(
                            project=self._project,
                            workflow=workflow,
                            state=current,
                            ticket_key=ticket_key,
                            backend=self._backend,
                        )

                        logger.debug(
                            "Worker produced artifacts: %s",
                            list(
                                produced.keys()
                            ),
                        )

                except WorkerOutputError as exc:
                    logger.warning(
                        "Worker output failed validation "
                        "for state '%s': %s",
                        current.name,
                        exc,
                    )

                    outcome = "failure"
                    feedback = exc.feedback

                    result = {
                        "outcome": outcome,
                        "reason": feedback.reason,
                        "feedback": (
                            "\n".join(
                                feedback.details
                            )
                            if feedback.details
                            else ""
                        ),
                        "violations": [],
                    }

                else:
                    # --------------------------------------------------
                    # State evaluation
                    # --------------------------------------------------

                    if current.kind == "verification":
                        (
                            outcome,
                            result,
                            feedback,
                            evidence,
                        ) = self._evaluate_verification(
                            ticket_key=ticket_key,
                        )

                    elif current.worker == "reviewer":
                        (
                            outcome,
                            result,
                            feedback,
                            evidence,
                        ) = self._evaluate_review(
                            ticket_key=ticket_key,
                        )

                    elif not current.supervised:
                        outcome = "success"
                        result = {
                            "outcome": "success",
                            "reason": "Worker completed; supervisor evaluation is disabled for this state.",
                            "violations": [],
                        }

                    else:
                        logger.debug(
                            "Invoking supervisor for state: %s",
                            current.name,
                        )

                        evidence_files = (
                            evidence.files()
                            if evidence is not None
                            else []
                        )

                        result = invoke_supervisor(
                            self._project,
                            workflow,
                            current,
                            ticket_key,
                            produced,
                            self._backend,
                            evidence_files=evidence_files,
                        )

                        outcome = result[
                            "outcome"
                        ]

                        logger.info(
                            "Supervisor outcome: %s, Reason: %s",
                            outcome,
                            result.get(
                                "reason",
                                "N/A",
                            ),
                        )

                        if outcome != "success":
                            feedback = (
                                _feedback_from_supervisor(
                                    result
                                )
                            )

                # ------------------------------------------------------
                # Clear the state's own feedback once it succeeds
                # ------------------------------------------------------

                if outcome == "success":
                    clear_feedback(
                        context_dir=context_dir,
                        state_name=current.name,
                    )

                # ------------------------------------------------------
                # Register produced artifacts
                # ------------------------------------------------------

                for name in produced:
                    if name not in state.artifacts:
                        state.artifacts.append(
                            name
                        )

                # ------------------------------------------------------
                # Resolve transition
                # ------------------------------------------------------

                transition = transitions.next_state(
                    workflow,
                    current.name,
                    outcome,
                    state.retry_counts,
                    policy,
                )

                state.retry_counts = (
                    transition.retry_counts
                )

                # ------------------------------------------------------
                # Hand failure feedback to the state that acts on it.
                #
                # Feedback is addressed to the transition target, so a
                # failure routed to implement (from run-tests or review)
                # is read by the coder on its next attempt. When the run
                # escalates to a terminal state, the feedback stays with the
                # failing state so the file always describes the latest failure.
                # ------------------------------------------------------

                if outcome in ("failure", "invalid_output") and feedback is not None:
                    feedback_state = (
                        current.name
                        if workflow.states[transition.next_state].terminal
                        else transition.next_state
                    )
                    feedback_file = write_feedback(
                        context_dir=context_dir,
                        state_name=feedback_state,
                        attempt=attempt,
                        feedback=feedback,
                    )

                    logger.info(
                        "Saved retry feedback for state '%s': %s",
                        feedback_state,
                        feedback_file,
                    )

                # ------------------------------------------------------
                # Runtime action capabilities
                #
                # Action states are not recorded as successful until their
                # actions have completed successfully.
                # ------------------------------------------------------

                worker_binding = (
                    self._project.workers.get(
                        current.worker
                    )
                )

                if (
                    worker_binding
                    and worker_binding.actions
                    and outcome == "success"
                ):
                    logger.info(
                        "Executing actions for state: %s",
                        current.name,
                    )

                    logger.debug(
                        "Action metadata for state '%s': %r",
                        current.name,
                        action_metadata,
                    )

                    try:
                        action_result = execute_actions(
                            self._project,
                            current,
                            ticket_key,
                            action_metadata,
                            self._project.core_dir.parent,
                            state.metadata.get(
                                "pr_number"
                            ),
                        )

                        state.metadata.update(
                            action_result
                        )

                        logger.info(
                            "Actions completed: %s",
                            action_result,
                        )

                    except ActionExecutionError:
                        logger.exception(
                            "Action execution failed"
                        )
                        raise

                # ------------------------------------------------------
                # Record history
                # ------------------------------------------------------

                state.record_history(
                    current.name,
                    attempt,
                    outcome,
                    notes=result.get(
                        "reason",
                        "",
                    ),
                )

                # ------------------------------------------------------
                # Escalation tracking
                # ------------------------------------------------------

                if (
                    transition
                    .escalated_due_to_retry_exhaustion
                ):
                    logger.warning(
                        "Escalating due to retry attempts "
                        "exhausted for state: %s",
                        current.name,
                    )

                    state.record_escalation(
                        current.name,
                        "retry attempts exhausted",
                    )

                elif outcome == "escalate":
                    reason = result.get(
                        "reason",
                        "",
                    )

                    logger.warning(
                        "Escalating state '%s': %s",
                        current.name,
                        reason,
                    )

                    state.record_escalation(
                        current.name,
                        reason,
                    )

                # ------------------------------------------------------
                # Advance workflow
                # ------------------------------------------------------

                state.current_state = (
                    transition.next_state
                )

                logger.info(
                    "Transitioning to next state: %s",
                    transition.next_state,
                )

                self._state_manager.save(
                    ticket_key,
                    state,
                )

                logger.debug(
                    "State saved for ticket: %s",
                    ticket_key,
                )

            except Exception:
                logger.exception(
                    "Error during workflow execution "
                    "at state %s",
                    current.name,
                )
                raise


def _feedback_from_supervisor(
    result: dict,
) -> WorkerFeedback:
    """Convert a supervisor rejection into retry feedback."""

    details: list[str] = []

    supervisor_feedback = result.get(
        "feedback",
        "",
    )

    if supervisor_feedback:
        details.append(
            str(
                supervisor_feedback
            )
        )

    violations = result.get(
        "violations",
        [],
    )

    if isinstance(
        violations,
        list,
    ):
        details.extend(
            str(violation)
            for violation in violations
            if violation
        )

    return WorkerFeedback(
        source="supervisor",
        reason=str(
            result.get(
                "reason",
                "Supervisor rejected worker output",
            )
        ),
        details=tuple(
            details
        ),
    )