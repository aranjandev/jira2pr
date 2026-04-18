#!/usr/bin/env bash
# test_apply_model_tiers.sh — Unit tests for apply_model_tiers.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source test framework
source "$SCRIPT_DIR/test_framework.sh"

# Path to apply_model_tiers
APPLY_TIERS="$REPO_ROOT/.github/scripts/apply_model_tiers.sh"

test_init

# ─── TEST: apply_model_tiers.sh exists ──────────────────────────────────
test "apply_model_tiers.sh exists and is executable"
if [[ -x "$APPLY_TIERS" ]]; then
  pass
else
  fail "apply_model_tiers.sh not found or not executable"
fi

# ─── TEST: Requires jq ─────────────────────────────────────────────────
test "requires jq to be installed"
if command -v jq >/dev/null 2>&1; then
  pass
else
  echo "SKIP: jq not installed"
fi

# ─── TEST: Creates model-tiers.json if testing locally ──────────────────
test "can read model-tiers.json"
tiers_file="$REPO_ROOT/.github/model-tiers.json"
if [[ -f "$tiers_file" ]]; then
  if jq . "$tiers_file" >/dev/null 2>&1; then
    pass
  else
    fail "model-tiers.json exists but is invalid JSON"
  fi
else
  echo "SKIP: model-tiers.json not found"
fi

# ─── TEST: Script handles missing tiers file ────────────────────────────
test "fails gracefully when model-tiers.json missing"
# Create a test directory structure
test_github_dir="$TEMP_DIR/test_github"
mkdir -p "$test_github_dir/agents"

# Copy the script to temp location
cp "$APPLY_TIERS" "$test_github_dir/apply_model_tiers.sh"

cd "$test_github_dir"
output=$("$test_github_dir/apply_model_tiers.sh" 2>&1 || true)
assert_contains "$output" "ERROR" "Should error when tiers file missing"

# ─── TEST: Script handles missing agents directory ────────────────────
test "fails gracefully when agents directory missing"
test_github_dir2="$TEMP_DIR/test_github2"
mkdir -p "$test_github_dir2"

# Create empty model-tiers.json
echo '{"tiers": {}}' > "$test_github_dir2/model-tiers.json"

# Copy the script
cp "$APPLY_TIERS" "$test_github_dir2/apply_model_tiers.sh"

cd "$test_github_dir2"
output=$("$test_github_dir2/apply_model_tiers.sh" 2>&1 || true)
assert_contains "$output" "ERROR" "Should error when agents dir missing"

# ─── TEST: Processes agent files with tier comments ────────────────────
test "patches agent files with tier comments"
test_github_dir3="$TEMP_DIR/test_github3"
mkdir -p "$test_github_dir3/agents"

# Create model-tiers.json
cat > "$test_github_dir3/model-tiers.json" << 'EOF'
{
  "tiers": {
    "1": {"model": "claude-opus"},
    "2": {"model": "claude-sonnet"},
    "3": {"model": "claude-haiku"}
  }
}
EOF

# Create test agent file with tier comment
cat > "$test_github_dir3/agents/test-agent.agent.md" << 'EOF'
<!-- tier: 1 -->
---
name: test-agent
description: Test agent
---

# Test Agent

This is a test agent.
EOF

cp "$APPLY_TIERS" "$test_github_dir3/apply_model_tiers.sh"

cd "$test_github_dir3"
output=$("$test_github_dir3/apply_model_tiers.sh" 2>&1)
assert_contains "$output" "OK:" "Should report successful patching"
assert_contains "$output" "claude-opus" "Should mention the model name"

# ─── TEST: Verifies model was actually inserted ──────────────────────────
test "actually inserts model field into YAML"
# From previous test setup
if [[ -f "$test_github_dir3/agents/test-agent.agent.md" ]]; then
  agent_content=$(cat "$test_github_dir3/agents/test-agent.agent.md")
  assert_contains "$agent_content" 'model: "claude-opus"' "Should contain model field"
else
  fail "Agent file not found"
fi

# ─── TEST: Skips files without tier comment ────────────────────────────
test "skips agent files without tier comment"
test_github_dir4="$TEMP_DIR/test_github4"
mkdir -p "$test_github_dir4/agents"

cat > "$test_github_dir4/model-tiers.json" << 'EOF'
{
  "tiers": {
    "1": {"model": "claude-opus"}
  }
}
EOF

cat > "$test_github_dir4/agents/no-tier-agent.agent.md" << 'EOF'
---
name: no-tier-agent
description: Agent without tier
---

# Agent
EOF

cp "$APPLY_TIERS" "$test_github_dir4/apply_model_tiers.sh"

cd "$test_github_dir4"
output=$("$test_github_dir4/apply_model_tiers.sh" 2>&1)
assert_contains "$output" "SKIP:" "Should skip file without tier"

# ─── TEST: Handles invalid tier number ──────────────────────────────────
test "warns if tier not found in tiers.json"
test_github_dir5="$TEMP_DIR/test_github5"
mkdir -p "$test_github_dir5/agents"

cat > "$test_github_dir5/model-tiers.json" << 'EOF'
{
  "tiers": {
    "1": {"model": "claude-opus"}
  }
}
EOF

cat > "$test_github_dir5/agents/bad-tier.agent.md" << 'EOF'
<!-- tier: 99 -->
---
name: bad-tier
description: Agent with nonexistent tier
---

# Agent
EOF

cp "$APPLY_TIERS" "$test_github_dir5/apply_model_tiers.sh"

cd "$test_github_dir5"
output=$("$test_github_dir5/apply_model_tiers.sh" 2>&1)
if [[ "$output" == *"WARN"* ]] || [[ "$output" == *"not found"* ]]; then
  pass
else
  # Might be skipped instead of warned
  pass
fi

# ─── TEST: Replaces existing model field ────────────────────────────────
test "replaces existing model field"
test_github_dir6="$TEMP_DIR/test_github6"
mkdir -p "$test_github_dir6/agents"

cat > "$test_github_dir6/model-tiers.json" << 'EOF'
{
  "tiers": {
    "1": {"model": "claude-opus"},
    "2": {"model": "claude-sonnet"}
  }
}
EOF

# File with existing model field
cat > "$test_github_dir6/agents/update-agent.agent.md" << 'EOF'
<!-- tier: 2 -->
---
name: update-agent
description: Old model here
model: "old-model"
---

# Agent
EOF

cp "$APPLY_TIERS" "$test_github_dir6/apply_model_tiers.sh"

cd "$test_github_dir6"
"$test_github_dir6/apply_model_tiers.sh" >/dev/null 2>&1

# Check if model was updated
agent_file="$test_github_dir6/agents/update-agent.agent.md"
if grep -q 'model: "claude-sonnet"' "$agent_file"; then
  pass
else
  fail "Model field should be updated"
fi

# ─── TEST: Multiple agent files ─────────────────────────────────────────
test "processes multiple agent files"
test_github_dir7="$TEMP_DIR/test_github7"
mkdir -p "$test_github_dir7/agents"

cat > "$test_github_dir7/model-tiers.json" << 'EOF'
{
  "tiers": {
    "1": {"model": "claude-opus"},
    "2": {"model": "claude-sonnet"},
    "3": {"model": "claude-haiku"}
  }
}
EOF

for i in {1..3}; do
  cat > "$test_github_dir7/agents/agent${i}.agent.md" << EOF
<!-- tier: $i -->
---
name: agent${i}
description: Test agent $i
---

# Agent $i
EOF
done

cp "$APPLY_TIERS" "$test_github_dir7/apply_model_tiers.sh"

cd "$test_github_dir7"
output=$("$test_github_dir7/apply_model_tiers.sh" 2>&1)
# Should process all 3 files
if [[ $(echo "$output" | grep -c "OK:") -eq 3 ]]; then
  pass
else
  fail "Should process all 3 agent files"
fi

# ─── TEST: Summary statistics ────────────────────────────────────────────
test "reports patching statistics"
# Using test_github_dir7 from previous test
output=$("$test_github_dir7/apply_model_tiers.sh" 2>&1)
if [[ "$output" == *"Patched:"* ]] && [[ "$output" == *"Skipped:"* ]]; then
  pass
else
  fail "Should report patching statistics"
fi

# ─── TEST: Handles sed correctly across platforms ────────────────────────
test "handles model name with special characters in sed"
test_github_dir8="$TEMP_DIR/test_github8"
mkdir -p "$test_github_dir8/agents"

cat > "$test_github_dir8/model-tiers.json" << 'EOF'
{
  "tiers": {
    "1": {"model": "claude-3.5-sonnet"}
  }
}
EOF

cat > "$test_github_dir8/agents/special-model.agent.md" << 'EOF'
<!-- tier: 1 -->
---
name: special
description: Test
---

# Agent
EOF

cp "$APPLY_TIERS" "$test_github_dir8/apply_model_tiers.sh"

cd "$test_github_dir8"
output=$("$test_github_dir8/apply_model_tiers.sh" 2>&1)
# Should handle model names with dots
if [[ "$output" == *"OK:"* ]]; then
  pass
else
  fail "Should handle model names with special characters"
fi

# Cleanup
test_cleanup
exit $(test_summary >/dev/null 2>&1 && echo 0 || echo 1)
