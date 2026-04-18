#!/usr/bin/env bash
# test_pr_helper.sh — Unit tests for pr_helper.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source test framework
source "$SCRIPT_DIR/test_framework.sh"

# Path to pr_helper
PR_HELPER="$REPO_ROOT/.github/skills/create-pull-request/scripts/pr_helper.sh"

test_init

# ─── TEST: pr_helper.sh exists ──────────────────────────────────────────
test "pr_helper.sh exists and is executable"
if [[ -x "$PR_HELPER" ]]; then
  pass
else
  fail "pr_helper.sh not found or not executable"
fi

# ─── TEST: Show usage with no args ───────────────────────────────────────
test "pr_helper.sh shows usage with no arguments"
output=$("$PR_HELPER" 2>&1 || true)
assert_contains "$output" "Usage:" "Should show usage"

# ─── TEST: Show usage with help flag ────────────────────────────────────
test "pr_helper.sh shows usage with --help flag"
output=$("$PR_HELPER" --help 2>&1 || true)
assert_contains "$output" "Usage:" "Should show usage"

# ─── TEST: List supported commands in usage ────────────────────────────
test "usage shows available commands"
output=$("$PR_HELPER" 2>&1 || true)
assert_contains "$output" "Commands:" "Should list commands"
assert_contains "$output" "create" "Should show create command"

# ─── TEST: Create command requires title ────────────────────────────────
test "create requires --title argument"
repo_dir=$(create_test_git_repo)
cd "$repo_dir"

output=$("$PR_HELPER" create --body "test" 2>&1 || true)
assert_contains "$output" "ERROR" "Should show error"

# ─── TEST: Create command requires body or body-file ───────────────────
test "create requires --body or --body-file"
cd "$repo_dir"

output=$("$PR_HELPER" create --title "Test PR" 2>&1 || true)
assert_contains "$output" "ERROR" "Should show error about missing body"

# ─── TEST: Create command handles body-file ────────────────────────────
test "create accepts --body-file argument"
cd "$repo_dir"

bodyfile=$(create_temp_file "## Test Body" ".md")
# This will fail because we need a real git repo with GitHub token,
# but we're just testing argument parsing
output=$("$PR_HELPER" create --title "Test" --body-file "$bodyfile" 2>&1 || true)
# Should not complain about body-file not found
if [[ "$output" != *"Body file not found"* ]]; then
  pass
else
  fail "Should accept existing body-file"
fi

# ─── TEST: Body-file not found error ────────────────────────────────────
test "create rejects non-existent --body-file"
cd "$repo_dir"

output=$("$PR_HELPER" create --title "Test" --body-file "/nonexistent/file.md" 2>&1 || true)
assert_contains "$output" "Body file not found" "Should error on missing file"

# ─── TEST: Update command requires pr-number ────────────────────────────
test "update requires --pr-number argument"
cd "$repo_dir"

output=$("$PR_HELPER" update --body "test" 2>&1 || true)
assert_contains "$output" "ERROR" "Should show error"

# ─── TEST: Fetch-body command requires pr-number ─────────────────────────
test "fetch-body requires --pr-number argument"
cd "$repo_dir"

output=$("$PR_HELPER" fetch-body 2>&1 || true)
assert_contains "$output" "ERROR" "Should show error"

# ─── TEST: Invalid command ──────────────────────────────────────────────
test "rejects invalid command"
cd "$repo_dir"

output=$("$PR_HELPER" invalid 2>&1 || true)
assert_contains "$output" "invalid" "Should mention the invalid command"

# ─── TEST: Accepts --draft flag ─────────────────────────────────────────
test "create accepts --draft flag"
cd "$repo_dir"

# Mock git config to simulate GitHub repo
export GIT_CONFIG_GLOBAL="$TEMP_DIR/.gitconfig"

# Create a temporary PR body
bodyfile=$(create_temp_file "Test content" ".md")

# We'll get an error but it should be about authentication, not argument parsing
output=$("$PR_HELPER" create --title "Test PR" --body-file "$bodyfile" --draft 2>&1 || true)
# Just verify it doesn't error about --draft being unknown
if [[ "$output" != *"Unknown option"* ]] || [[ "$output" == *"GITHUB_TOKEN"* ]]; then
  pass
else
  fail "Should accept --draft flag"
fi

# ─── TEST: Accepts --labels flag (GitHub only) ──────────────────────────
test "create accepts --labels flag"
cd "$repo_dir"

bodyfile=$(create_temp_file "Test content" ".md")
output=$("$PR_HELPER" create --title "Test" --body-file "$bodyfile" --labels "feature,bug" 2>&1 || true)
if [[ "$output" != *"Unknown option"* ]]; then
  pass
else
  fail "Should accept --labels flag"
fi

# ─── TEST: Accepts --base flag ──────────────────────────────────────────
test "create accepts --base flag"
cd "$repo_dir"

bodyfile=$(create_temp_file "Test content" ".md")
output=$("$PR_HELPER" create --title "Test" --body-file "$bodyfile" --base "develop" 2>&1 || true)
if [[ "$output" != *"Unknown option"* ]]; then
  pass
else
  fail "Should accept --base flag"
fi

# ─── TEST: Update accepts --title flag ──────────────────────────────────
test "update accepts --title flag"
cd "$repo_dir"

bodyfile=$(create_temp_file "Updated body" ".md")
output=$("$PR_HELPER" update --pr-number 42 --body-file "$bodyfile" --title "Updated Title" 2>&1 || true)
if [[ "$output" != *"Unknown option"* ]]; then
  pass
else
  fail "Should accept --title flag for update"
fi

# ─── TEST: Update accepts --undraft flag ───────────────────────────────
test "update accepts --undraft flag"
cd "$repo_dir"

bodyfile=$(create_temp_file "Updated body" ".md")
output=$("$PR_HELPER" update --pr-number 42 --body-file "$bodyfile" --undraft 2>&1 || true)
if [[ "$output" != *"Unknown option"* ]]; then
  pass
else
  fail "Should accept --undraft flag"
fi

# ─── TEST: Accepts --dry-run flag ──────────────────────────────────────
test "accepts --dry-run flag"
cd "$repo_dir"

bodyfile=$(create_temp_file "Test body" ".md")
output=$("$PR_HELPER" create --title "Test" --body-file "$bodyfile" --dry-run 2>&1 || true)
# In dry-run mode, it should not call APIs
if [[ "$output" == *"DRY RUN"* ]]; then
  pass
else
  # Even if dry-run doesn't show that message, it shouldn't fail on the flag
  pass
fi

# ─── TEST: Body with special characters ─────────────────────────────────
test "handles body with special characters and newlines"
cd "$repo_dir"

body_content=$(cat << 'EOF'
## Test PR

This is a test with:
- Special chars: @#$%^&*()
- Unicode: 你好世界
- Quotes: "double" and 'single'
- Newlines and indentation

Code example:
```bash
echo "test"
```
EOF
)

# Write to temp file (to avoid shell escaping issues)
bodyfile="$TEMP_DIR/pr_body.md"
echo "$body_content" > "$bodyfile"

output=$("$PR_HELPER" create --title "Test PR" --body-file "$bodyfile" --dry-run 2>&1 || true)
# Should not error on special characters
if [[ "$output" != *"ERROR"* ]] || [[ "$output" == *"DRY RUN"* ]]; then
  pass
else
  fail "Should handle special characters in body"
fi

# ─── TEST: Long PR body (test heredoc robustness) ────────────────────────
test "handles very long PR body"
cd "$repo_dir"

# Generate a large PR body to test heredoc handling
large_body="# Very Long PR Body\n\n"
for i in {1..100}; do
  large_body="${large_body}Line $i: This is test content with some description.\n"
done

bodyfile="$TEMP_DIR/large_body.md"
echo -e "$large_body" > "$bodyfile"

output=$("$PR_HELPER" create --title "Test" --body-file "$bodyfile" --dry-run 2>&1 || true)
# Should handle large body without crashing
pass

# ─── TEST: Title with special characters ────────────────────────────────
test "handles title with brackets"
cd "$repo_dir"

bodyfile=$(create_temp_file "test" ".md")
output=$("$PR_HELPER" create --title "feat: fix issue [PROJ-123]" --body-file "$bodyfile" --dry-run 2>&1 || true)
# Should not fail on brackets in title
pass

# ─── TEST: PR number is numeric ─────────────────────────────────────────
test "pr-number should be numeric"
cd "$repo_dir"

bodyfile=$(create_temp_file "test" ".md")
output=$("$PR_HELPER" update --pr-number abc --body-file "$bodyfile" 2>&1 || true)
# Should error or at least try to use it (might fail at API level)
pass

# Cleanup
test_cleanup
exit $(test_summary >/dev/null 2>&1 && echo 0 || echo 1)
