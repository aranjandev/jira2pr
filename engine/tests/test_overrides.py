"""Tests for per-platform overrides under canonical/overrides/<platform>/.

An override replaces a canonical agent prompt or artifact schema for one
platform. The drift tests keep each override structurally aligned with the
canonical file it replaces.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
import yaml
from assembler.platforms.copilot import CopilotAssembler
from assembler.platforms.runtime import RuntimeAssembler
from assembler.registry import CanonicalRegistry
from assembler.validator import CanonicalValidationError, validate
from assembler.writer import FileWriter

CANONICAL_DIR = Path(__file__).resolve().parent.parent.parent / "canonical"
OVERRIDES_DIR = CANONICAL_DIR / "overrides"

OVERRIDE_FILES = sorted(
    p
    for p in OVERRIDES_DIR.glob("*/*/*")
    if p.is_file()
)


def _canonical_counterpart(override: Path) -> Path:
    kind = override.parent.name
    return CANONICAL_DIR / kind / override.name


def _markdown_headings(path: Path) -> list[str]:
    """Return heading lines outside fenced code blocks."""
    headings: list[str] = []
    in_fence = False
    for line in path.read_text().splitlines():
        if line.startswith("```"):
            in_fence = not in_fence
        elif not in_fence and line.startswith("#"):
            headings.append(line.strip())
    return headings


def _assemble_copilot(tmp_path: Path) -> Path:
    reg = CanonicalRegistry.load(CANONICAL_DIR)
    validate(reg, "copilot")
    writer = FileWriter(tmp_path)
    CopilotAssembler().assemble(reg, writer)
    writer.finalize()
    return tmp_path


def _assemble_runtime(tmp_path: Path) -> Path:
    reg = CanonicalRegistry.load(CANONICAL_DIR)
    validate(reg, "runtime")
    writer = FileWriter(tmp_path)
    RuntimeAssembler().assemble(reg, writer)
    writer.finalize()
    return tmp_path


# ---------------------------------------------------------------------------
# Drift: overrides must keep the structure of the canonical file they replace
# ---------------------------------------------------------------------------


def test_override_files_exist():
    assert OVERRIDE_FILES, "expected at least one override under canonical/overrides/"


@pytest.mark.parametrize(
    "override",
    OVERRIDE_FILES,
    ids=lambda p: str(p.relative_to(OVERRIDES_DIR)),
)
def test_override_has_canonical_counterpart(override):
    assert _canonical_counterpart(override).is_file()


@pytest.mark.parametrize(
    "override",
    [p for p in OVERRIDE_FILES if p.suffix == ".md"],
    ids=lambda p: str(p.relative_to(OVERRIDES_DIR)),
)
def test_markdown_override_keeps_canonical_headings(override):
    canonical = _markdown_headings(_canonical_counterpart(override))
    overridden = set(_markdown_headings(override))
    missing = [h for h in canonical if h not in overridden]
    assert not missing, (
        f"{override.relative_to(CANONICAL_DIR)} is missing canonical heading(s) "
        f"{missing}; update the override to match "
        f"{_canonical_counterpart(override).relative_to(CANONICAL_DIR)}"
    )


@pytest.mark.parametrize(
    "override",
    [p for p in OVERRIDE_FILES if p.suffix == ".yaml"],
    ids=lambda p: str(p.relative_to(OVERRIDES_DIR)),
)
def test_yaml_override_keeps_canonical_top_level_keys(override):
    canonical = set(yaml.safe_load(_canonical_counterpart(override).read_text()))
    overridden = set(yaml.safe_load(override.read_text()))
    missing = sorted(canonical - overridden)
    assert not missing, (
        f"{override.relative_to(CANONICAL_DIR)} is missing canonical key(s) "
        f"{missing}; update the override to match "
        f"{_canonical_counterpart(override).relative_to(CANONICAL_DIR)}"
    )


# ---------------------------------------------------------------------------
# Registry resolution
# ---------------------------------------------------------------------------


def test_agent_body_uses_override_for_platform():
    reg = CanonicalRegistry.load(CANONICAL_DIR)
    override = (OVERRIDES_DIR / "copilot/agents/planner.md").read_text()
    assert reg.agent_body("planner", "copilot") == override
    assert reg.agent_body("planner", "copilot") != reg.agent_body("planner")


def test_agent_body_falls_back_without_override():
    reg = CanonicalRegistry.load(CANONICAL_DIR)
    assert reg.agent_body("planner", "runtime") == reg.agent_body("planner")
    assert reg.agent_body("coder", "copilot") == reg.agent_body("coder")


def test_artifact_schema_files_swap_overridden_files():
    reg = CanonicalRegistry.load(CANONICAL_DIR)
    base = {p.name: p for p in reg.artifact_schema_files()}
    copilot = {p.name: p for p in reg.artifact_schema_files("copilot")}
    assert set(copilot) == set(base)
    assert copilot["plan.schema.yaml"].parent == OVERRIDES_DIR / "copilot/artifacts"
    assert copilot["requirements-schema.md"] == base["requirements-schema.md"]
    runtime = {p.name: p for p in reg.artifact_schema_files("runtime")}
    assert runtime == base


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _canonical_copy(tmp_path: Path) -> Path:
    dest = tmp_path / "canonical"
    shutil.copytree(CANONICAL_DIR, dest)
    return dest


def test_override_for_unknown_agent_rejected(tmp_path):
    canonical = _canonical_copy(tmp_path)
    (canonical / "overrides/copilot/agents/plannr.md").write_text("# Plannr\n")

    with pytest.raises(CanonicalValidationError) as exc_info:
        validate(CanonicalRegistry.load(canonical), "copilot")
    assert any("plannr" in e for e in exc_info.value.errors)


def test_override_for_unknown_artifact_rejected(tmp_path):
    canonical = _canonical_copy(tmp_path)
    (canonical / "overrides/copilot/artifacts/plan.schema.yml").write_text("version: 1\n")

    with pytest.raises(CanonicalValidationError) as exc_info:
        validate(CanonicalRegistry.load(canonical), "copilot")
    assert any("plan.schema.yml" in e for e in exc_info.value.errors)


# ---------------------------------------------------------------------------
# Generated output
# ---------------------------------------------------------------------------


def test_copilot_output_uses_overrides(tmp_path):
    out = _assemble_copilot(tmp_path)

    planner = (out / ".github/agents/planner.agent.md").read_text()
    assert "canonical/overrides/copilot/agents/planner.md" in planner
    assert "Plan Self-Check" in planner
    assert "exactly one repository file" not in planner

    schema = (out / ".jira2pr/artifacts/plan.schema.yaml").read_text()
    assert "files:" in schema
    assert "file_path" not in schema

    reviewer = (out / ".github/agents/reviewer.agent.md").read_text()
    assert "canonical/overrides/copilot/agents/reviewer.md" in reviewer
    assert "exact `file_path`" not in reviewer


def test_copilot_output_keeps_canonical_for_other_agents(tmp_path):
    out = _assemble_copilot(tmp_path)
    coder = (out / ".github/agents/coder.agent.md").read_text()
    assert "canonical/agents/coder.md" in coder


def test_runtime_output_is_unaffected_by_copilot_overrides(tmp_path):
    out = _assemble_runtime(tmp_path)
    reg = CanonicalRegistry.load(CANONICAL_DIR)

    planner = (out / ".jira2pr/agents/planner.md").read_text()
    assert "canonical/agents/planner.md" in planner
    assert planner.endswith(reg.agent_body("planner"))
    assert "operate on exactly one repository file" in planner

    schema = (out / ".jira2pr/artifacts/plan.schema.yaml").read_text()
    assert schema == (CANONICAL_DIR / "artifacts/plan.schema.yaml").read_text()
    review_schema = (out / ".jira2pr/artifacts/review-schema.md").read_text()
    assert review_schema == (CANONICAL_DIR / "artifacts/review-schema.md").read_text()


# ---------------------------------------------------------------------------
# Orchestrator supervision
# ---------------------------------------------------------------------------


def test_canonical_orchestrator_honors_disabled_supervisor():
    body = CanonicalRegistry.load(CANONICAL_DIR).agent_body("orchestrator")
    assert "current.validation.supervisor == false" in body


def test_copilot_orchestrator_self_evaluates_all_but_planning(tmp_path):
    out = _assemble_copilot(tmp_path)
    orchestrator = (out / ".github/agents/orchestrator.agent.md").read_text()
    assert "canonical/overrides/copilot/agents/orchestrator.md" in orchestrator
    assert 'current.validation.success_criteria == "planning"' in orchestrator
    assert "## Self-Evaluation" in orchestrator
    for criteria in ("jira-ingest", "review", "submit"):
        assert f"| `{criteria}` |" in orchestrator


def test_copilot_orchestrator_still_delegates_to_supervisor(tmp_path):
    out = _assemble_copilot(tmp_path)
    orchestrator = (out / ".github/agents/orchestrator.agent.md").read_text()
    assert "agents: [jira-reader, researcher, planner, coder, reviewer, pr-author, supervisor]" in orchestrator
    assert "invoke(supervisor," in orchestrator


def test_self_evaluated_criteria_are_defined_in_success_criteria():
    reg = CanonicalRegistry.load(CANONICAL_DIR)
    body = (OVERRIDES_DIR / "copilot/agents/orchestrator.md").read_text()
    for key in reg.success_criteria.criteria:
        if key != "planning":
            assert f"| `{key}` |" in body, f"override must cover self-evaluated criteria '{key}'"
