"""Tests for assembler.registry.CanonicalRegistry against the real canonical/ tree."""

from pathlib import Path

from assembler.registry import CanonicalRegistry

CANONICAL_DIR = Path(__file__).resolve().parent.parent.parent / "canonical"


def _load():
    return CanonicalRegistry.load(CANONICAL_DIR)


def test_loads_all_eight_agents():
    reg = _load()
    slugs = {a.slug for a in reg.agents}
    assert slugs == {
        "orchestrator", "supervisor", "jira-reader", "researcher", "planner", "coder", "reviewer", "pr-author",
    }


def test_agent_model_tier_and_kind():
    reg = _load()
    orchestrator = reg.agent("orchestrator")
    assert orchestrator.kind == "orchestrator"
    assert orchestrator.model_tier == 0
    supervisor = reg.agent("supervisor")
    assert supervisor.kind == "supervisor"
    assert supervisor.model_tier == 2
    coder = reg.agent("coder")
    assert coder.kind == "worker"
    assert coder.artifact_schema is None


def test_feature_workflow_loaded():
    reg = _load()
    assert "feature" in reg.workflows
    feature = reg.workflows["feature"]
    assert feature.initial_state == "jira-ingest"
    assert set(feature.states) == {
        "jira-ingest", "plan", "implement", "review", "submit", "done", "human-review",
    }


def test_empty_workflows_skipped_with_warning():
    reg = _load()
    assert "bugfix" not in reg.workflows
    assert "scope-creep" not in reg.workflows
    assert any("bugfix" in w for w in reg.warnings)
    assert any("scope-creep" in w for w in reg.warnings)


def test_success_criteria_loaded():
    reg = _load()
    assert reg.success_criteria.criteria["planning"] == (
        "requirements_covered", "implementation_feasible", "test_strategy_defined",
    )


def test_workers_loaded():
    reg = _load()
    assert reg.workers["planner"].can_delegate == ("researcher",)
    assert reg.workers["pr-author"].actions == ("git.commit", "git.push", "pr.create", "pr.update")
    assert reg.workers["orchestrator"].can_delegate == (
        "jira-reader", "researcher", "planner", "coder", "reviewer", "pr-author", "supervisor",
    )


def test_capabilities_loaded_with_bindings():
    reg = _load()
    jira_read = reg.capabilities["jira.read"]
    assert jira_read.type == "context"
    assert jira_read.binding.kind == "script"
    assert jira_read.binding.handler == "jira"
    web_search = reg.capabilities["web.search"]
    assert web_search.binding.kind == "native"


def test_model_for_tier_all_platforms():
    reg = _load()
    assert "GPT-5.6 Luna (copilot)" in reg.model_for_tier(0, "copilot")
    assert reg.model_for_tier(2, "aider")
    assert "unknown for" in reg.model_for_tier(2, "nonexistent-platform")


def test_execution_policy_loaded():
    reg = _load()
    assert reg.execution_policy.default_max_attempts == 1
    assert reg.execution_policy.on_exhaustion == "escalate"
    assert reg.execution_policy.terminal_success_state == "done"
    assert reg.execution_policy.terminal_escalated_state == "human-review"
    assert reg.execution_policy.max_total_iterations == 40


def test_artifact_schema_files_exclude_registry():
    reg = _load()
    names = {p.name for p in reg.artifact_schema_files()}
    assert "plan-schema.md" in names
    assert "REGISTRY.md" not in names
