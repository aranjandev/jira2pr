"""End-to-end tests for the Copilot platform adapter."""

from pathlib import Path

from assembler.platforms.copilot import CopilotAssembler
from assembler.registry import CanonicalRegistry
from assembler.validator import validate
from assembler.writer import FileWriter

CANONICAL_DIR = Path(__file__).resolve().parent.parent.parent / "canonical"

AGENT_SLUGS = ["orchestrator", "supervisor", "jira-reader", "researcher", "planner", "coder", "reviewer", "pr-author"]


def _assemble(tmp_path):
    reg = CanonicalRegistry.load(CANONICAL_DIR)
    validate(reg, "copilot")
    writer = FileWriter(tmp_path)
    CopilotAssembler().assemble(reg, writer)
    writer.finalize()
    return tmp_path


def test_generates_all_eight_agents(tmp_path):
    out = _assemble(tmp_path)
    for slug in AGENT_SLUGS:
        assert (out / ".github/agents" / f"{slug}.agent.md").exists()


def test_orchestrator_agent_is_user_invocable_with_all_workers_and_supervisor(tmp_path):
    out = _assemble(tmp_path)
    content = (out / ".github/agents/orchestrator.agent.md").read_text()
    assert "user-invocable: true" in content
    assert "agents: [jira-reader, researcher, planner, coder, reviewer, pr-author, supervisor]" in content


def test_supervisor_agent_not_user_invocable(tmp_path):
    out = _assemble(tmp_path)
    content = (out / ".github/agents/supervisor.agent.md").read_text()
    assert "user-invocable: false" in content


def test_worker_agents_not_user_invocable(tmp_path):
    out = _assemble(tmp_path)
    content = (out / ".github/agents/coder.agent.md").read_text()
    assert "user-invocable: false" in content


def test_core_package_emitted(tmp_path):
    out = _assemble(tmp_path)
    assert (out / ".jira2pr/workflows/feature.workflow.yaml").exists()
    assert (out / ".jira2pr/artifacts/plan-schema.md").exists()
    assert (out / ".jira2pr/state/workflow-state.template.yaml").exists()
    assert (out / ".jira2pr/capabilities.yaml").exists()
    assert (out / ".jira2pr/config.yaml").exists()


def test_feature_prompt_generated(tmp_path):
    out = _assemble(tmp_path)
    content = (out / ".github/prompts/feature.prompt.md").read_text()
    assert 'agent: "orchestrator"' in content
    assert "jira-ingest" in content


def test_resume_and_status_prompts_generated(tmp_path):
    out = _assemble(tmp_path)
    assert (out / ".github/prompts/resume.prompt.md").exists()
    assert (out / ".github/prompts/status.prompt.md").exists()


def test_workflow_protocol_instructions_generated(tmp_path):
    out = _assemble(tmp_path)
    content = (out / ".github/instructions/workflow-protocol.instructions.md").read_text()
    assert "requirements_covered" in content
    assert "escalate" in content


def test_no_skills_or_model_tiers_json(tmp_path):
    out = _assemble(tmp_path)
    assert not (out / ".github/skills").exists()
    assert not (out / ".github/model-tiers.json").exists()
    assert not (out / ".github/scripts/apply_model_tiers.py").exists()


def test_model_baked_into_frontmatter(tmp_path):
    out = _assemble(tmp_path)
    content = (out / ".github/agents/jira-reader.agent.md").read_text()
    assert "GPT-5 mini" in content


def test_idempotent(tmp_path):
    _assemble(tmp_path)
    reg = CanonicalRegistry.load(CANONICAL_DIR)
    writer = FileWriter(tmp_path, check=True)
    CopilotAssembler().assemble(reg, writer)
    writer.finalize()
    assert writer.all_ok
