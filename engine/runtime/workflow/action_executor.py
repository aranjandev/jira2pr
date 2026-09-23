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
from runtime.capabilities import resolve, CapabilityError
from runtime.logging_config import get_logger
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
    1. Run git.commit with commit_metadata message
    2. Run git.push
    3. If not updating existing PR: run pr.create (extract PR_NUMBER/PR_URL from stdout)
    4. Else: run pr.update with existing_pr_number
    5. Return dict with pr_number and pr_url

    Raises ActionExecutionError on any failure.
    """
    logger.info(f"Executing actions for state: {state.name}")

    # 1. Git commit
    logger.info("Step 1: Creating git commit")
    commit_msg = action_metadata.get("commit_message")
    if not commit_msg:
        raise ActionExecutionError("action_metadata missing 'commit_message'")

    commit_cap = project.capabilities.get("git.commit")
    if not commit_cap:
        raise ActionExecutionError("Capability 'git.commit' not found")

    try:
        commit_argv = resolve(commit_cap, str(repo_root), {"message": commit_msg})
        logger.debug(f"Commit argv: {commit_argv}")
        result = subprocess.run(
            commit_argv,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error(f"git.commit failed: {result.stderr}")
            raise ActionExecutionError(f"git.commit failed: {result.stderr.strip()}")
        logger.info(f"Commit successful: {result.stdout.strip()}")
    except CapabilityError as e:
        logger.error(f"Failed to resolve git.commit: {e}")
        raise ActionExecutionError(f"Failed to resolve git.commit: {e}") from e

    # 2. Git push
    logger.info("Step 2: Pushing commits")
    push_cap = project.capabilities.get("git.push")
    if not push_cap:
        raise ActionExecutionError("Capability 'git.push' not found")

    try:
        push_argv = resolve(push_cap, str(repo_root), {})
        logger.debug(f"Push argv: {push_argv}")
        result = subprocess.run(
            push_argv,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error(f"git.push failed: {result.stderr}")
            raise ActionExecutionError(f"git.push failed: {result.stderr.strip()}")
        logger.info(f"Push successful: {result.stdout.strip()}")
    except CapabilityError as e:
        logger.error(f"Failed to resolve git.push: {e}")
        raise ActionExecutionError(f"Failed to resolve git.push: {e}") from e

    # 3 & 4. PR create or update
    result_metadata = {}

    if not existing_pr_number:
        # Create new PR
        logger.info("Step 3: Creating new pull request")
        pr_title = action_metadata.get("pr_title")
        if not pr_title:
            raise ActionExecutionError("action_metadata missing 'pr_title' for new PR")

        # Find pr-description.md artifact
        body_file = project.artifacts_dir(ticket_key) / "pr-description.md"
        if not body_file.exists():
            raise ActionExecutionError(f"pr-description.md not found at {body_file}")

        create_cap = project.capabilities.get("pr.create")
        if not create_cap:
            raise ActionExecutionError("Capability 'pr.create' not found")

        try:
            create_argv = resolve(
                create_cap,
                str(repo_root),
                {"title": pr_title, "body_file": str(body_file)},
            )
            logger.debug(f"PR create argv: {create_argv}")
            result = subprocess.run(
                create_argv,
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.error(f"pr.create failed: {result.stderr}")
                raise ActionExecutionError(f"pr.create failed: {result.stderr.strip()}")

            # Parse PR_URL and PR_NUMBER from stdout
            pr_url = None
            pr_number = None
            for line in result.stdout.split("\n"):
                if line.startswith("PR_URL="):
                    pr_url = line.split("=", 1)[1]
                elif line.startswith("PR_NUMBER="):
                    pr_number = line.split("=", 1)[1]

            if not pr_number:
                raise ActionExecutionError("pr.create did not output PR_NUMBER")

            result_metadata["pr_number"] = pr_number
            if pr_url:
                result_metadata["pr_url"] = pr_url
            logger.info(f"PR created: {pr_url or 'N/A'} (#{pr_number})")
        except CapabilityError as e:
            logger.error(f"Failed to resolve pr.create: {e}")
            raise ActionExecutionError(f"Failed to resolve pr.create: {e}") from e
    else:
        # Update existing PR
        logger.info(f"Step 3: Updating existing pull request #{existing_pr_number}")

        # Find pr-description.md artifact
        body_file = project.artifacts_dir(ticket_key) / "pr-description.md"
        if not body_file.exists():
            raise ActionExecutionError(f"pr-description.md not found at {body_file}")

        update_cap = project.capabilities.get("pr.update")
        if not update_cap:
            raise ActionExecutionError("Capability 'pr.update' not found")

        try:
            update_argv = resolve(
                update_cap,
                str(repo_root),
                {"pr_number": existing_pr_number, "body_file": str(body_file)},
            )
            logger.debug(f"PR update argv: {update_argv}")
            result = subprocess.run(
                update_argv,
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                logger.error(f"pr.update failed: {result.stderr}")
                raise ActionExecutionError(f"pr.update failed: {result.stderr.strip()}")

            # Parse PR_URL from stdout
            pr_url = None
            for line in result.stdout.split("\n"):
                if line.startswith("PR_URL="):
                    pr_url = line.split("=", 1)[1]

            result_metadata["pr_number"] = existing_pr_number
            if pr_url:
                result_metadata["pr_url"] = pr_url
            logger.info(f"PR updated: {pr_url or 'N/A'} (#{existing_pr_number})")
        except CapabilityError as e:
            logger.error(f"Failed to resolve pr.update: {e}")
            raise ActionExecutionError(f"Failed to resolve pr.update: {e}") from e

    return result_metadata
