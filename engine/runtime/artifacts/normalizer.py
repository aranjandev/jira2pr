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

    Removes outer fenced blocks when they wrap the entire document,
    and removes any remaining ``` markers from anywhere in the content.
    """
    text = path.read_text(encoding="utf-8")

    match = _FENCED_DOCUMENT.match(text)

    if match:
        normalized = match.group(1)
    else:
        normalized = text
    
    # Remove all ``` occurrences from anywhere in the content
    normalized = normalized.replace("```", "").rstrip() + "\n"
    
    path.write_text(
        normalized,
        encoding="utf-8",
    )

def normalize_artifact(path: Path) -> None:
    if path.suffix in {".yaml", ".yml"}:
        normalize_yaml_file(path)