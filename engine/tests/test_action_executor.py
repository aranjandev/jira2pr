"""Tests for action execution."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from assembler.platforms.aider import AiderAssembler
from assembler.registry import CanonicalRegistry
from assembler.writer import FileWriter
from runtime.workflow.action_executor import (
    parse_pr_actions,
    strip_pr_actions_block,
    execute_actions,
    ActionExecutionError,
)
from runtime.workflow.loader import RuntimeProject

CANONICAL_DIR = Path(__file__).resolve().parent.parent.parent / "canonical"


@pytest.fixture
def project(tmp_path):
    reg = CanonicalRegistry.load(CANONICAL_DIR)
    writer = FileWriter(tmp_path)
    AiderAssembler().assemble(reg, writer)
    writer.finalize()
    return RuntimeProject.load(tmp_path)


def test_parse_pr_actions_valid_block():
    """parse_pr_actions extracts commit_message and pr_title from valid block."""
    response = """# PR Description

Some content here.

```pr-actions
commit_message: "feat: add feature"
pr_title: "Add feature"
```

More content.
"""
    result = parse_pr_actions(response)
    assert result == {
        "commit_message": "feat: add feature",
        "pr_title": "Add feature",
    }


def test_parse_pr_actions_with_quotes():
    """parse_pr_actions handles quoted and unquoted values."""
    response = """```pr-actions
commit_message: "feat: multi word message"
pr_title: Simple Title
```"""
    result = parse_pr_actions(response)
    assert result["commit_message"] == "feat: multi word message"
    assert result["pr_title"] == "Simple Title"


def test_parse_pr_actions_missing_block():
    """parse_pr_actions raises error when block not found."""
    response = "# Some content\nNo pr-actions here."
    with pytest.raises(ActionExecutionError, match="pr-actions block not found"):
        parse_pr_actions(response)


def test_parse_pr_actions_missing_commit_message():
    """parse_pr_actions raises error when commit_message is missing."""
    response = """```pr-actions
pr_title: "Add feature"
```"""
    with pytest.raises(ActionExecutionError, match="commit_message"):
        parse_pr_actions(response)


def test_parse_pr_actions_malformed_line():
    """parse_pr_actions raises error on malformed lines."""
    response = """```pr-actions
commit_message: "feat: add"
invalid line without colon
```"""
    with pytest.raises(ActionExecutionError, match="Invalid pr-actions line"):
        parse_pr_actions(response)


def test_strip_pr_actions_block():
    """strip_pr_actions_block removes the pr-actions block from response."""
    response = """# PR Description

Some content.

```pr-actions
commit_message: "feat: add"
pr_title: "Add"
```

More content here.
"""
    result = strip_pr_actions_block(response)
    assert "pr-actions" not in result
    assert "```" not in result
    assert "# PR Description" in result
    assert "Some content." in result
    assert "More content here." in result


def test_strip_pr_actions_block_preserves_other_fences():
    """strip_pr_actions_block only removes pr-actions fence, not others."""
    response = """# Content

```json
{"key": "value"}
```

```pr-actions
commit_message: "feat: add"
```

```python
print("hello")
```
"""
    result = strip_pr_actions_block(response)
    assert "```json" in result
    assert "```python" in result
    assert "pr-actions" not in result


@patch("runtime.workflow.action_executor.subprocess.run")
def test_execute_actions_create_new_pr(mock_run, project, tmp_path):
    """execute_actions creates a new PR and returns pr_number and pr_url."""
    # Mock subprocess calls for commit, push, create
    def run_side_effect(*args, **kwargs):
        argv = args[0]
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        
        if "git.py" in str(argv):
            if "commit" in argv:
                result.stdout = "Committed: feat: add feature"
            elif "push" in argv:
                result.stdout = "Pushed branch"
        elif "github.py" in str(argv):
            if "create" in argv:
                result.stdout = "PR_URL=https://github.com/test/test/pull/1\nPR_NUMBER=1\n"
        else:
            result.stdout = ""
        
        return result
    
    mock_run.side_effect = run_side_effect
    
    # Create a minimal workflow state
    from assembler.model import StateSpec
    state = StateSpec(
        name="submit",
        worker="pr-author",
        consumes=(),
        produces=("pr-description.md",),
        updates=(),
        success_criteria=None,
        max_attempts=None,
    )
    
    # Create pr-description.md artifact
    artifacts_dir = project.artifacts_dir("PROJ-1")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "pr-description.md").write_text("# PR Description\n\nTest content.")
    
    action_metadata = {
        "commit_message": "feat: add feature",
        "pr_title": "Add feature",
    }
    
    result = execute_actions(
        project,
        state,
        "PROJ-1",
        action_metadata,
        project.core_dir.parent,
        existing_pr_number=None,
    )
    
    assert result["pr_number"] == "1"
    assert result["pr_url"] == "https://github.com/test/test/pull/1"
    assert mock_run.call_count == 3  # commit, push, create


@patch("runtime.workflow.action_executor.subprocess.run")
def test_execute_actions_update_existing_pr(mock_run, project):
    """execute_actions updates existing PR when pr_number is provided."""
    def run_side_effect(*args, **kwargs):
        argv = args[0]
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        
        if "git.py" in str(argv):
            if "commit" in argv:
                result.stdout = "Committed"
            elif "push" in argv:
                result.stdout = "Pushed"
        elif "github.py" in str(argv):
            if "update" in argv:
                result.stdout = "PR_URL=https://github.com/test/test/pull/42\n"
        else:
            result.stdout = ""
        
        return result
    
    mock_run.side_effect = run_side_effect
    
    from assembler.model import StateSpec
    state = StateSpec(
        name="submit",
        worker="pr-author",
        consumes=(),
        produces=("pr-description.md",),
        updates=(),
        success_criteria=None,
        max_attempts=None,
    )
    
    # Create pr-description.md artifact
    artifacts_dir = project.artifacts_dir("PROJ-2")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    (artifacts_dir / "pr-description.md").write_text("# Updated PR\n\nTest content.")
    
    action_metadata = {"commit_message": "fix: update something"}
    
    result = execute_actions(
        project,
        state,
        "PROJ-2",
        action_metadata,
        project.core_dir.parent,
        existing_pr_number="42",
    )
    
    assert result["pr_number"] == "42"
    assert result["pr_url"] == "https://github.com/test/test/pull/42"
    # Should not call create for update
    assert mock_run.call_count == 3  # commit, push, update


@patch("runtime.workflow.action_executor.subprocess.run")
def test_execute_actions_missing_commit_message(mock_run, project):
    """execute_actions raises error if commit_message is missing."""
    from assembler.model import StateSpec
    state = StateSpec(
        name="submit",
        worker="pr-author",
        consumes=(),
        produces=(),
        updates=(),
        success_criteria=None,
        max_attempts=None,
    )
    
    action_metadata = {"pr_title": "Add feature"}  # missing commit_message
    
    with pytest.raises(ActionExecutionError, match="commit_message"):
        execute_actions(
            project,
            state,
            "PROJ-3",
            action_metadata,
            project.core_dir.parent,
            existing_pr_number=None,
        )


@patch("runtime.workflow.action_executor.subprocess.run")
def test_execute_actions_subprocess_failure(mock_run, project):
    """execute_actions raises error if subprocess fails."""
    mock_run.return_value = MagicMock(
        returncode=1, stderr="git error", stdout=""
    )
    
    from assembler.model import StateSpec
    state = StateSpec(
        name="submit",
        worker="pr-author",
        consumes=(),
        produces=(),
        updates=(),
        success_criteria=None,
        max_attempts=None,
    )
    
    action_metadata = {"commit_message": "feat: add"}
    
    with pytest.raises(ActionExecutionError, match="git.commit failed"):
        execute_actions(
            project,
            state,
            "PROJ-4",
            action_metadata,
            project.core_dir.parent,
            existing_pr_number=None,
        )
