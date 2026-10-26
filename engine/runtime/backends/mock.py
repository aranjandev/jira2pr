"""MockBackend — deterministic, offline stand-in for tests and dry-runs.

Used by the workflow executor test suite to run a full workflow
(feature: jira-ingest -> ... -> done/human-review) without any real LLM,
Aider, or network calls.

The mock is file-oriented like the real backends: it identifies what to
produce from the output file name (``requirements.md``, ``plan.yaml``,
``review.md``, ``pr-description.md``, ``supervisor-<state>-decision.json``).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from runtime.backends.base import LLMBackend

# output file name -> content (or None to use the default)
ArtifactResponder = Callable[[str], str | None]

# workflow state name -> decision file content (or None to use the default)
DecisionResponder = Callable[[str], str | None]

DEFAULT_PLAN = """\
version: 1
summary: Add an example module.
tasks:
  - id: T1
    file_path: src/example.py
    edit_mode: create
    instructions: Create the example module.
    dependencies: []
tests:
  - id: TEST1
    file_path: tests/test_example.py
    edit_mode: create
    instructions: Add tests for the example module.
    verifies:
      - Example module behaves as specified.
    dependencies: [T1]
constraints: []
out_of_scope: []
"""

DEFAULT_REVIEW = """\
# Review

No blocking findings.

```review-verdict
verdict: approve
reason: Implementation satisfies the requirements.
```
"""

DEFAULT_PR_DESCRIPTION = """\
# Pull Request Description

Adds the example module.

```pr-actions
commit_message: "feat: add example module"
pr_title: "Add example module"
```
"""

DEFAULT_ARTIFACTS: dict[str, str] = {
    "plan.yaml": DEFAULT_PLAN,
    "review.md": DEFAULT_REVIEW,
    "pr-description.md": DEFAULT_PR_DESCRIPTION,
}

DEFAULT_DECISION = {
    "outcome": "success",
    "reason": "ok",
    "feedback": "",
    "violations": [],
}


class MockBackend(LLMBackend):
    """Writes scripted or generic canned output and records every call made.

    *artifact_responder* receives the output file name and may return custom
    content for it. *decision_responder* receives the workflow state name of
    a supervisor evaluation and may return the raw decision file content
    (e.g. a stateful counter that fails the first N attempts at a given
    state, to exercise retry/escalation paths). When a responder is absent or
    returns None, a successful default is used.
    """

    def __init__(
        self,
        artifact_responder: ArtifactResponder | None = None,
        decision_responder: DecisionResponder | None = None,
    ) -> None:
        self._artifact_responder = artifact_responder
        self._decision_responder = decision_responder
        self.calls: list[dict] = []

    def produce_artifact(
        self,
        *,
        model: str,
        read_files: list[Path],
        output_file: Path,
        repo_root: Path,
        map_tokens: int | None = None,
    ) -> None:
        self.calls.append(
            {
                "op": "produce_artifact",
                "model": model,
                "output": output_file.name,
            }
        )

        content = None

        if self._artifact_responder is not None:
            content = self._artifact_responder(output_file.name)

        if content is None:
            content = DEFAULT_ARTIFACTS.get(
                output_file.name,
                "# Content\n\nGenerated.\n",
            )

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(content, encoding="utf-8")

    def produce_structured(
        self,
        *,
        model: str,
        read_files: list[Path],
        output_file: Path,
        repo_root: Path,
        map_tokens: int | None = None,
    ) -> None:
        # supervisor-<state>-decision.json
        state_name = output_file.name.removeprefix(
            "supervisor-"
        ).removesuffix("-decision.json")

        self.calls.append(
            {
                "op": "produce_structured",
                "model": model,
                "state": state_name,
            }
        )

        content = None

        if self._decision_responder is not None:
            content = self._decision_responder(state_name)

        if content is None:
            content = json.dumps(DEFAULT_DECISION)

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(content, encoding="utf-8")

    def edit_repository(
        self,
        *,
        model: str,
        read_files: list[Path],
        edit_files: list[Path],
        repo_root: Path,
        map_tokens: int | None = None,
    ) -> None:
        self.calls.append(
            {
                "op": "edit_repository",
                "model": model,
                "files": [str(path) for path in edit_files],
            }
        )

        for path in edit_files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# edited by MockBackend\n", encoding="utf-8")

    def repair_repository(
        self,
        *,
        model: str,
        read_files: list[Path],
        edit_files: list[Path],
        repo_root: Path,
        test_command: str,
        lint_command: str,
        map_tokens: int | None = None,
    ) -> None:
        self.calls.append(
            {
                "op": "repair_repository",
                "model": model,
                "files": [str(path) for path in edit_files],
            }
        )

    def remediate_review(
        self,
        *,
        model: str,
        read_files: list[Path],
        edit_files: list[Path],
        repo_root: Path,
        test_command: str,
        lint_command: str,
        map_tokens: int | None = None,
    ) -> None:
        self.calls.append(
            {
                "op": "remediate_review",
                "model": model,
                "files": [str(path) for path in edit_files],
            }
        )
