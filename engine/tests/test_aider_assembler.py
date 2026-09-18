"""End-to-end tests for the Aider platform adapter."""

from pathlib import Path

from assembler.platforms.aider import AiderAssembler
from assembler.registry import CanonicalRegistry
from assembler.validator import validate
from assembler.writer import FileWriter

CANONICAL_DIR = Path(__file__).resolve().parent.parent.parent / "canonical"

AGENT_SLUGS = ["orchestrator", "supervisor", "jira-reader", "researcher", "planner", "coder", "reviewer", "pr-author"]


def _assemble(tmp_path):
    reg = CanonicalRegistry.load(CANONICAL_DIR)
    validate(reg, "aider")
    writer = FileWriter(tmp_path)
    AiderAssembler().assemble(reg, writer)
    writer.finalize()
    return tmp_path


def test_generates_agent_bodies(tmp_path):
    out = _assemble(tmp_path)
    for slug in AGENT_SLUGS:
        assert (out / ".jira2pr/agents" / f"{slug}.md").exists()


def test_no_generated_python(tmp_path):
    out = _assemble(tmp_path)
    assert list(out.rglob("*.py")) == []


def test_aider_cli_files_generated(tmp_path):
    out = _assemble(tmp_path)
    assert (out / ".aider.conf.yml").exists()
    assert (out / ".aiderignore").exists()


def test_aider_config_has_models(tmp_path):
    out = _assemble(tmp_path)
    content = (out / ".jira2pr/config/aider.yaml").read_text()
    assert "backend: aider" in content
    assert "models:" in content


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
    AiderAssembler().assemble(reg, writer)
    writer.finalize()
    assert writer.all_ok
