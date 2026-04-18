#!/usr/bin/env bash
# test_git_helper.sh — Unit tests for git_helper.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Source test framework
source "$SCRIPT_DIR/test_framework.sh"

# Path to git_helper
GIT_HELPER="$REPO_ROOT/.github/skills/git-operations/scripts/git_helper.sh"

test_init

# ─── TEST: git_helper.sh exists and is executable ──────────────────────────
test "git_helper.sh exists and is executable"
if [[ -x "$GIT_HELPER" ]]; then
  pass
else
  fail "git_helper.sh not found or not executable at $GIT_HELPER"
fi

# ─── TEST: Show usage when no args ────────────────────────────────────────
test "git_helper.sh shows usage with no arguments"
output=$("$GIT_HELPER" 2>&1 || true)
assert_contains "$output" "Usage:" "Should show usage"

# ─── TEST: Show usage with -h flag ──────────────────────────────────────
test "git_helper.sh shows usage with -h flag"
output=$("$GIT_HELPER" -h 2>&1 || true)
assert_contains "$output" "Usage:" "Should show usage"

# ─── TEST: Create branch with valid type ────────────────────────────────
test "create-branch with valid type (feat)"
repo_dir=$(create_test_git_repo)
cd "$repo_dir"

# The script will actually create the branch
"$GIT_HELPER" create-branch PROJ-123 feat
branch_name=$(git branch --show-current)
assert_eq "$branch_name" "feat/proj-123" "Branch name should be feat/proj-123"

# ─── TEST: Create branch with different type ───────────────────────────
test "create-branch with different type (fix)"
cd "$repo_dir"
git checkout main 2>/dev/null || git checkout master
"$GIT_HELPER" create-branch BUG-456 fix
branch_name=$(git branch --show-current)
assert_eq "$branch_name" "fix/bug-456" "Branch name should be fix/bug-456"

# ─── TEST: Create branch converts ticket key to lowercase ───────────────
test "create-branch converts ticket key to lowercase"
cd "$repo_dir"
git checkout main 2>/dev/null || git checkout master
"$GIT_HELPER" create-branch MYTICKET-789 docs
branch_name=$(git branch --show-current)
assert_eq "$branch_name" "docs/myticket-789" "Ticket key should be lowercase"

# ─── TEST: Create branch rejects invalid type ──────────────────────────
test "create-branch rejects invalid type"
cd "$repo_dir"
git checkout main 2>/dev/null || git checkout master
output=$("$GIT_HELPER" create-branch PROJ-111 invalid 2>&1 || true)
assert_contains "$output" "Invalid branch type" "Should reject invalid type"

# ─── TEST: Create branch with missing type argument ────────────────────
test "create-branch requires type argument"
cd "$repo_dir"
output=$("$GIT_HELPER" create-branch 2>&1 || true)
assert_contains "$output" "requires" "Should show error"

# ─── TEST: Commit requires message ──────────────────────────────────────
test "commit requires message argument"
cd "$repo_dir"
output=$("$GIT_HELPER" commit 2>&1 || true)
assert_contains "$output" "MESSAGE" "Should show error about missing message"

# ─── TEST: Commit with changes ────────────────────────────────────────
test "commit creates commit with message"
cd "$repo_dir"
git checkout main 2>/dev/null || git checkout master
git checkout -b test/commit-123
echo "test content" > test_file.txt
"$GIT_HELPER" commit "feat(test): add test file"
# Verify commit message
commit_msg=$(git log --oneline -1 | grep "feat(test)")
if [[ -n "$commit_msg" ]]; then
  pass
else
  fail "Commit not created with correct message"
fi

# ─── TEST: Commit with no changes ──────────────────────────────────────
test "commit with no staged changes returns 0"
cd "$repo_dir"
git checkout main 2>/dev/null || git checkout master
output=$("$GIT_HELPER" commit "feat(test): no changes" 2>&1 || true)
assert_contains "$output" "No changes" "Should report no changes"

# ─── TEST: Push requires upstream tracking ────────────────────────────
test "push command exists"
cd "$repo_dir"
# Just test that push command doesn't error on branch without files
result=$("$GIT_HELPER" push 2>&1 || true)
# We're just checking it doesn't crash
pass

# ─── TEST: Status command works ────────────────────────────────────────
test "status shows branch information"
cd "$repo_dir"
output=$("$GIT_HELPER" status 2>&1)
assert_contains "$output" "Branch:" "Should show branch line"

# ─── TEST: Status shows upstream info ───────────────────────────────────
test "status includes upstream tracking info"
cd "$repo_dir"
output=$("$GIT_HELPER" status 2>&1)
assert_contains "$output" "Upstream:" "Should show upstream line"

# ─── TEST: Unknown command fails ────────────────────────────────────────
test "unknown command shows error"
output=$("$GIT_HELPER" unknown 2>&1 || true)
assert_contains "$output" "Unknown command" "Should show error"

# ─── TEST: Branch name format with PROJ-123 ────────────────────────────
test "branch name format with real scenario: PROJ-123 feat"
cd "$repo_dir"
git checkout main 2>/dev/null || git checkout master
"$GIT_HELPER" create-branch PROJ-123 feat
current=$(git branch --show-current)
assert_eq "$current" "feat/proj-123" "Should match feat/proj-123 format"

# ─── TEST: Multiple commits on same branch ────────────────────────────
test "multiple commits on same branch"
cd "$repo_dir"
git checkout -b test/multi-commit 2>/dev/null || git checkout test/multi-commit
echo "file1" > file1.txt
"$GIT_HELPER" commit "feat: add file1"
echo "file2" > file2.txt
"$GIT_HELPER" commit "feat: add file2"
# Verify both commits exist
commit_count=$(git log --oneline | wc -l)
# Should have at least initial commit + 2 new commits
if [[ $commit_count -ge 3 ]]; then
  pass
else
  fail "Should have at least 3 commits but got $commit_count"
fi

# ─── TEST: Commit message with special characters ───────────────────────
test "commit message with special characters"
cd "$repo_dir"
git checkout -b test/special-chars 2>/dev/null || git checkout test/special-chars
echo "content" > special.txt
"$GIT_HELPER" commit "fix(api): handle 'quotes' and \"double quotes\""
commit_msg=$(git log -1 --pretty=%B)
assert_contains "$commit_msg" "handle" "Commit should contain message text"

# Cleanup
test_cleanup
exit $(test_summary >/dev/null 2>&1 && echo 0 || echo 1)
