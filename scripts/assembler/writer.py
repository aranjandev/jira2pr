"""FileWriter — encapsulates write-vs-check duality for all assembly output."""

from __future__ import annotations

import difflib
import shutil
import sys
from pathlib import Path


class FileWriter:
    """Writes or checks generated files against a target directory.

    In normal mode, ``put()`` writes files to disk.
    In check mode, ``put()`` compares content against existing files and
    records diffs without writing.
    """

    def __init__(self, target_dir: Path, check: bool = False) -> None:
        self._target = target_dir.resolve()
        self._check = check
        self._written: list[str] = []
        self._diffs: list[str] = []
        self._missing: list[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def put(self, rel_path: str | Path, content: str) -> None:
        """Write a text file, or compare in check mode."""
        dest = self._target / rel_path
        if self._check:
            self._check_file(dest, content, str(rel_path))
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content)
            self._written.append(str(rel_path))

    def copy(self, src: Path, rel_path: str | Path) -> None:
        """Copy a single file from *src* to *target_dir/rel_path*."""
        dest = self._target / rel_path
        if self._check:
            if dest.exists():
                existing = dest.read_text()
                expected = src.read_text()
                if existing != expected:
                    self._diffs.append(str(rel_path))
            else:
                self._missing.append(str(rel_path))
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            self._written.append(str(rel_path))

    def copy_tree(self, src_dir: Path, rel_path: str | Path) -> None:
        """Recursively copy a directory from *src_dir* to *target_dir/rel_path*."""
        for src_file in sorted(src_dir.rglob("*")):
            if src_file.is_file():
                file_rel = Path(rel_path) / src_file.relative_to(src_dir)
                self.copy(src_file, file_rel)

    @property
    def all_ok(self) -> bool:
        """True if check mode found no differences."""
        return not self._diffs and not self._missing

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
            return "Check failed: " + ", ".join(parts) + "."
        return f"Wrote {len(self._written)} file(s) to {self._target}"

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

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
