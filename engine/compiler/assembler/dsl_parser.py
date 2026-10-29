"""Pure parsing functions for the canonical/generated workflow DSL.

These are shared by the compiler (`assembler.registry.CanonicalRegistry`,
parsing from `canonical/`) and the runtime engine (`runtime.workflow.loader`,
parsing from the generated `.jira2pr/` tree inside a target repo) so both
sides read the exact same schema and can never silently diverge.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None  # type: ignore[assignment]

from assembler.model import (
    CapabilityBinding,
    CapabilitySpec,
    ExecutionPolicy,
    StateSpec,
    SuccessCriteria,
    SupervisorContract,
    TransitionSpec,
    WorkerBinding,
    WorkflowSpec,
)


def load_yaml(path: Path) -> Any:
    """Load a YAML file. Requires pyyaml."""
    text = path.read_text()
    if yaml is not None:
        return yaml.safe_load(text)
    raise SystemExit(
        "pyyaml is not installed. Install it (`pip install pyyaml`) or run "
        "this script inside an environment where it is available."
    )


def as_str_tuple(value: Any) -> tuple[str, ...]:
    """Normalize a YAML list field into a tuple of non-empty strings.

    Tolerates malformed/empty nested entries (e.g. an accidental `- []`).
    """
    if not value:
        return ()
    return tuple(str(item) for item in value if item)


def _parse_iteration_cap(raw: Any) -> tuple[int | None, int | None]:
    """Return ``(base, per_task)`` for ``retry.max_total_iterations``.

    Accepts a plain integer (fixed cap, ``per_task`` is None) or a mapping
    ``{base: int, per_task: int}`` where the effective cap is
    ``base + per_task * task_count``.
    """
    if raw is None:
        return None, None
    if isinstance(raw, dict):
        base = raw.get("base")
        per_task = raw.get("per_task")
        return (
            int(base) if base is not None else None,
            int(per_task) if per_task is not None else None,
        )
    return int(raw), None


def parse_workflow_file(path: Path, root: Path) -> WorkflowSpec | None:
    """Parse one ``*.workflow.yaml`` file. Returns None if the file is empty."""
    if path.stat().st_size == 0:
        return None
    raw = load_yaml(path) or {}
    name = raw["workflow"]
    states: dict[str, StateSpec] = {}
    for state_name, state_raw in (raw.get("states") or {}).items():
        state_raw = state_raw or {}
        transitions_raw = state_raw.get("transitions") or {}
        kind = state_raw.get("kind", "worker")
        if kind not in ("worker", "verification"):
            raise ValueError(
                f"{path}: state '{state_name}' has unknown kind {kind!r} "
                "(expected 'worker' or 'verification')"
            )
        states[state_name] = StateSpec(
            name=state_name,
            worker=state_raw.get("worker"),
            consumes=as_str_tuple(state_raw.get("consumes")),
            produces=as_str_tuple(state_raw.get("produces")),
            updates=as_str_tuple(state_raw.get("updates")),
            success_criteria=(state_raw.get("validation") or {}).get("success_criteria"),
            max_attempts=(state_raw.get("retry") or {}).get("max_attempts"),
            budget=(state_raw.get("retry") or {}).get("budget"),
            kind=kind,
            supervised=bool((state_raw.get("validation") or {}).get("supervisor", True)),
            transitions=TransitionSpec(
                success=transitions_raw.get("success"),
                failure=transitions_raw.get("failure"),
                escalate=transitions_raw.get("escalate"),
                invalid_output=transitions_raw.get("invalid_output"),
            ),
            terminal=bool(state_raw.get("terminal", False)),
            outcome=state_raw.get("outcome"),
        )
    try:
        source_path = str(path.relative_to(root))
    except ValueError:
        source_path = str(path)
    base_cap, per_task_cap = _parse_iteration_cap((raw.get("retry") or {}).get("max_total_iterations"))
    return WorkflowSpec(
        name=name,
        version=int(raw.get("version", 1)),
        initial_state=raw["initial_state"],
        states=states,
        source_path=source_path,
        max_total_iterations=base_cap,
        max_total_iterations_per_task=per_task_cap,
        budgets={str(k): int(v) for k, v in (raw.get("budgets") or {}).items()},
    )


def parse_workflows_dir(workflows_dir: Path, root: Path) -> tuple[dict[str, WorkflowSpec], list[str]]:
    """Parse all ``*.workflow.yaml`` files in a directory.

    Returns ``(workflows, warnings)``; empty files are skipped with a warning
    rather than raising (e.g. bugfix/scope-creep are intentionally unfilled).
    """
    workflows: dict[str, WorkflowSpec] = {}
    warnings: list[str] = []
    for path in sorted(workflows_dir.glob("*.workflow.yaml")):
        spec = parse_workflow_file(path, root)
        if spec is None:
            try:
                rel = path.relative_to(root)
            except ValueError:
                rel = path
            warnings.append(f"Skipping empty workflow definition: {rel}")
            continue
        workflows[spec.name] = spec
    return workflows, warnings


def parse_success_criteria(path: Path) -> SuccessCriteria:
    raw = load_yaml(path) or {}
    return SuccessCriteria(
        criteria={
            key: as_str_tuple(labels)
            for key, labels in (raw.get("success_criteria") or {}).items()
        }
    )


def parse_workers(path: Path) -> dict[str, WorkerBinding]:
    raw = load_yaml(path) or {}
    workers: dict[str, WorkerBinding] = {}
    for slug, data in (raw.get("workers") or {}).items():
        data = data or {}
        workers[slug] = WorkerBinding(
            slug=slug,
            runtime_context=as_str_tuple(data.get("runtime_context")),
            can_delegate=as_str_tuple(data.get("can_delegate")),
            actions=as_str_tuple(data.get("actions")),
        )
    return workers


def parse_supervisor_contract(path: Path) -> SupervisorContract:
    raw = (load_yaml(path) or {}).get("supervisor") or {}
    return SupervisorContract(
        output_schema=raw.get("output_schema") or {},
        criteria_evaluation=as_str_tuple(raw.get("criteria_evaluation")),
        instructions=(raw.get("instructions") or "").strip(),
    )


def parse_execution_policy(path: Path) -> ExecutionPolicy:
    raw = (load_yaml(path) or {}).get("execution_policy") or {}
    retry = raw.get("retry") or {}
    criteria = raw.get("criteria_evaluation") or {}
    terminal = raw.get("terminal_outcomes") or {}
    return ExecutionPolicy(
        default_max_attempts=int(retry.get("default_max_attempts", 1)),
        on_exhaustion=retry.get("on_exhaustion", "escalate"),
        criteria_mode=criteria.get("mode", "all_pass"),
        terminal_success_state=terminal.get("success", "done"),
        terminal_escalated_state=terminal.get("escalated", "human-review"),
        max_total_iterations=int(retry.get("max_total_iterations", 40)),
    )


def parse_capabilities(path: Path) -> dict[str, CapabilitySpec]:
    raw = load_yaml(path) or {}
    capabilities: dict[str, CapabilitySpec] = {}

    for cap_id, data in (raw.get("capabilities") or {}).items():
        data = data or {}
        binding_raw = data.get("binding") or {"kind": "native"}
        binding = CapabilityBinding(
            kind=binding_raw.get("kind", "native"),
            handler=binding_raw.get("handler"),
        )
        capabilities[cap_id] = CapabilitySpec(
            id=cap_id,
            description=data.get("description", ""),
            type=data.get("type", "context"),
            binding=binding,
        )

    return capabilities