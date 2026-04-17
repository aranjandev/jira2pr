#!/usr/bin/env bash
# apply_model_tiers.sh — Patches model: field in all .agent.md files based on <!-- tier: N --> comments.
# Reads tier-to-model mapping from model-tiers.json.
# Usage: ./.github/scripts/apply_model_tiers.sh
# Requirements: jq, sed

set -euo pipefail

# Load unset vars from .env at repo root (if present)
_repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -n "$_repo_root" && -f "$_repo_root/.env" ]]; then
  while IFS='=' read -r _k _v; do
    [[ -z "$_k" || "$_k" =~ ^[[:space:]]*# ]] && continue
    if [[ -z "${!_k+x}" ]]; then
      _v="${_v#[\"']}" ; _v="${_v%[\"']}"
      export "${_k}=${_v}"
    fi
  done < <(grep -E '^[^#].*=' "$_repo_root/.env" 2>/dev/null || true)
fi
unset _repo_root _k _v 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GITHUB_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TIERS_FILE="$GITHUB_DIR/model-tiers.json"
AGENTS_DIR="$GITHUB_DIR/agents"

if [[ ! -f "$TIERS_FILE" ]]; then
  echo "ERROR: $TIERS_FILE not found" >&2
  exit 1
fi

if ! command -v jq &>/dev/null; then
  echo "ERROR: jq is required but not installed" >&2
  exit 1
fi

if [[ ! -d "$AGENTS_DIR" ]]; then
  echo "ERROR: $AGENTS_DIR directory not found" >&2
  exit 1
fi

patched=0
skipped=0

for agent_file in "$AGENTS_DIR"/*.agent.md; do
  [[ -f "$agent_file" ]] || continue
  filename="$(basename "$agent_file")"

  # Extract tier number from <!-- tier: N --> comment
  tier=$(grep -oE '<!--\s*tier:\s*[0-9]+\s*-->' "$agent_file" | grep -oE '[0-9]+' | head -1)

  if [[ -z "$tier" ]]; then
    echo "SKIP: $filename — no <!-- tier: N --> comment found"
    ((skipped++))
    continue
  fi

  # Look up model name from tiers JSON
  model=$(jq -r --arg t "$tier" '.tiers[$t].model // empty' "$TIERS_FILE")

  if [[ -z "$model" ]]; then
    echo "WARN: $filename — tier $tier not found in $TIERS_FILE"
    ((skipped++))
    continue
  fi

  # Check if model: line already exists in YAML frontmatter (between --- delimiters)
  if grep -qE '^model:' "$agent_file"; then
    # Replace existing model: line
    sed -i '' "s|^model:.*|model: \"$model\"|" "$agent_file"
  else
    # Insert model: line after the first --- line (start of frontmatter)
    sed -i '' "0,/^---$/{ /^---$/a\\
model: \"$model\"
}" "$agent_file"
  fi

  echo "OK: $filename — tier $tier → $model"
  ((patched++))
done

echo ""
echo "Done. Patched: $patched, Skipped: $skipped"
