"""Tests for runtime.workflow.loader.RuntimeProject against a generated `.jira2pr/` tree."""

from pathlib import Path

import pytest

from assembler.platforms.aider import AiderAssembler
from assembler.registry import CanonicalRegistry
from assembler.writer import FileWriter
from runtime.workflow.loader import RuntimeProject, WorkflowNotFoundError

CANONICAL_DIR = Path(__file__).resolve().parent.parent.parent / "canonical"


@pytest.fixture
def project_dir(tmp_path):
    reg = CanonicalRegistry.load(CANONICAL_DIR)
    writer = FileWriter(tmp_path)
    AiderAssembler().assemble(reg, writer)
    writer.finalize()
    return tmp_path


def test_load_raises_if_no_jira2pr_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        RuntimeProject.load(tmp_path)


def test_loads_agents_and_workflows(project_dir):
    project = RuntimeProject.load(project_dir)
    assert {a.slug for a in project.agents} == {
        "orchestrator", "supervisor", "jira-reader", "researcher", "planner", "coder", "reviewer", "pr-author",
    }
    assert "feature" in project.workflows


def test_workflow_lookup_raises_for_unknown(project_dir):
    project = RuntimeProject.load(project_dir)
    with pytest.raises(WorkflowNotFoundError):
        project.workflow("nonexistent")


def test_agent_body_readable(project_dir):
    project = RuntimeProject.load(project_dir)
    assert "Coder Agent" in project.agent_body("coder")


def test_capabilities_and_workers_loaded(project_dir):
    project = RuntimeProject.load(project_dir)
    assert "jira.read" in project.capabilities
    assert project.workers["planner"].can_delegate == ("researcher",)


def test_agent_metadata_matches_config(project_dir):
    project = RuntimeProject.load(project_dir)
    reviewer = project.agent("reviewer")
    assert reviewer.model_tier == 2
    assert reviewer.artifact_schema == "review-schema.md"
