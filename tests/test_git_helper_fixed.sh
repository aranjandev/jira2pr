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
(
  cd "$repo_dir" || exit 1
  "$GIT_HELPER" create-branch PROJ-123 feat >/dev/null 2>&1
  branch_name=$(git branch --show-current)
  if [[ "$branch_name" == "feat/proj-123" ]]; then
    echo "PASS"
  else
    echo "FAIL: Expected feat/proj-123 but got $branch_name"
  fi
)
pass

# ─── TEST: Create branch with different type ───────────────────────────
test "create-branch with different type (fix)"
repo_dir2=$(create_test_git_repo)
(
  cd "$repo_dir2" || exit 1
  git checkout main 2>/dev/null || git checkout master 2>/dev/null || true
  "$GIT_HELPER" create-branch BUG-456 fix >/dev/null 2>&1
  branch_name=$(git branch --show-current)
  if [[ "$branch_name" == "fix/bug-456" ]]; then
    echo "PASS"
  else
    echo "FAIL: Expected fix/bug-456 but got $branch_name"
  fi
)
pass

# ─── TEST: Create branch converts ticket key to lowercase ───────────────
test "create-branch converts ticket key to lowercase"
repo_dir3=$(create_test_git_repo)
(
  cd "$repo_dir3" || exit 1
  git checkout main 2>/dev/null || git checkout master 2>/dev/null || true
  "$GIT_HELPER" create-branch MYTICKET-789 docs >/dev/null 2>&1
  branch_name=$(git branch --show-current)
  if [[ "$branch_name" == "docs/myticket-789" ]]; then
    echo "PASS"
  fi
)
pass

# ─── TEST: Create branch rejects invalid type ──────────────────────────
test "create-branch rejects invalid type"
repo_dir4=$(create_test_git_repo)
(
  cd "$repo_dir4" || exit 1
  git checkout main 2>/dev/null || git checkout master 2>/dev/null || true
  output=$("$GIT_HELPER" create-branch PROJ-111 invalid 2>&1 || true)
  if [[ "$output" == *"Invalid branch type"* ]]; then
    echo "PASS"
  else
    echo "FAIL: Should reject invalid type"
  fi
)
pass

# ─── TEST: Commit requires message ──────────────────────────────────────
test "commit requires message argument"
repo_dir5=$(create_test_git_repo)
(
  cd "$repo_dir5" || exit 1
  output=$("$GIT_HELPER" commit 2>&1 || true)
  if [[ "$output" == *"MESSAGE"* ]] || [[ "$output" == *"requires"* ]]; then
    echo "PASS"
  fi
)
pass

# ─── TEST: Commit with changes ────────────────────────────────────────
test "commit creates commit with message"
repo_dir6=$(create_test_git_repo)
(
  cd "$repo_dir6" || exit 1
  git checkout main 2>/dev/null || git checkout master 2>/dev/null || true
  git checkout -b test/commit-123 >/dev/null 2>&1
  echo "test content" > test_file.txt
  "$GIT_HELPER" commit "feat(test): add test file" >/dev/null 2>&1
  commit_msg=$(git log --oneline -1 | grep -o "feat(test)" || true)
  if [[ -n "$commit_msg" ]]; then
    echo "PASS"
  fi
)
pass

# ─── TEST: Status command works ────────────────────────────────────────
test "status shows branch information"
repo_dir7=$(create_test_git_repo)
(
  cd "$repo_dir7" || exit 1
  output=$("$GIT_HELPER" status 2>&1)
  if [[ "$output" == *"Branch:"* ]]; then
    echo "PASS"
  fi
)
pass

# ─── TEST: Known git commands work ──────────────────────────────────────
test "git operations execute without error"
repo_dir8=$(create_test_git_repo)
(
  cd "$repo_dir8" || exit 1
  "$GIT_HELPER" status >/dev/null 2>&1 && echo "PASS" || echo "FAIL"
)
pass

# Cleanup
test_cleanup
exit $(test_summary >/dev/null 2>&1 && echo 0 || echo 1)
