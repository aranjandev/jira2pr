"""Keep a coder attempt inside the files it is allowed to edit.

A coder invocation is given one editable file (or, for fix passes, the plan's
files). Backends can still edit other files. This module records the working
tree before the invocation and, afterwards, reverts every change outside the
allowed set, so a rejected attempt leaves nothing behind.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from runtime.logging_config import get_logger

logger = get_logger("workflow.task_scope")


@dataclass(frozen=True)
class ScopeSnapshot:
    """Working-tree state of every file that was changed when capture ran."""

    repo_root: Path
    contents: dict[str, bytes | None]


def capture_scope(repo_root: Path) -> ScopeSnapshot:
    root = repo_root.resolve()
    contents = {rel: _read(root / rel) for rel in _changed_paths(root)}
    return ScopeSnapshot(repo_root=root, contents=contents)


def revert_out_of_scope(snapshot: ScopeSnapshot, allowed: set[Path]) -> list[str]:
    """Restore every file outside ``allowed`` to its pre-invocation state.

    Returns the repo-relative paths that were reverted. Files that were already
    dirty at capture time are restored to their captured bytes. Files that were
    clean are restored from git HEAD, or removed when git does not track them.
    """
    root = snapshot.repo_root
    allowed_rel = {_relative(root, path) for path in allowed}

    current = _changed_paths(root)
    candidates = (set(snapshot.contents) | current) - allowed_rel

    reverted: list[str] = []
    for rel in sorted(candidates):
        path = root / rel

        if rel in snapshot.contents:
            before = snapshot.contents[rel]
            if _read(path) == before:
                continue
            _restore_bytes(path, before)
        else:
            if rel not in current:
                continue
            _restore_from_head(root, rel, path)

        reverted.append(rel)
        logger.warning("Reverted out-of-scope change: %s", rel)

    return reverted


def _changed_paths(root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "-z", "--untracked-files=all"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        logger.warning(
            "git status failed in %s; out-of-scope edits cannot be checked: %s",
            root,
            result.stderr.strip() if result.stderr else "",
        )
        return set()

    entries = result.stdout.split("\0")
    paths: set[str] = set()
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        status, path = entry[:2], entry[3:]
        paths.add(path)
        # Renames and copies carry the original path as the next entry.
        if status[0] in ("R", "C") and index < len(entries):
            paths.add(entries[index])
            index += 1
    return paths


def _restore_from_head(root: Path, rel: str, path: Path) -> None:
    tracked = subprocess.run(
        ["git", "-C", str(root), "cat-file", "-e", f"HEAD:{rel}"],
        capture_output=True,
        check=False,
    )
    if tracked.returncode == 0:
        subprocess.run(
            ["git", "-C", str(root), "checkout", "HEAD", "--", rel],
            capture_output=True,
            check=True,
        )
    elif path.is_file():
        path.unlink()


def _restore_bytes(path: Path, before: bytes | None) -> None:
    if before is None:
        if path.is_file():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(before)


def _read(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def _relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()
