#!/usr/bin/env bash
# test_simple.sh — Simplified shell script tests focusing on core functionality

set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

# ─── SIMPLE ASSERTION HELPERS ───────────────────────────────────────────────

assert_file_exists() {
  local file="$1"
  if [[ -f "$file" ]]; then
    ((TESTS_PASSED++))
    echo -e "${GREEN}✓${NC} $file exists"
    return 0
  else
    ((TESTS_FAILED++))
    echo -e "${RED}✗${NC} $file missing"
    return 1
  fi
}

assert_executable() {
  local file="$1"
  if [[ -x "$file" ]]; then
    ((TESTS_PASSED++))
    echo -e "${GREEN}✓${NC} $file is executable"
    return 0
  else
    ((TESTS_FAILED++))
    echo -e "${RED}✗${NC} $file not executable"
    return 1
  fi
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  if [[ "$haystack" == *"$needle"* ]]; then
    ((TESTS_PASSED++))
    echo -e "${GREEN}✓${NC} Output contains '$needle'"
    return 0
  else
    ((TESTS_FAILED++))
    echo -e "${RED}✗${NC} Output missing '$needle'"
    return 1
  fi
}

test_script() {
  local script_name="$1"
  local script_path="$2"
  
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo -e "${BLUE}Testing: $script_name${NC}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  # Test 1: File exists
  assert_file_exists "$script_path"
  
  # Test 2: Is executable
  assert_executable "$script_path"
  
  # Test 3: Shows usage/help
  output=$("$script_path" --help 2>&1 || "$script_path" 2>&1 || true)
  if [[ -n "$output" ]]; then
    ((TESTS_PASSED++))
    echo -e "${GREEN}✓${NC} Script responds to execution"
  else
    ((TESTS_FAILED++))
    echo -e "${RED}✗${NC} Script produces no output"
  fi
}

# ─── RUN TESTS ───────────────────────────────────────────────────────────────

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Shell Script Test Suite - Simplified                  ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Test all shell scripts
test_script "git_helper" "$REPO_ROOT/.github/skills/git-operations/scripts/git_helper.sh"
test_script "fetch_jira" "$REPO_ROOT/.github/skills/read-jira-ticket/scripts/fetch_jira.sh"
test_script "pr_helper" "$REPO_ROOT/.github/skills/create-pull-request/scripts/pr_helper.sh"
test_script "create_pr" "$REPO_ROOT/.github/skills/create-pull-request/scripts/create_pr.sh"
test_script "apply_model_tiers" "$REPO_ROOT/.github/scripts/apply_model_tiers.sh"

# ─── SUMMARY ────────────────────────────────────────────────────────────────

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    TEST SUMMARY                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [[ $TESTS_FAILED -eq 0 ]]; then
  echo -e "${GREEN}✓ All tests passed!${NC}"
  exit 0
else
  echo -e "${RED}✗ Some tests failed${NC}"
  exit 1
fi
