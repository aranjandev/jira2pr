"""FileWriter — encapsulates write-vs-check duality and manifest-based pruning.

Every path written via ``put``/``copy``/``copy_tree`` is recorded in a
manifest (``.jira2pr/.manifest.json`` under the target dir). On the next run,
paths present in the previous manifest but no longer emitted are pruned
(deleted) automatically — this is what keeps a regenerated target directory
free of stale files left over from an older agent/skill/prompt roster,
without ever touching files the compiler itself never wrote (runtime state
instances, archived state, the artifact registry, etc.).
"""

from __future__ import annotations

import difflib
import json
import shutil
import sys
from pathlib import Path

MANIFEST_REL_PATH = ".jira2pr/.manifest.json"


class FileWriter:
    """Writes or checks generated files against a target directory.

    In normal mode, ``put()`` writes files to disk.
    In check mode, ``put()`` compares content against existing files and
    records diffs without writing.

    Call ``finalize()`` once assembly is complete to prune stale files (write
    mode) or compute what would be pruned (check mode).
    """

    def __init__(self, target_dir: Path, check: bool = False) -> None:
        self._target = target_dir.resolve()
        self._check = check
        self._written: list[str] = []
        self._diffs: list[str] = []
        self._missing: list[str] = []
        self._removed: list[str] = []
        self._warnings: list[str] = []
        self._emitted: set[str] = set()
        self._manifest_path = self._target / MANIFEST_REL_PATH
        self._previous_manifest: set[str] = self._load_manifest()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def put(self, rel_path: str | Path, content: str) -> None:
        """Write a text file, or compare in check mode."""
        rel_str = str(rel_path)
        self._emitted.add(rel_str)
        dest = self._target / rel_path
        if self._check:
            self._check_file(dest, content, rel_str)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content)
            self._written.append(rel_str)

    def copy(self, src: Path, rel_path: str | Path) -> None:
        """Copy a single file from *src* to *target_dir/rel_path*."""
        rel_str = str(rel_path)
        self._emitted.add(rel_str)
        dest = self._target / rel_path
        if self._check:
            if dest.exists():
                existing = dest.read_text()
                expected = src.read_text()
                if existing != expected:
                    self._diffs.append(rel_str)
            else:
                self._missing.append(rel_str)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            self._written.append(rel_str)

    def copy_tree(self, src_dir: Path, rel_path: str | Path) -> None:
        """Recursively copy a directory from *src_dir* to *target_dir/rel_path*."""
        for src_file in sorted(src_dir.rglob("*")):
            if src_file.is_file() and "__pycache__" not in src_file.parts and src_file.suffix != ".pyc":
                file_rel = Path(rel_path) / src_file.relative_to(src_dir)
                self.copy(src_file, file_rel)

    def check_protected_dir(self, rel_path: str | Path) -> bool:
        """Return True if *rel_path* exists and contains files.

        Useful for adapters that want to warn before emitting into a
        directory that agents manage at runtime (e.g. archived state).
        Manifest-based pruning already guarantees the compiler never
        deletes files it did not itself write, so this is advisory only.
        """
        dir_path = self._target / rel_path
        if not dir_path.is_dir():
            return False
        return any(dir_path.iterdir())

    def add_warning(self, message: str) -> None:
        """Add a warning message to be displayed in the summary."""
        self._warnings.append(message)

    def finalize(self) -> None:
        """Prune stale files and persist the manifest. Call once, after assembly.

        In check mode this only computes what *would* be pruned (reflected in
        ``all_ok``/``summary()``); nothing is written to disk.
        """
        stale = sorted(self._previous_manifest - self._emitted)
        if self._check:
            self._removed = stale
            return
        for rel_str in stale:
            path = self._target / rel_str
            if path.exists():
                path.unlink()
                self._removed.append(rel_str)
        _prune_empty_dirs(self._target, stale)
        self._manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self._manifest_path.write_text(
            json.dumps({"files": sorted(self._emitted)}, indent=2) + "\n"
        )

    @property
    def all_ok(self) -> bool:
        """True if check mode found no differences, missing, or stale files."""
        return not self._diffs and not self._missing and not self._removed

    def summary(self) -> str:
        """Return a human-readable summary of what was done."""
        if self._check:
            if self.all_ok:
                return "All files are up to date."
            parts = []
            if self._diffs:
                parts.append(f"{len(self._diffs)} file(s) would change")
            if self._missing:
                parts.append(f"{len(self._missing)} file(s) missing")
            if self._removed:
                parts.append(f"{len(self._removed)} stale file(s) would be removed")
            return "Check failed: " + ", ".join(parts) + "."

        lines = [f"Wrote {len(self._written)} file(s) to {self._target}"]
        if self._removed:
            lines.append(f"Removed {len(self._removed)} stale file(s)")
        if self._warnings:
            lines.append("\nWarnings:")
            for warning in self._warnings:
                lines.append(f"  ⚠️  {warning}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_manifest(self) -> set[str]:
        if not self._manifest_path.exists():
            return set()
        try:
            data = json.loads(self._manifest_path.read_text())
        except (json.JSONDecodeError, OSError):
            return set()
        return set(data.get("files", []))

    def _check_file(self, dest: Path, content: str, label: str) -> None:
        if dest.exists():
            existing = dest.read_text()
            if existing != content:
                diff = difflib.unified_diff(
                    existing.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=label,
                    tofile=f"{label} (generated)",
                )
                sys.stdout.writelines(diff)
                self._diffs.append(label)
        else:
            print(f"MISSING: {label}", file=sys.stderr)
            self._missing.append(label)


def _prune_empty_dirs(root: Path, removed_rel_paths: list[str]) -> None:
    """Remove now-empty parent directories left behind by pruned files."""
    all_dirs: set[Path] = set()
    for rel in removed_rel_paths:
        cur = (root / rel).parent
        while cur != root and root in cur.parents:
            all_dirs.add(cur)
            cur = cur.parent
    for d in sorted(all_dirs, key=lambda p: len(p.parts), reverse=True):
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass

