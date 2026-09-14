"""Tests for runtime.workflow.state_manager — atomic writes, ticket key
validation (path-traversal boundary), and archiving.
"""

import pytest

from runtime.workflow.state_manager import (
    InvalidTicketKeyError,
    StateManager,
    WorkflowState,
    validate_ticket_key,
)


def test_validate_ticket_key_accepts_well_formed():
    assert validate_ticket_key("PROJ-123") == "PROJ-123"


@pytest.mark.parametrize("bad", ["proj-123", "PROJ_123", "../../etc/passwd", "PROJ-", "-123", ""])
def test_validate_ticket_key_rejects_malformed(bad):
    with pytest.raises(InvalidTicketKeyError):
        validate_ticket_key(bad)


def test_create_then_load_round_trips(tmp_path):
    sm = StateManager(tmp_path)
    sm.create("PROJ-1", "feature", "jira-ingest")
    state = sm.load("PROJ-1")
    assert state.workflow == "feature"
    assert state.current_state == "jira-ingest"
    assert state.status == "active"


def test_create_twice_raises(tmp_path):
    sm = StateManager(tmp_path)
    sm.create("PROJ-1", "feature", "jira-ingest")
    with pytest.raises(FileExistsError):
        sm.create("PROJ-1", "feature", "jira-ingest")


def test_load_missing_raises(tmp_path):
    sm = StateManager(tmp_path)
    with pytest.raises(FileNotFoundError):
        sm.load("PROJ-1")


def test_save_leaves_no_tmp_file(tmp_path):
    sm = StateManager(tmp_path)
    state = sm.create("PROJ-1", "feature", "jira-ingest")
    state.current_state = "plan"
    sm.save("PROJ-1", state)
    assert list((tmp_path / "state").glob(".*.tmp")) == []


def test_archive_moves_file(tmp_path):
    sm = StateManager(tmp_path)
    sm.create("PROJ-1", "feature", "jira-ingest")
    dest = sm.archive("PROJ-1")
    assert dest.exists()
    assert not sm.exists("PROJ-1")


def test_record_history_and_escalation():
    state = WorkflowState(workflow="feature", work_item="PROJ-1")
    state.record_history("plan", 1, "success")
    state.record_escalation("plan", "conflicting requirements")
    assert state.history[0]["state"] == "plan"
    assert state.escalations[0]["reason"] == "conflicting requirements"


def test_ticket_key_path_traversal_rejected(tmp_path):
    sm = StateManager(tmp_path)
    with pytest.raises(InvalidTicketKeyError):
        sm.load("../../etc/passwd")
