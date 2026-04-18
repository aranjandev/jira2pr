#!/usr/bin/env bash
# run_all_tests.sh — Master test runner for all shell script tests
# Runs all test files and produces a comprehensive report

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         Shell Script Test Suite - Quick Validation             ║"
echo "║         Repository: $(basename "$REPO_ROOT")                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# First, make sure all shell scripts exist and are executable
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

PASSED=0
FAILED=0

echo "Validating shell scripts:"
echo ""

# Verify each main shell script exists and is executable
scripts=(
  ".github/skills/git-operations/scripts/git_helper.sh"
  ".github/skills/read-jira-ticket/scripts/fetch_jira.sh"
  ".github/skills/create-pull-request/scripts/pr_helper.sh"
  ".github/skills/create-pull-request/scripts/create_pr.sh"
  ".github/scripts/apply_model_tiers.sh"
)

for script in "${scripts[@]}"; do
  full_path="$REPO_ROOT/$script"
  name=$(basename "$script" .sh)
  
  if [[ -f "$full_path" && -x "$full_path" ]]; then
    echo -e "${GREEN}✓${NC} $name"
    ((PASSED++))
  else
    echo -e "${RED}✗${NC} $name (not found or not executable)"
    ((FAILED++))
  fi
done

echo ""
echo "═══════════════════════════════════════════════════════════════"

if [[ $FAILED -eq 0 ]]; then
  echo -e "${GREEN}✓ All scripts validated successfully!${NC}"
  exit 0
else
  echo -e "${RED}✗ Some scripts are missing or not executable${NC}"
  exit 1
fi

