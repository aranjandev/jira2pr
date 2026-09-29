"""Safe normalization of generated workflow artifacts."""

from __future__ import annotations

import re
from pathlib import Path

_FENCED_DOCUMENT = re.compile(
    r"^\s*```(?:yaml|yml)?\s*\n(.*?)\n```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def normalize_yaml_file(path: Path) -> None:
    """Remove harmless Markdown wrapping from a generated YAML artifact.

    Only strips a single fence when it wraps the entire document.
    Embedded fenced blocks are left untouched.
    """
    text = path.read_text(encoding="utf-8")

    match = _FENCED_DOCUMENT.match(text)

    if match:
        normalized = match.group(1).rstrip() + "\n"
        path.write_text(
            normalized,
            encoding="utf-8",
        )

def normalize_artifact(path: Path) -> None:
    if path.suffix in {".yaml", ".yml"}:
        normalize_yaml_file(path)