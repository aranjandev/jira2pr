"""Scope enforcement against a real git working tree."""

import subprocess
from pathlib import Path

import pytest
from runtime.workflow.task_scope import capture_scope, revert_out_of_scope


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        capture_output=True,
        check=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    (tmp_path / "allowed.py").write_text("a = 1\n", encoding="utf-8")
    (tmp_path / "other.py").write_text("b = 1\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "init")
    return tmp_path


def test_out_of_scope_tracked_and_new_files_are_reverted(repo: Path):
    snapshot = capture_scope(repo)

    (repo / "allowed.py").write_text("a = 2\n", encoding="utf-8")
    (repo / "other.py").write_text("b = 2\n", encoding="utf-8")
    (repo / "stray.py").write_text("c = 1\n", encoding="utf-8")

    reverted = revert_out_of_scope(snapshot, allowed={repo / "allowed.py"})

    assert sorted(reverted) == ["other.py", "stray.py"]
    assert (repo / "allowed.py").read_text(encoding="utf-8") == "a = 2\n"
    assert (repo / "other.py").read_text(encoding="utf-8") == "b = 1\n"
    assert not (repo / "stray.py").exists()


def test_file_dirty_before_capture_is_restored_to_captured_bytes(repo: Path):
    # An earlier task already changed other.py. This task must not change it again.
    (repo / "other.py").write_text("b = from-earlier-task\n", encoding="utf-8")
    snapshot = capture_scope(repo)

    (repo / "other.py").write_text("b = from-this-task\n", encoding="utf-8")
    (repo / "allowed.py").write_text("a = 2\n", encoding="utf-8")

    reverted = revert_out_of_scope(snapshot, allowed={repo / "allowed.py"})

    assert reverted == ["other.py"]
    assert (repo / "other.py").read_text(encoding="utf-8") == "b = from-earlier-task\n"
    assert (repo / "allowed.py").read_text(encoding="utf-8") == "a = 2\n"


def test_no_out_of_scope_change_reverts_nothing(repo: Path):
    snapshot = capture_scope(repo)
    (repo / "allowed.py").write_text("a = 3\n", encoding="utf-8")

    assert revert_out_of_scope(snapshot, allowed={repo / "allowed.py"}) == []
    assert (repo / "allowed.py").read_text(encoding="utf-8") == "a = 3\n"


def test_non_git_directory_checks_nothing(tmp_path: Path):
    (tmp_path / "f.py").write_text("x = 1\n", encoding="utf-8")
    snapshot = capture_scope(tmp_path)
    (tmp_path / "f.py").write_text("x = 2\n", encoding="utf-8")

    assert revert_out_of_scope(snapshot, allowed=set()) == []
