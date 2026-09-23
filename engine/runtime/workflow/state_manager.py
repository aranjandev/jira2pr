"""State manager — the runtime engine is the ONLY writer of workflow state.

Workers may read state; they must never write it (see
`canonical/state/workflow-state.template.yaml`). Writes are atomic
(temp file + `os.replace`) so a crash mid-write can never corrupt the file
a resumed run reads.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml

from runtime.logging_config import get_logger

logger = get_logger("workflow.state_manager")

# Conservative JIRA-style key: one or more uppercase letters, then -<digits>.
TICKET_KEY_RE = re.compile(r"^[A-Z][A-Z0-9]*-[0-9]+$")


class InvalidTicketKeyError(ValueError):
    """Raised when a ticket key fails validation before it is used in a path."""


def validate_ticket_key(ticket_key: str) -> str:
    """Reject anything that isn't a well-formed ticket key before it touches a path.

    This is a path-traversal boundary: ticket keys come from user/CLI input
    and are joined directly into a filesystem path.
    """
    if not TICKET_KEY_RE.match(ticket_key):
        raise InvalidTicketKeyError(
            f"Invalid ticket key: {ticket_key!r} (expected e.g. 'PROJ-123')"
        )
    return ticket_key


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class WorkflowState:
    workflow: str
    work_item: str
    status: str = "active"  # active | completed | escalated | failed
    current_state: str = ""
    retry_counts: dict[str, int] = field(default_factory=dict)
    total_iterations: int = 0
    artifacts: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    escalations: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowState":
        return cls(
            workflow=data.get("workflow", ""),
            work_item=data.get("work_item", ""),
            status=data.get("status", "active"),
            current_state=data.get("current_state", ""),
            retry_counts=dict(data.get("retry_counts") or {}),
            total_iterations=int(data.get("total_iterations", 0)),
            artifacts=list(data.get("artifacts") or []),
            decisions=list(data.get("decisions") or []),
            escalations=list(data.get("escalations") or []),
            history=list(data.get("history") or []),
            metadata=dict(data.get("metadata") or {}),
        )

    def record_history(self, state: str, attempt: int, outcome: str, notes: str = "") -> None:
        entry = {"timestamp": _now(), "state": state, "attempt": attempt, "outcome": outcome, "notes": notes}
        self.history.append(entry)
        logger.debug(f"Recorded history entry: {state} (attempt {attempt}): {outcome}")

    def record_escalation(self, state: str, reason: str) -> None:
        entry = {"timestamp": _now(), "state": state, "reason": reason}
        self.escalations.append(entry)
        logger.warning(f"Recorded escalation at state {state}: {reason}")


class StateManager:
    """Reads/writes `<core_dir>/state/<TICKET-KEY>.yaml` atomically."""

    def __init__(self, core_dir: Path) -> None:
        self._state_dir = Path(core_dir) / "state"
        self._archive_dir = self._state_dir / "archive"
        logger.debug(f"StateManager initialized: state_dir={self._state_dir}, archive_dir={self._archive_dir}")

    def _path(self, ticket_key: str) -> Path:
        validate_ticket_key(ticket_key)
        return self._state_dir / f"{ticket_key}.yaml"

    def exists(self, ticket_key: str) -> bool:
        exists = self._path(ticket_key).exists()
        logger.debug(f"State exists for {ticket_key}: {exists}")
        return exists

    def create(self, ticket_key: str, workflow: str, initial_state: str) -> WorkflowState:
        if self.exists(ticket_key):
            logger.error(f"State already exists for {ticket_key}")
            raise FileExistsError(f"State already exists for {ticket_key}; use load()/resume instead.")
        logger.info(f"Creating new workflow state for {ticket_key}: workflow={workflow}, initial_state={initial_state}")
        state = WorkflowState(workflow=workflow, work_item=ticket_key, current_state=initial_state)
        self.save(ticket_key, state)
        logger.debug(f"State created and saved for {ticket_key}")
        return state

    def load(self, ticket_key: str) -> WorkflowState:
        path = self._path(ticket_key)
        if not path.exists():
            logger.error(f"No workflow state found for {ticket_key} at {path}")
            raise FileNotFoundError(f"No workflow state found for {ticket_key} at {path}")
        logger.info(f"Loading workflow state for {ticket_key} from {path}")
        data = yaml.safe_load(path.read_text()) or {}
        state = WorkflowState.from_dict(data)
        logger.debug(f"State loaded: workflow={state.workflow}, current_state={state.current_state}, total_iterations={state.total_iterations}")
        return state

    def save(self, ticket_key: str, state: WorkflowState) -> None:
        path = self._path(ticket_key)
        logger.debug(f"Saving workflow state for {ticket_key} to {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        content = yaml.safe_dump(state.to_dict(), sort_keys=False)
        fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(content)
            os.replace(tmp_path, path)
            logger.debug(f"State saved atomically for {ticket_key}")
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    def archive(self, ticket_key: str) -> Path:
        """Move a completed/escalated state file to state/archive/."""
        src = self._path(ticket_key)
        logger.info(f"Archiving workflow state for {ticket_key}")
        self._archive_dir.mkdir(parents=True, exist_ok=True)
        dest = self._archive_dir / src.name
        os.replace(src, dest)
        logger.debug(f"State archived from {src} to {dest}")
        return dest
