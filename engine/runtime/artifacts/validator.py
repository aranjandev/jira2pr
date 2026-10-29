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

    seen_ids: set[str] = set()

    _validate_plan_section(
        raw_entries=data.get("tasks"),
        section="tasks",
        kind="implementation",
        repo_root=repo_root,
        seen_ids=seen_ids,
    )

    _validate_plan_section(
        raw_entries=data.get("tests"),
        section="tests",
        kind="test",
        repo_root=repo_root,
        seen_ids=seen_ids,
    )

    return data


def _validate_plan_section(
    *,
    raw_entries: object,
    section: str,
    kind: str,
    repo_root: Path,
    seen_ids: set[str],
) -> None:
    """Validate one executable section of plan.yaml."""

    if not isinstance(raw_entries, list) or not raw_entries:
        raise ArtifactValidationError(
            f"plan.yaml must contain a non-empty {section} list"
        )

    allowed_edit_modes = (
        {"create", "modify", "delete"}
        if kind == "implementation"
        else {"create", "modify"}
    )

    repo_root = repo_root.resolve()

    for index, entry in enumerate(raw_entries):
        prefix = f"{section}[{index}]"

        if not isinstance(entry, dict):
            raise ArtifactValidationError(
                f"{prefix} must be a mapping"
            )

        task_id = entry.get("id")
        file_path = entry.get("file_path")
        edit_mode = entry.get("edit_mode")
        instructions = entry.get("instructions")
        dependencies = entry.get("dependencies")
        verifies = entry.get("verifies")

        # --------------------------------------------------------------
        # ID
        # --------------------------------------------------------------

        if not isinstance(task_id, str) or not task_id.strip():
            raise ArtifactValidationError(
                f"{prefix}.id must be a non-empty string"
            )

        task_id = task_id.strip()

        if task_id in seen_ids:
            raise ArtifactValidationError(
                f"Duplicate task id: {task_id}"
            )

        # --------------------------------------------------------------
        # File path
        # --------------------------------------------------------------

        if not isinstance(file_path, str) or not file_path.strip():
            raise ArtifactValidationError(
                f"{prefix}.file_path must be a non-empty string"
            )

        file_path = file_path.strip()

        # --------------------------------------------------------------
        # Edit mode
        # --------------------------------------------------------------

        if edit_mode not in allowed_edit_modes:
            raise ArtifactValidationError(
                f"{prefix}.edit_mode has unsupported value "
                f"{edit_mode!r}; expected one of "
                f"{sorted(allowed_edit_modes)}"
            )

        # --------------------------------------------------------------
        # Instructions
        # --------------------------------------------------------------

        if (
            not isinstance(instructions, str)
            or not instructions.strip()
        ):
            raise ArtifactValidationError(
                f"{prefix}.instructions must be non-empty"
            )

        # --------------------------------------------------------------
        # Dependencies
        # --------------------------------------------------------------

        if not isinstance(dependencies, list):
            raise ArtifactValidationError(
                f"{prefix}.dependencies must be a list"
            )

        if not all(
            isinstance(dependency, str) and dependency.strip()
            for dependency in dependencies
        ):
            raise ArtifactValidationError(
                f"{prefix}.dependencies must contain non-empty task IDs"
            )

        # Dependencies must refer to tasks already encountered.
        for dependency in dependencies:
            dependency = dependency.strip()

            if dependency not in seen_ids:
                raise ArtifactValidationError(
                    f"{prefix}.dependencies references unknown "
                    f"or later task '{dependency}'"
                )

        # --------------------------------------------------------------
        # Test-specific fields
        # --------------------------------------------------------------

        if kind == "test":
            if not isinstance(verifies, list) or not verifies:
                raise ArtifactValidationError(
                    f"{prefix}.verifies must be a non-empty list"
                )

            if not all(
                isinstance(item, str) and item.strip()
                for item in verifies
            ):
                raise ArtifactValidationError(
                    f"{prefix}.verifies must contain non-empty strings"
                )

        # --------------------------------------------------------------
        # Repository path validation
        # --------------------------------------------------------------

        target = (
            repo_root
            / file_path
        ).resolve()

        try:
            target.relative_to(repo_root)
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

        # Only add this ID after validation so later entries may depend on it.
        seen_ids.add(task_id)


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