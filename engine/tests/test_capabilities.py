"""Tests for capability resolution (resolve function)."""

import pytest

from assembler.model import CapabilitySpec, CapabilityBinding
from runtime.capabilities import resolve, CapabilityError


def test_resolve_jira_read_with_ticket_key():
    """jira.read capability with a ticket key resolves to correct argv."""
    cap = CapabilitySpec(
        id="jira.read",
        description="Fetch and parse a JIRA issue",
        type="context",
        binding=CapabilityBinding(kind="script", handler="jira"),
    )
    argv = resolve(cap, "/repo", {"ticket_key_or_url": "PROJ-123"})
    assert argv == [
        "python3",
        "/repo/.jira2pr/runtime/integrations/jira.py",
        "PROJ-123",
    ]


def test_resolve_git_status_no_params():
    """git.status capability requires no parameters."""
    cap = CapabilitySpec(
        id="git.status",
        description="Read git status",
        type="context",
        binding=CapabilityBinding(kind="script", handler="git"),
    )
    argv = resolve(cap, "/repo", {})
    assert argv == [
        "python3",
        "/repo/.jira2pr/runtime/integrations/git.py",
        "status",
    ]


def test_resolve_git_commit_with_message():
    """git.commit capability requires a message parameter."""
    cap = CapabilitySpec(
        id="git.commit",
        description="Create a git commit",
        type="action",
        binding=CapabilityBinding(kind="script", handler="git"),
    )
    argv = resolve(cap, "/repo", {"message": "feat: add feature"})
    assert argv == [
        "python3",
        "/repo/.jira2pr/runtime/integrations/git.py",
        "commit",
        "feat: add feature",
    ]


def test_resolve_git_push_no_params():
    """git.push capability requires no parameters."""
    cap = CapabilitySpec(
        id="git.push",
        description="Push commits",
        type="action",
        binding=CapabilityBinding(kind="script", handler="git"),
    )
    argv = resolve(cap, "/repo", {})
    assert argv == [
        "python3",
        "/repo/.jira2pr/runtime/integrations/git.py",
        "push",
    ]


def test_resolve_pr_create():
    """pr.create capability requires title and body_file."""
    cap = CapabilitySpec(
        id="pr.create",
        description="Create a PR",
        type="action",
        binding=CapabilityBinding(kind="script", handler="github"),
    )
    argv = resolve(
        cap,
        "/repo",
        {"title": "feat: new feature", "body_file": "/tmp/pr_body.md"},
    )
    assert argv == [
        "python3",
        "/repo/.jira2pr/runtime/integrations/github.py",
        "create",
        "--title",
        "feat: new feature",
        "--body-file",
        "/tmp/pr_body.md",
    ]


def test_resolve_pr_update():
    """pr.update capability requires pr_number and body_file."""
    cap = CapabilitySpec(
        id="pr.update",
        description="Update a PR",
        type="action",
        binding=CapabilityBinding(kind="script", handler="github"),
    )
    argv = resolve(
        cap,
        "/repo",
        {"pr_number": "42", "body_file": "/tmp/pr_body.md"},
    )
    assert argv == [
        "python3",
        "/repo/.jira2pr/runtime/integrations/github.py",
        "update",
        "--pr-number",
        "42",
        "--body-file",
        "/tmp/pr_body.md",
    ]


def test_resolve_missing_required_parameter():
    """resolve() raises CapabilityError when required parameter is missing."""
    cap = CapabilitySpec(
        id="jira.read",
        description="Fetch and parse a JIRA issue",
        type="context",
        binding=CapabilityBinding(kind="script", handler="jira"),
    )
    with pytest.raises(CapabilityError, match="requires parameter 'ticket_key_or_url'"):
        resolve(cap, "/repo", {})


def test_resolve_extra_parameter():
    """resolve() raises CapabilityError when extra parameter is provided."""
    cap = CapabilitySpec(
        id="git.status",
        description="Read git status",
        type="context",
        binding=CapabilityBinding(kind="script", handler="git"),
    )
    with pytest.raises(CapabilityError, match="does not accept parameter"):
        resolve(cap, "/repo", {"extra": "param"})


def test_resolve_native_capability_error():
    """resolve() raises CapabilityError for native capabilities."""
    cap = CapabilitySpec(
        id="web.search",
        description="Search web",
        type="context",
        binding=CapabilityBinding(kind="native", handler=""),
    )
    with pytest.raises(CapabilityError, match="has no script binding"):
        resolve(cap, "/repo", {})


def test_resolve_unknown_handler():
    """resolve() raises CapabilityError for unknown handler."""
    cap = CapabilitySpec(
        id="unknown.read",
        description="Unknown capability",
        type="context",
        binding=CapabilityBinding(kind="script", handler="unknown_handler"),
    )
    with pytest.raises(CapabilityError, match="not in CAPABILITY_HANDLER_SCRIPT_MAP"):
        resolve(cap, "/repo", {})


def test_resolve_repo_root_with_trailing_slash():
    """resolve() correctly strips trailing slash from repo_root."""
    cap = CapabilitySpec(
        id="git.status",
        description="Read git status",
        type="context",
        binding=CapabilityBinding(kind="script", handler="git"),
    )
    argv = resolve(cap, "/repo/", {})
    # Should not have double slash
    assert "/repo//.jira2pr" not in " ".join(argv)
    assert argv[1] == "/repo/.jira2pr/runtime/integrations/git.py"
