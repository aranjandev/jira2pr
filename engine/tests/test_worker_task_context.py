"""Tests for dependency-aware read-only context of repository tasks."""

from __future__ import annotations

from pathlib import Path

from runtime.workflow.worker_invoker import (
    RepositoryTask,
    _build_task_read_files,
    _dependency_read_files,
)


def _task(task_id: str, file_path: str, dependencies: tuple[str, ...] = ()) -> RepositoryTask:
    return RepositoryTask(
        id=task_id,
        kind="test" if task_id.startswith("TEST") else "implementation",
        file_path=file_path,
        edit_mode="modify",
        instructions="",
        dependencies=dependencies,
    )


def test_dependency_files_are_included_for_dependent_task(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "tests").mkdir()
    impl = tmp_path / "pkg" / "main.py"
    impl.write_text("def load(): ...\n", encoding="utf-8")
    test = tmp_path / "tests" / "test_main.py"
    test.write_text("", encoding="utf-8")

    tasks = [
        _task("T2", "pkg/main.py"),
        _task("TEST1", "tests/test_main.py", dependencies=("T2",)),
    ]

    result = _dependency_read_files(
        task=tasks[1],
        tasks=tasks,
        repo_root=tmp_path,
        target_path=test.resolve(),
    )

    assert result == [impl.resolve()]


def test_non_dependency_and_self_target_files_are_excluded(tmp_path):
    (tmp_path / "a.py").write_text("", encoding="utf-8")
    (tmp_path / "b.py").write_text("", encoding="utf-8")
    tasks = [
        _task("T1", "a.py"),
        _task("T2", "b.py", dependencies=("T1",)),
    ]

    # Target equals the dependency's file: nothing extra is added.
    result = _dependency_read_files(
        task=tasks[1],
        tasks=tasks,
        repo_root=tmp_path,
        target_path=(tmp_path / "a.py").resolve(),
    )
    assert result == []

    # A task without dependencies gets no extra files.
    assert _dependency_read_files(
        task=tasks[0],
        tasks=tasks,
        repo_root=tmp_path,
        target_path=(tmp_path / "b.py").resolve(),
    ) == []


def test_missing_dependency_file_is_skipped(tmp_path):
    tasks = [
        _task("T1", "does_not_exist.py"),
        _task("T2", "b.py", dependencies=("T1",)),
    ]

    assert _dependency_read_files(
        task=tasks[1],
        tasks=tasks,
        repo_root=tmp_path,
        target_path=(tmp_path / "b.py").resolve(),
    ) == []


def test_build_task_read_files_orders_dependencies_before_task_context(tmp_path):
    plan = Path("plan.yaml")
    shared = Path("AGENTS.md")
    dependency = Path("dep.py")
    context = Path("coder-task-TEST1.yaml")

    result = _build_task_read_files(
        read_files=[plan, shared],
        task_context_path=context,
        dependency_files=[dependency],
    )

    assert result == [shared, dependency, context]


def test_build_task_read_files_default_has_no_dependencies():
    result = _build_task_read_files(
        read_files=[Path("AGENTS.md")],
        task_context_path=Path("ctx.yaml"),
    )

    assert result == [Path("AGENTS.md"), Path("ctx.yaml")]
