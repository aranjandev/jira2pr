"""Executes action capabilities (git.commit, git.push, pr.create, pr.update).

Actions are deterministic integrations that modify the working repository:
they create commits, push branches, and manage pull requests.

Actions are invoked after the worker's response is validated. The worker
must include a trailing metadata block with action parameters:

```pr-actions
commit_message: "feat: add new feature"
pr_title: "Add new feature"  (omitted when updating an existing PR)
```
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from assembler.model import StateSpec

from runtime.capabilities import CapabilityError, resolve
from runtime.logging_config import get_logger
from runtime.workflow.evidence import planned_changed_files
from runtime.workflow.loader import RuntimeProject

logger = get_logger("workflow.action_executor")

# Regex to extract pr-actions metadata block from response
PR_ACTIONS_BLOCK_RE = re.compile(
    r"```pr-actions\s*\n(.*?)\n```",
    re.DOTALL,
)


class ActionExecutionError(Exception):
    """Raised when action execution fails."""


def parse_pr_actions(response: str) -> dict[str, str]:
    """Extract pr-actions metadata block from worker response.

    Returns a dict with keys like 'commit_message', 'pr_title', or raises
    ActionExecutionError if the block is malformed/missing.

    Example block:
    ```
    ```pr-actions
    commit_message: "feat: add feature"
    pr_title: "Add feature"
    ```
    ```
    """
    match = PR_ACTIONS_BLOCK_RE.search(response)
    if not match:
        raise ActionExecutionError("pr-actions block not found in worker response")

    block = match.group(1).strip()
    result = {}

    for line in block.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ActionExecutionError(f"Invalid pr-actions line: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"\'')  # Remove surrounding quotes
        result[key] = value

    if "commit_message" not in result:
        raise ActionExecutionError("pr-actions block missing 'commit_message'")

    return result


def strip_pr_actions_block(response: str) -> str:
    """Remove pr-actions block from worker response.

    Returns the response with the pr-actions block removed (used to create
    clean artifact files).
    """
    return PR_ACTIONS_BLOCK_RE.sub("", response).strip()

def execute_actions(
    project: RuntimeProject,
    state: StateSpec,
    ticket_key: str,
    action_metadata: dict[str, str],
    repo_root: Path,
    existing_pr_number: str | None,
) -> dict[str, str]:
    """Execute action capabilities for the current state.

    Steps:
    1. Commit only plan-authorized files.
    2. Push the current branch.
    3. Create a new PR or update the existing PR.
    4. Return PR metadata.

    Raises ActionExecutionError on any failure.
    """

    logger.info(
        "Executing actions for state: %s",
        state.name,
    )

    repo_root = repo_root.resolve()

    # --------------------------------------------------------------
    # Step 1: Git commit
    # --------------------------------------------------------------

    logger.info(
        "Step 1: Creating git commit"
    )

    commit_msg = action_metadata.get(
        "commit_message"
    )

    if not commit_msg:
        raise ActionExecutionError(
            "action_metadata missing 'commit_message'"
        )

    commit_cap = project.capabilities.get(
        "git.commit"
    )

    if not commit_cap:
        raise ActionExecutionError(
            "Capability 'git.commit' not found"
        )

    commit_manifest = _write_commit_manifest(
        project=project,
        ticket_key=ticket_key,
        repo_root=repo_root,
    )

    try:
        commit_argv = resolve(
            commit_cap,
            str(repo_root),
            {
                "message": commit_msg,
                "files_from": str(commit_manifest),
            },
        )

        logger.debug(
            "Commit argv: %s",
            commit_argv,
        )

        result = subprocess.run(
            commit_argv,
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            logger.error(
                "git.commit failed: %s",
                result.stderr,
            )

            raise ActionExecutionError(
                f"git.commit failed: {result.stderr.strip()}"
            )

        logger.info(
            "Commit successful: %s",
            result.stdout.strip(),
        )

    except CapabilityError as exc:
        logger.error(
            "Failed to resolve git.commit: %s",
            exc,
        )

        raise ActionExecutionError(
            f"Failed to resolve git.commit: {exc}"
        ) from exc

    # --------------------------------------------------------------
    # Step 2: Git push
    # --------------------------------------------------------------

    logger.info(
        "Step 2: Pushing commits"
    )

    push_cap = project.capabilities.get(
        "git.push"
    )

    if not push_cap:
        raise ActionExecutionError(
            "Capability 'git.push' not found"
        )

    try:
        push_argv = resolve(
            push_cap,
            str(repo_root),
            {},
        )

        logger.debug(
            "Push argv: %s",
            push_argv,
        )

        result = subprocess.run(
            push_argv,
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            logger.error(
                "git.push failed: %s",
                result.stderr,
            )

            raise ActionExecutionError(
                f"git.push failed: {result.stderr.strip()}"
            )

        logger.info(
            "Push successful: %s",
            result.stdout.strip(),
        )

    except CapabilityError as exc:
        logger.error(
            "Failed to resolve git.push: %s",
            exc,
        )

        raise ActionExecutionError(
            f"Failed to resolve git.push: {exc}"
        ) from exc

    # --------------------------------------------------------------
    # Step 3: PR create/update
    # --------------------------------------------------------------

    result_metadata: dict[str, str] = {}

    body_file = (
        project.artifacts_dir(ticket_key)
        / "pr-description.md"
    )

    if not body_file.is_file():
        raise ActionExecutionError(
            f"pr-description.md not found at {body_file}"
        )

    if not existing_pr_number:
        logger.info(
            "Step 3: Creating new pull request"
        )

        pr_title = action_metadata.get(
            "pr_title"
        )

        if not pr_title:
            raise ActionExecutionError(
                "action_metadata missing 'pr_title' for new PR"
            )

        create_cap = project.capabilities.get(
            "pr.create"
        )

        if not create_cap:
            raise ActionExecutionError(
                "Capability 'pr.create' not found"
            )

        try:
            create_argv = resolve(
                create_cap,
                str(repo_root),
                {
                    "title": pr_title,
                    "body_file": str(body_file),
                },
            )

            logger.debug(
                "PR create argv: %s",
                create_argv,
            )

            result = subprocess.run(
                create_argv,
                cwd=repo_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.error(
                    "pr.create failed: %s",
                    result.stderr,
                )

                raise ActionExecutionError(
                    f"pr.create failed: {result.stderr.strip()}"
                )

            pr_url = None
            pr_number = None

            for line in result.stdout.splitlines():
                if line.startswith("PR_URL="):
                    pr_url = line.split(
                        "=",
                        1,
                    )[1]

                elif line.startswith("PR_NUMBER="):
                    pr_number = line.split(
                        "=",
                        1,
                    )[1]

            if not pr_number:
                raise ActionExecutionError(
                    "pr.create did not output PR_NUMBER"
                )

            result_metadata["pr_number"] = (
                pr_number
            )

            if pr_url:
                result_metadata["pr_url"] = (
                    pr_url
                )

            logger.info(
                "PR created: %s (#%s)",
                pr_url or "N/A",
                pr_number,
            )

        except CapabilityError as exc:
            logger.error(
                "Failed to resolve pr.create: %s",
                exc,
            )

            raise ActionExecutionError(
                f"Failed to resolve pr.create: {exc}"
            ) from exc

    else:
        logger.info(
            "Step 3: Updating existing pull request #%s",
            existing_pr_number,
        )

        update_cap = project.capabilities.get(
            "pr.update"
        )

        if not update_cap:
            raise ActionExecutionError(
                "Capability 'pr.update' not found"
            )

        try:
            update_argv = resolve(
                update_cap,
                str(repo_root),
                {
                    "pr_number": existing_pr_number,
                    "body_file": str(body_file),
                },
            )

            logger.debug(
                "PR update argv: %s",
                update_argv,
            )

            result = subprocess.run(
                update_argv,
                cwd=repo_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logger.error(
                    "pr.update failed: %s",
                    result.stderr,
                )

                raise ActionExecutionError(
                    f"pr.update failed: {result.stderr.strip()}"
                )

            pr_url = None

            for line in result.stdout.splitlines():
                if line.startswith("PR_URL="):
                    pr_url = line.split(
                        "=",
                        1,
                    )[1]

            result_metadata["pr_number"] = (
                existing_pr_number
            )

            if pr_url:
                result_metadata["pr_url"] = (
                    pr_url
                )

            logger.info(
                "PR updated: %s (#%s)",
                pr_url or "N/A",
                existing_pr_number,
            )

        except CapabilityError as exc:
            logger.error(
                "Failed to resolve pr.update: %s",
                exc,
            )

            raise ActionExecutionError(
                f"Failed to resolve pr.update: {exc}"
            ) from exc

    return result_metadata


def _write_commit_manifest(
    project: RuntimeProject,
    ticket_key: str,
    repo_root: Path,
) -> Path:
    """Write the plan-authorized commit file list."""

    repo_root = repo_root.resolve()

    plan_path = (
        project.artifacts_dir(ticket_key)
        / "plan.yaml"
    )

    commit_files = planned_changed_files(
        plan_path=plan_path,
        repo_root=repo_root,
    )

    if not commit_files:
        raise ActionExecutionError(
            "No plan-authorized files available to commit"
        )

    relative_paths: list[str] = []

    for path in commit_files:
        resolved = path.resolve()

        try:
            relative = resolved.relative_to(repo_root)
        except ValueError as exc:
            raise ActionExecutionError(
                f"Commit file is outside repository root: {resolved}"
            ) from exc

        relative_paths.append(
            relative.as_posix()
        )

    manifest_path = (
        project.context_dir(ticket_key)
        / "commit-files.txt"
    )

    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path.write_text(
        "\n".join(relative_paths) + "\n",
        encoding="utf-8",
    )

    logger.info(
        "Commit manifest contains %d plan-authorized file(s)",
        len(relative_paths),
    )

    logger.debug(
        "Commit manifest written to %s:\n%s",
        manifest_path,
        "\n".join(
            f"  - {path}"
            for path in relative_paths
        ),
    )

    return manifest_path