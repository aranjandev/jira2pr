"""Aider run failures are backend invocation errors; preconditions are not."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from runtime.backends.aider import AiderBackend, AiderInvocationError
from runtime.backends.base import BackendInvocationError


def test_timeout_is_backend_invocation_error():
    backend = AiderBackend(timeout=5)
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="aider", timeout=5)), pytest.raises(BackendInvocationError, match="timed out"):
        backend._run(["aider"], model="m")


def test_non_zero_exit_is_backend_invocation_error():
    backend = AiderBackend()
    result = MagicMock(returncode=2, stderr="boom\n", stdout="")
    with patch("subprocess.run", return_value=result), pytest.raises(BackendInvocationError, match="exited 2"):
        backend._run(["aider"], model="m")


def test_missing_precondition_is_not_a_backend_error(tmp_path: Path):
    # A missing read file is a configuration problem and must stop the run.
    backend = AiderBackend()
    with pytest.raises(AiderInvocationError) as exc_info:
        backend.repair_repository(
            model="m",
            read_files=[tmp_path / "missing.md"],
            edit_files=[tmp_path / "a.py"],
            repo_root=tmp_path,
            test_command="",
            lint_command="",
        )
    assert not isinstance(exc_info.value, BackendInvocationError)
