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

    def _repair_implementation(
        self,
        *,
        ticket_key: str,
        evidence: ImplementationEvidence,
    ) -> None:
        """Run one implementation repair using verification failures."""

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

        repo_root = (
            self._project.core_dir.parent.resolve()
        )

        plan_path = (
            self._project.artifacts_dir(ticket_key)
            / "plan.yaml"
        )

        edit_files = planned_changed_files(
            plan_path=plan_path,
            repo_root=repo_root,
        )

        if not edit_files:
            raise RuntimeError(
                "Implementation repair has no "
                "plan-authorized editable files"
            )

        coder_path = self._project.agent_path(
            "coder"
        )

        read_files = [
            coder_path,
            plan_path,
            evidence.test_results_path,
            evidence.lint_results_path,
        ]

        project_instructions = (
            repo_root
            / "AGENTS.md"
        )

        if project_instructions.is_file():
            read_files.append(
                project_instructions
            )

        map_tokens = (
            self._project.map_tokens_for(
                "repository"
            )
        )

        model = (
            self._project.model_for_agent(
                "coder"
            )
        )

        logger.info(
            "Invoking implementation repair: "
            "tests=%s lint=%s editable_files=%d",
            "PASS"
            if evidence.tests_passed
            else "FAIL",
            "PASS"
            if evidence.lint_passed
            else "FAIL",
            len(edit_files),
        )

        self._backend.repair_repository(
            model=model,
            read_files=read_files,
            edit_files=edit_files,
            repo_root=repo_root,
            test_command=test_command,
            lint_command=lint_command,
            map_tokens=map_tokens,
        )

    def _remediate_review(
        self,
        *,
        ticket_key: str,
    ) -> None:
        """Repair blocking implementation findings identified by review."""

        repo_root = (
            self._project.core_dir.parent.resolve()
        )

        artifacts_dir = (
            self._project.artifacts_dir(
                ticket_key
            )
        )

        plan_path = (
            artifacts_dir
            / "plan.yaml"
        )

        requirements_path = (
            artifacts_dir
            / "requirements.md"
        )

        review_path = (
            artifacts_dir
            / "review.md"
        )

        required_read_files = [
            plan_path,
            requirements_path,
            review_path,
        ]

        for path in required_read_files:
            if not path.is_file():
                raise RuntimeError(
                    "Review remediation context "
                    f"file does not exist: {path}"
                )

        edit_files = planned_changed_files(
            plan_path=plan_path,
            repo_root=repo_root,
        )

        if not edit_files:
            raise RuntimeError(
                "Review remediation has no "
                "plan-authorized editable files"
            )

        read_files = list(
            required_read_files
        )

        project_instructions = (
            repo_root
            / "AGENTS.md"
        )

        if project_instructions.is_file():
            read_files.append(
                project_instructions
            )

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

        model = (
            self._project.model_for_agent(
                "coder"
            )
        )

        map_tokens = (
            self._project.map_tokens_for(
                "repository"
            )
        )

        logger.info(
            "Invoking review remediation with %d editable file(s)",
            len(edit_files),
        )

        logger.debug(
            "Review remediation read-only files:\n%s",
            "\n".join(
                f"  - {path}"
                for path in read_files
            ),
        )

        logger.debug(
            "Review remediation editable files:\n%s",
            "\n".join(
                f"  - {path}"
                for path in edit_files
            ),
        )

        self._backend.remediate_review(
            model=model,
            read_files=read_files,
            edit_files=edit_files,
            repo_root=repo_root,
            test_command=test_command,
            lint_command=lint_command,
            map_tokens=map_tokens,
        )

    def _evaluate_implementation(
        self,
        *,
        ticket_key: str,
    ) -> tuple[
        str,
        dict,
        WorkerFeedback | None,
        ImplementationEvidence,
    ]:
        """Verify implementation and attempt one repair when necessary."""

        evidence = (
            self._collect_implementation_evidence(
                ticket_key=ticket_key,
            )
        )

        if not evidence.verification_passed:
            logger.warning(
                "Implementation verification failed: "
                "tests=%s lint=%s. Attempting repair.",
                "PASS"
                if evidence.tests_passed
                else "FAIL",
                "PASS"
                if evidence.lint_passed
                else "FAIL",
            )

            self._repair_implementation(
                ticket_key=ticket_key,
                evidence=evidence,
            )

            logger.info(
                "Implementation repair completed. "
                "Recollecting evidence."
            )

            evidence = (
                self._collect_implementation_evidence(
                    ticket_key=ticket_key,
                )
            )

        if evidence.verification_passed:
            result = {
                "outcome": "success",
                "reason": (
                    "Deterministic implementation verification "
                    "passed: tests and lint succeeded."
                ),
                "violations": [],
            }

            logger.info(
                "Implementation verification passed; "
                "skipping implementation supervisor"
            )

            return (
                "success",
                result,
                None,
                evidence,
            )

        reason = (
            "Implementation verification failed after repair: "
            f"tests={'PASS' if evidence.tests_passed else 'FAIL'}, "
            f"lint={'PASS' if evidence.lint_passed else 'FAIL'}."
        )

        feedback = WorkerFeedback(
            source="verification",
            reason=reason,
            details=(),
        )

        result = {
            "outcome": "failure",
            "reason": reason,
            "violations": [
                name
                for name, passed in (
                    (
                        "tests_pass",
                        evidence.tests_passed,
                    ),
                    (
                        "lint_pass",
                        evidence.lint_passed,
                    ),
                )
                if not passed
            ],
        }

        return (
            "failure",
            result,
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
                "failure",
                {
                    "outcome": "failure",
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
            "Reviewer requested implementation changes"
        )

        self._remediate_review(
            ticket_key=ticket_key,
        )

        logger.info(
            "Review remediation completed. "
            "Collecting deterministic verification evidence."
        )

        evidence = (
            self._collect_implementation_evidence(
                ticket_key=ticket_key,
            )
        )

        if evidence.verification_passed:
            reason = (
                "Review remediation completed and deterministic "
                "verification passed. The corrected implementation "
                "requires another review."
            )

            return (
                "failure",
                {
                    "outcome": "failure",
                    "reason": reason,
                    "violations": [],
                },
                None,
                evidence,
            )

        reason = (
            "Review remediation completed, but the corrected "
            "implementation does not pass deterministic verification: "
            f"tests={'PASS' if evidence.tests_passed else 'FAIL'}, "
            f"lint={'PASS' if evidence.lint_passed else 'FAIL'}."
        )

        return (
            "escalate",
            {
                "outcome": "escalate",
                "reason": reason,
                "violations": [
                    name
                    for name, passed in (
                        (
                            "tests_pass",
                            evidence.tests_passed,
                        ),
                        (
                            "lint_pass",
                            evidence.lint_passed,
                        ),
                    )
                    if not passed
                ],
            },
            None,
            evidence,
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

            attempt = (
                state.retry_counts.get(
                    current.name,
                    0,
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

            if attempt == 1:
                clear_feedback(
                    context_dir=context_dir,
                    state_name=current.name,
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

                    if current.name == "implement":
                        (
                            outcome,
                            result,
                            feedback,
                            evidence,
                        ) = self._evaluate_implementation(
                            ticket_key=ticket_key,
                        )

                    elif current.name == "review":
                        (
                            outcome,
                            result,
                            feedback,
                            evidence,
                        ) = self._evaluate_review(
                            ticket_key=ticket_key,
                        )

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
                # Persist or clear retry feedback
                # ------------------------------------------------------

                if outcome == "success":
                    clear_feedback(
                        context_dir=context_dir,
                        state_name=current.name,
                    )

                elif (
                    outcome == "failure"
                    and feedback is not None
                ):
                    feedback_file = write_feedback(
                        context_dir=context_dir,
                        state_name=current.name,
                        attempt=attempt,
                        feedback=feedback,
                    )

                    logger.info(
                        "Saved retry feedback for state '%s': %s",
                        current.name,
                        feedback_file,
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