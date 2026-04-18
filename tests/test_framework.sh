#!/usr/bin/env bash
# test_framework.sh — Lightweight bash testing framework with mocking support
# Provides: assertions, test tracking, mock utilities, colored output

set -euo pipefail

# ─── COLORS ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ─── GLOBALS ──────────────────────────────────────────────────────────────────
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
CURRENT_TEST=""
MOCK_DIR=""
TEMP_DIR=""

# ─── LIFECYCLE ────────────────────────────────────────────────────────────────

# Initialize test environment before running tests
test_init() {
  MOCK_DIR="$(mktemp -d)"
  TEMP_DIR="$(mktemp -d)"
  export MOCK_DIR TEMP_DIR
  export PATH="${MOCK_DIR}:${PATH}"
}

# Cleanup after tests
test_cleanup() {
  if [[ -n "$MOCK_DIR" && -d "$MOCK_DIR" ]]; then
    rm -rf "$MOCK_DIR"
  fi
  if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
    rm -rf "$TEMP_DIR"
  fi
}

# Print test summary
test_summary() {
  echo ""
  echo "═══════════════════════════════════════════════════════════════"
  echo -e "Tests run: $TESTS_RUN"
  echo -e "${GREEN}Tests passed: $TESTS_PASSED${NC}"
  if [[ $TESTS_FAILED -gt 0 ]]; then
    echo -e "${RED}Tests failed: $TESTS_FAILED${NC}"
    return 1
  fi
  echo "═══════════════════════════════════════════════════════════════"
  return 0
}

# ─── TEST EXECUTION ──────────────────────────────────────────────────────────

# Begin a test
test() {
  CURRENT_TEST="$1"
  ((TESTS_RUN++))
  echo -e "\n${BLUE}▶ Test:${NC} $CURRENT_TEST"
}

# Pass current test
pass() {
  ((TESTS_PASSED++))
  echo -e "  ${GREEN}✓ Pass${NC}"
}

# Fail current test with message
fail() {
  local msg="${1:-Assertion failed}"
  ((TESTS_FAILED++))
  echo -e "  ${RED}✗ Fail${NC}: $msg"
}

# ─── ASSERTIONS ───────────────────────────────────────────────────────────────

# Assert string equality
assert_eq() {
  local actual="$1"
  local expected="$2"
  local msg="${3:-Expected '$expected' but got '$actual'}"
  
  if [[ "$actual" == "$expected" ]]; then
    pass
  else
    fail "$msg"
  fi
}

# Assert string inequality
assert_neq() {
  local actual="$1"
  local unexpected="$2"
  local msg="${3:-Should not equal '$unexpected' but got '$actual'}"
  
  if [[ "$actual" != "$unexpected" ]]; then
    pass
  else
    fail "$msg"
  fi
}

# Assert string contains substring
assert_contains() {
  local haystack="$1"
  local needle="$2"
  local msg="${3:-Expected to contain '$needle'}"
  
  if [[ "$haystack" == *"$needle"* ]]; then
    pass
  else
    fail "$msg"
  fi
}

# Assert exit code
assert_exit_code() {
  local actual=$1
  local expected=${2:-0}
  local msg="${3:-Expected exit code $expected but got $actual}"
  
  if [[ $actual -eq $expected ]]; then
    pass
  else
    fail "$msg"
  fi
}

# Assert file exists
assert_file_exists() {
  local filepath="$1"
  local msg="${2:-File should exist: $filepath}"
  
  if [[ -f "$filepath" ]]; then
    pass
  else
    fail "$msg"
  fi
}

# Assert file does not exist
assert_file_not_exists() {
  local filepath="$1"
  local msg="${2:-File should not exist: $filepath}"
  
  if [[ ! -f "$filepath" ]]; then
    pass
  else
    fail "$msg"
  fi
}

# Assert file contains text
assert_file_contains() {
  local filepath="$1"
  local needle="$2"
  local msg="${3:-File '$filepath' should contain '$needle'}"
  
  if [[ -f "$filepath" ]] && grep -q "$needle" "$filepath"; then
    pass
  else
    fail "$msg"
  fi
}

# Assert JSON is valid
assert_valid_json() {
  local json="$1"
  local msg="${2:-Invalid JSON}"
  
  if echo "$json" | jq . >/dev/null 2>&1; then
    pass
  else
    fail "$msg"
  fi
}

# Assert JSON has key with value
assert_json_property() {
  local json="$1"
  local key_path="$2"
  local expected_value="$3"
  local msg="${4:-JSON property '$key_path' should equal '$expected_value'}"
  
  local actual
  actual=$(echo "$json" | jq -r "$key_path" 2>/dev/null || echo "")
  
  if [[ "$actual" == "$expected_value" ]]; then
    pass
  else
    fail "$msg (got: $actual)"
  fi
}

# ─── MOCKING ──────────────────────────────────────────────────────────────────

# Create a mock command that echoes output and sets exit code
mock_command() {
  local cmd_name="$1"
  local output="$2"
  local exit_code="${3:-0}"
  local mock_script="$MOCK_DIR/$cmd_name"
  
  # Create a script that captures arguments
  cat > "$mock_script" << EOF
#!/usr/bin/env bash
# Mock of $cmd_name
echo "$output" >&1
exit $exit_code
EOF
  chmod +x "$mock_script"
}

# Create a mock command that captures arguments to a file
mock_command_capture() {
  local cmd_name="$1"
  local output="$2"
  local exit_code="${3:-0}"
  local capture_file="$MOCK_DIR/${cmd_name}.captured_args"
  local mock_script="$MOCK_DIR/$cmd_name"
  
  cat > "$mock_script" << EOF
#!/usr/bin/env bash
# Mock of $cmd_name (capturing arguments)
echo "\$@" >> "$capture_file"
echo "$output" >&1
exit $exit_code
EOF
  chmod +x "$mock_script"
}

# Get captured arguments from a mock (for verify)
get_mock_calls() {
  local cmd_name="$1"
  local capture_file="$MOCK_DIR/${cmd_name}.captured_args"
  
  if [[ -f "$capture_file" ]]; then
    cat "$capture_file"
  fi
}

# Assert mock was called with specific arguments
assert_mock_called_with() {
  local cmd_name="$1"
  shift
  local expected_args="$@"
  local captured="$(get_mock_calls "$cmd_name" || echo "")"
  
  if [[ "$captured" == *"$expected_args"* ]]; then
    pass
  else
    fail "Mock '$cmd_name' should be called with '$expected_args' but got '$captured'"
  fi
}

# ─── TEST HELPERS ────────────────────────────────────────────────────────────

# Create a temporary git repo for testing (requires git)
create_test_git_repo() {
  local repo_dir="${1:-$TEMP_DIR/test_repo_$$}"
  mkdir -p "$repo_dir"
  
  # Suppress output from git commands
  (cd "$repo_dir" && git init -q)
  (cd "$repo_dir" && git config user.email "test@example.com")
  (cd "$repo_dir" && git config user.name "Test User")
  
  # Create initial commit
  echo "# Test" > "$repo_dir/README.md"
  (cd "$repo_dir" && git add README.md && git commit -m "initial commit" -q)
  
  # Create origin remote (bare repo for testing)
  local bare_repo="$TEMP_DIR/test_repo_$$.git"
  mkdir -p "$bare_repo"
  git init --bare "$bare_repo" -q
  (cd "$repo_dir" && git remote add origin "$bare_repo")
  
  echo "$repo_dir"
}

# Create a temporary file with content
create_temp_file() {
  local content="$1"
  local suffix="${2:-.txt}"
  local filepath="$TEMP_DIR/tempfile_${RANDOM}${suffix}"
  
  echo "$content" > "$filepath"
  echo "$filepath"
}

# Load environment from .env file
load_env() {
  local env_file="${1:-.env}"
  
  if [[ -f "$env_file" ]]; then
    # shellcheck disable=SC1090
    source "$env_file"
  fi
}

# Set environment variable for test
set_test_env() {
  local key="$1"
  local value="$2"
  export "$key=$value"
}

# Clear environment variable
unset_test_env() {
  local key="$1"
  unset "$key" 2>/dev/null || true
}

export -f test pass fail
export -f assert_eq assert_neq assert_contains assert_exit_code
export -f assert_file_exists assert_file_not_exists assert_file_contains
export -f assert_valid_json assert_json_property
export -f mock_command mock_command_capture get_mock_calls assert_mock_called_with
export -f create_temp_file create_test_git_repo load_env set_test_env unset_test_env
