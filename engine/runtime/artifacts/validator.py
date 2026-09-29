"""Validation for generated workflow artifacts."""

from __future__ import annotations

from pathlib import Path

import yaml


class ArtifactValidationError(ValueError):
    """Raised when a generated artifact is invalid."""


def validate_plan(
    plan_path: Path,
    repo_root: Path,
) -> dict:
    """Parse and validate a generated plan.yaml."""

    try:
        data = yaml.safe_load(
            plan_path.read_text(encoding="utf-8")
        )
    except yaml.YAMLError as exc:
        raise ArtifactValidationError(
            f"Invalid YAML in {plan_path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ArtifactValidationError(
            "plan.yaml must contain a YAML mapping"
        )

    if data.get("version") != 1:
        raise ArtifactValidationError(
            "plan.yaml must declare version: 1"
        )

    tasks = data.get("tasks")

    if not isinstance(tasks, list) or not tasks:
        raise ArtifactValidationError(
            "plan.yaml must contain a non-empty tasks list"
        )

    seen_ids: set[str] = set()

    for index, task in enumerate(tasks):
        prefix = f"tasks[{index}]"

        if not isinstance(task, dict):
            raise ArtifactValidationError(
                f"{prefix} must be a mapping"
            )

        task_id = task.get("id")
        file_path = task.get("file_path")
        edit_mode = task.get("edit_mode")
        instructions = task.get("instructions")
        dependencies = task.get("dependencies")

        if not isinstance(task_id, str) or not task_id:
            raise ArtifactValidationError(
                f"{prefix}.id must be a non-empty string"
            )

        if task_id in seen_ids:
            raise ArtifactValidationError(
                f"Duplicate task id: {task_id}"
            )

        if not isinstance(file_path, str) or not file_path:
            raise ArtifactValidationError(
                f"{prefix}.file_path must be a non-empty string"
            )

        if edit_mode not in {"create", "modify", "delete"}:
            raise ArtifactValidationError(
                f"{prefix}.edit_mode must be "
                "create, modify, or delete"
            )

        if not isinstance(instructions, str) or not instructions.strip():
            raise ArtifactValidationError(
                f"{prefix}.instructions must be non-empty"
            )

        if not isinstance(dependencies, list):
            raise ArtifactValidationError(
                f"{prefix}.dependencies must be a list"
            )

        # Dependencies must refer to previously defined tasks.
        for dependency in dependencies:
            if dependency not in seen_ids:
                raise ArtifactValidationError(
                    f"{prefix}.dependencies references "
                    f"unknown or later task '{dependency}'"
                )

        target = (repo_root / file_path).resolve()

        try:
            target.relative_to(repo_root.resolve())
        except ValueError as exc:
            raise ArtifactValidationError(
                f"{prefix}.file_path escapes repository root: "
                f"{file_path}"
            ) from exc

        if edit_mode in {"modify", "delete"} and not target.is_file():
            raise ArtifactValidationError(
                f"{prefix}: {edit_mode} target does not exist: "
                f"{file_path}"
            )

        if edit_mode == "create" and target.exists():
            raise ArtifactValidationError(
                f"{prefix}: create target already exists: "
                f"{file_path}"
            )

        seen_ids.add(task_id)

    return data

def validate_artifact(
    path: Path,
    *,
    repo_root: Path,
) -> None:
    if path.name == "plan.yaml":
        validate_plan(
            path,
            repo_root,
        )