"""Tests for assembler.validator — cross-reference checks over the canonical DSL.

Each test constructs a minimally broken registry (by mutating a copy loaded
from the real canonical/ tree) and asserts the validator catches it with a
message naming the offending file/key.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from assembler.model import StateSpec, TransitionSpec
from assembler.registry import CanonicalRegistry
from assembler.validator import CanonicalValidationError, validate

CANONICAL_DIR = Path(__file__).resolve().parent.parent.parent / "canonical"


def _load():
    return CanonicalRegistry.load(CANONICAL_DIR)


def test_valid_registry_passes():
    reg = _load()
    validate(reg, "copilot")
    validate(reg, "aider")


def test_unknown_worker_rejected():
    reg = _load()
    feature = reg.workflows["feature"]
    states = dict(feature.states)
    states["plan"] = replace(states["plan"], worker="nonexistent-worker")
    reg.workflows["feature"] = replace(feature, states=states)

    with pytest.raises(CanonicalValidationError) as exc_info:
        validate(reg, "copilot")
    assert any("nonexistent-worker" in e for e in exc_info.value.errors)


def test_unknown_transition_target_rejected():
    reg = _load()
    feature = reg.workflows["feature"]
    states = dict(feature.states)
    states["plan"] = replace(
        states["plan"], transitions=replace(states["plan"].transitions, success="nowhere")
    )
    reg.workflows["feature"] = replace(feature, states=states)

    with pytest.raises(CanonicalValidationError) as exc_info:
        validate(reg, "copilot")
    assert any("nowhere" in e for e in exc_info.value.errors)


def test_unknown_success_criteria_key_rejected():
    reg = _load()
    feature = reg.workflows["feature"]
    states = dict(feature.states)
    states["plan"] = replace(states["plan"], success_criteria="not-a-real-key")
    reg.workflows["feature"] = replace(feature, states=states)

    with pytest.raises(CanonicalValidationError) as exc_info:
        validate(reg, "copilot")
    assert any("not-a-real-key" in e for e in exc_info.value.errors)


def test_terminal_state_without_outcome_rejected():
    reg = _load()
    feature = reg.workflows["feature"]
    states = dict(feature.states)
    states["done"] = replace(states["done"], outcome=None)
    reg.workflows["feature"] = replace(feature, states=states)

    with pytest.raises(CanonicalValidationError) as exc_info:
        validate(reg, "copilot")
    assert any("outcome" in e for e in exc_info.value.errors)


def test_unreachable_state_rejected():
    reg = _load()
    feature = reg.workflows["feature"]
    states = dict(feature.states)
    states["orphan"] = StateSpec(
        name="orphan", worker="coder", transitions=TransitionSpec(success="done"),
    )
    reg.workflows["feature"] = replace(feature, states=states)

    with pytest.raises(CanonicalValidationError) as exc_info:
        validate(reg, "copilot")
    assert any("orphan" in e and "unreachable" in e for e in exc_info.value.errors)


def test_capability_type_mismatch_rejected():
    reg = _load()
    # git.commit is type=action; putting it under runtime_context (expects context) should fail.
    reg.workers["pr-author"] = replace(reg.workers["pr-author"], runtime_context=("git.commit",))

    with pytest.raises(CanonicalValidationError) as exc_info:
        validate(reg, "copilot")
    assert any("git.commit" in e and "type" in e for e in exc_info.value.errors)


def test_unknown_capability_rejected():
    reg = _load()
    reg.workers["coder"] = replace(reg.workers["coder"], actions=("not.a.real.capability",))

    with pytest.raises(CanonicalValidationError) as exc_info:
        validate(reg, "copilot")
    assert any("not.a.real.capability" in e for e in exc_info.value.errors)


def test_unknown_model_tier_for_platform_rejected():
    reg = _load()
    reg.model_tiers["tiers"][2]["models"].pop("aider", None)

    with pytest.raises(CanonicalValidationError) as exc_info:
        validate(reg, "aider")
    assert any("tier 2" in e for e in exc_info.value.errors)
