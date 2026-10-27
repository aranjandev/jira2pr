"""Deterministic lint autofix: the fixer only receives the plan's files."""

import shlex
import sys
from pathlib import Path

from runtime.workflow.evidence import apply_lint_autofix

UNUSED_IMPORT = "import os\n\nx = 1\n"


def test_autofix_fixes_planned_files_only(tmp_path: Path):
    (tmp_path / "planned.py").write_text(UNUSED_IMPORT, encoding="utf-8")
    (tmp_path / "other.py").write_text(UNUSED_IMPORT, encoding="utf-8")

    command = f"{shlex.quote(sys.executable)} -m ruff check --fix --select F401"
    apply_lint_autofix(
        command=command,
        changed_files=[Path("planned.py")],
        repo_root=tmp_path,
    )

    assert "import os" not in (tmp_path / "planned.py").read_text(encoding="utf-8")
    assert (tmp_path / "other.py").read_text(encoding="utf-8") == UNUSED_IMPORT


def test_missing_autofix_command_does_not_stop_the_run(tmp_path: Path):
    (tmp_path / "planned.py").write_text(UNUSED_IMPORT, encoding="utf-8")

    apply_lint_autofix(
        command="definitely-not-a-real-command-xyz",
        changed_files=[Path("planned.py")],
        repo_root=tmp_path,
    )

    assert (tmp_path / "planned.py").read_text(encoding="utf-8") == UNUSED_IMPORT


def test_empty_command_is_a_no_op(tmp_path: Path):
    (tmp_path / "planned.py").write_text(UNUSED_IMPORT, encoding="utf-8")

    apply_lint_autofix(command="", changed_files=[Path("planned.py")], repo_root=tmp_path)

    assert (tmp_path / "planned.py").read_text(encoding="utf-8") == UNUSED_IMPORT
