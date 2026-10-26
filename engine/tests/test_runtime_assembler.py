"""End-to-end tests for the runtime platform adapter (LiteLLM + Aider backend)."""

from pathlib import Path

from assembler.platforms.runtime import RuntimeAssembler
from assembler.registry import CanonicalRegistry
from assembler.validator import validate
from assembler.writer import FileWriter

CANONICAL_DIR = Path(__file__).resolve().parent.parent.parent / "canonical"

# The runtime platform does not execute the orchestrator agent.
AGENT_SLUGS = ["supervisor", "jira-reader", "researcher", "planner", "coder", "reviewer", "pr-author"]


def _assemble(tmp_path):
    reg = CanonicalRegistry.load(CANONICAL_DIR)
    validate(reg, "runtime")
    writer = FileWriter(tmp_path)
    RuntimeAssembler().assemble(reg, writer)
    writer.finalize()
    return tmp_path


def test_generates_agent_bodies(tmp_path):
    out = _assemble(tmp_path)
    for slug in AGENT_SLUGS:
        assert (out / ".jira2pr/agents" / f"{slug}.md").exists()
    assert not (out / ".jira2pr/agents/orchestrator.md").exists()


def test_runtime_integrations_generated(tmp_path):
    out = _assemble(tmp_path)
    assert (out / ".jira2pr/runtime/integrations/jira.py").exists()


def test_aider_cli_files_generated(tmp_path):
    out = _assemble(tmp_path)
    assert (out / ".aider.conf.yml").exists()
    assert (out / ".aiderignore").exists()


def test_runtime_config_has_models_and_backends(tmp_path):
    out = _assemble(tmp_path)
    content = (out / ".jira2pr/config/runtime.yaml").read_text()
    assert "backend: jira2pr" in content
    assert "models:" in content
    assert "repository: aider" in content
    assert "orchestrator" not in content


def test_core_package_shared_with_copilot(tmp_path):
    out = _assemble(tmp_path)
    assert (out / ".jira2pr/workflows/feature.workflow.yaml").exists()
    assert (out / ".jira2pr/capabilities.yaml").exists()
    assert (out / ".jira2pr/state/workflow-state.template.yaml").exists()


def test_readme_generated(tmp_path):
    out = _assemble(tmp_path)
    assert (out / ".jira2pr/README.md").exists()


def test_idempotent(tmp_path):
    _assemble(tmp_path)
    reg = CanonicalRegistry.load(CANONICAL_DIR)
    writer = FileWriter(tmp_path, check=True)
    RuntimeAssembler().assemble(reg, writer)
    writer.finalize()
    assert writer.all_ok


def test_project_instructions_generated_at_root(tmp_path):
    out = _assemble(tmp_path)
    agents_file = out / "AGENTS.md"
    assert agents_file.exists()
    content = agents_file.read_text()
    assert "How Agents Contribute to Code" in content
    assert "### Agent Roster" in content


def test_orchestrator_excluded_from_aider_roster(tmp_path):
    out = _assemble(tmp_path)
    content = (out / "AGENTS.md").read_text()
    # Orchestrator row should not appear in the roster table for Aider
    assert "| **orchestrator**" not in content
    # But other agents should still be there
    assert "| **coder**" in content
    assert "| **supervisor**" in content
    # The static prose can still mention orchestrator (explaining Copilot vs Aider difference)
    # but the dynamic roster table should exclude it
