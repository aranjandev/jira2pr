#!/usr/bin/env python3
"""Assemble platform-specific agent setups from canonical definitions.

Usage:
    python scripts/assemble.py --target-dir vscode-copilot --platform copilot
    python scripts/assemble.py --target-dir my-project     --platform claude
    python scripts/assemble.py --target-dir vscode-copilot --platform copilot --check

Options:
    --target-dir DIR    Output root directory (required).
    --platform NAME     Platform to assemble: copilot, claude (required).
    --canonical-dir DIR Path to canonical definitions (default: canonical/).
    --check             Dry-run: exit 1 if any generated file would change.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure the scripts/ directory is on sys.path so `assembler` package resolves.
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from assembler.platforms import PLATFORMS
from assembler.registry import CanonicalRegistry
from assembler.writer import FileWriter


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Assemble platform-specific agent setups from canonical definitions."
    )
    parser.add_argument(
        "--target-dir",
        required=True,
        help="Output root directory (e.g., vscode-copilot, my-project).",
    )
    parser.add_argument(
        "--platform",
        required=True,
        choices=list(PLATFORMS.keys()),
        help="Platform to assemble.",
    )
    parser.add_argument(
        "--canonical-dir",
        default=None,
        help="Path to canonical definitions (default: canonical/ relative to repo root).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Dry-run: exit 1 if any generated file would change.",
    )
    args = parser.parse_args()

    # Resolve paths relative to repo root (parent of scripts/).
    repo_root = _SCRIPTS_DIR.parent
    canonical_dir = Path(args.canonical_dir) if args.canonical_dir else repo_root / "canonical"
    target_dir = Path(args.target_dir)
    if not target_dir.is_absolute():
        target_dir = repo_root / target_dir

    registry = CanonicalRegistry.load(canonical_dir)
    writer = FileWriter(target_dir, check=args.check)
    assembler_cls = PLATFORMS[args.platform]
    assembler = assembler_cls()

    assembler.assemble(registry, writer)

    print(writer.summary())
    if args.check and not writer.all_ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
