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

    - If there is only one ``` fence, removes it and everything below it.
    - If there are two or more ``` fences, keeps only the lines between the
      first two fences (excluding the fence lines themselves).
    """
    text = path.read_text(encoding="utf-8")
    lines = text.split('\n')
    
    # Find all line indices containing ```
    fence_indices = [i for i, line in enumerate(lines) if '```' in line]
    
    if len(fence_indices) == 1:
        # One fence: remove it and everything below it
        normalized_lines = lines[:fence_indices[0]]
    elif len(fence_indices) >= 2:
        # Two or more fences: keep content between the first two (excluding fence lines)
        normalized_lines = lines[fence_indices[0] + 1:fence_indices[1]]
    else:
        # No fences: keep as-is
        normalized_lines = lines
    
    # Join lines and ensure single trailing newline
    normalized = '\n'.join(normalized_lines).rstrip() + '\n'
    
    path.write_text(
        normalized,
        encoding="utf-8",
    )

def normalize_artifact(path: Path) -> None:
    if path.suffix in {".yaml", ".yml"}:
        normalize_yaml_file(path)