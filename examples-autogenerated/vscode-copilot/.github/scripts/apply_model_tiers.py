#!/usr/bin/env python3
# apply_model_tiers.py — Patches model: field in all .agent.md files based on <!-- tier: N --> comments.
# Reads tier-to-model mapping from model-tiers.json.
# Usage: python3 ./.github/scripts/apply_model_tiers.py

import json
import os
import re
import subprocess
import sys
from pathlib import Path


# ─── .env loader ─────────────────────────────────────────────────────────────

def load_env():
    """Load unset vars from .env at repo root (if present)."""
    try:
        repo_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
    except subprocess.CalledProcessError:
        return

    env_path = Path(repo_root) / ".env"
    if not env_path.is_file():
        return

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
                os.environ.setdefault(key, value)


# ─── YAML frontmatter helpers ────────────────────────────────────────────────

def patch_model_in_frontmatter(content: str, model: str) -> str:
    """
    Insert or replace the `model:` field in YAML frontmatter (between --- delimiters).
    Returns the modified content string.
    """
    lines = content.splitlines(keepends=True)

    # Find the first and second --- delimiters
    dash_positions = []
    for i, line in enumerate(lines):
        if line.strip() == "---":
            dash_positions.append(i)
            if len(dash_positions) == 2:
                break

    model_line = f'model: "{model}"\n'

    if len(dash_positions) >= 2:
        start, end = dash_positions[0], dash_positions[1]
        frontmatter = lines[start + 1 : end]

        # Check if model: already exists in frontmatter
        for i, line in enumerate(frontmatter):
            if re.match(r"^model:", line):
                frontmatter[i] = model_line
                lines[start + 1 : end] = frontmatter
                return "".join(lines)

        # Insert model: after the opening ---
        lines.insert(start + 1, model_line)
    else:
        # No frontmatter found — insert at top
        lines.insert(0, f"---\n{model_line}---\n")

    return "".join(lines)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    load_env()

    script_dir = Path(__file__).resolve().parent
    github_dir = script_dir.parent
    tiers_file = github_dir / "model-tiers.json"
    agents_dir = github_dir / "agents"

    if not tiers_file.is_file():
        print(f"ERROR: {tiers_file} not found", file=sys.stderr)
        sys.exit(1)

    if not agents_dir.is_dir():
        print(f"ERROR: {agents_dir} directory not found", file=sys.stderr)
        sys.exit(1)

    with open(tiers_file) as f:
        tiers_data = json.load(f)

    agent_files = sorted(agents_dir.glob("*.agent.md"))
    patched = 0
    skipped = 0

    for agent_file in agent_files:
        filename = agent_file.name
        content = agent_file.read_text()

        # Extract tier number from <!-- tier: N --> comment
        match = re.search(r"<!--\s*tier:\s*(\d+)\s*-->", content)
        if not match:
            print(f"SKIP: {filename} — no <!-- tier: N --> comment found")
            skipped += 1
            continue

        tier = match.group(1)

        # Look up model name from tiers JSON
        model = tiers_data.get("tiers", {}).get(tier, {}).get("model")
        if not model:
            print(f"WARN: {filename} — tier {tier} not found in {tiers_file.name}")
            skipped += 1
            continue

        new_content = patch_model_in_frontmatter(content, model)
        if new_content != content:
            agent_file.write_text(new_content)
            print(f"OK: {filename} — tier {tier} → {model}")
            patched += 1
        else:
            # Content unchanged means model line was already correct
            print(f"OK: {filename} — tier {tier} → {model} (already set)")
            patched += 1

    print()
    print(f"Done. Patched: {patched}, Skipped: {skipped}")


if __name__ == "__main__":
    main()
