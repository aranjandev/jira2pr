# Shell Script Test Suite

Comprehensive unit tests for all shell scripts in the jira2pr repository.

## Overview

This test suite provides:

- **Test Framework** (`test_framework.sh`) — Lightweight bash testing utilities with mocking support
- **Individual Test Suites** — Dedicated tests for each shell script module:
  - `test_git_helper.sh` — Tests for git branch/commit/push operations
  - `test_fetch_jira.sh` — Tests for JIRA ticket fetching and JSON parsing
  - `test_pr_helper.sh` — Tests for PR creation/update with argument validation
  - `test_apply_model_tiers.sh` — Tests for model tier patching

## Quick Start

### Run all tests:

```bash
cd tests/
./run_all_tests.sh
```

### Run individual test suites:

```bash
./test_git_helper.sh
./test_fetch_jira.sh
./test_pr_helper.sh
./test_apply_model_tiers.sh
```

## Requirements

- **Bash 4.0+** (for associative arrays and advanced syntax)
- **git** — for repository operations
- **jq** — for JSON parsing (recommended)
- **curl** — for HTTP operations (mocked in tests)

## Test Framework Features

### Assertions

The framework provides these assertion helpers:

```bash
# String comparisons
assert_eq "$actual" "$expected" "Message"
assert_neq "$actual" "$unexpected" "Message"
assert_contains "$string" "$substring" "Message"

# Exit codes
assert_exit_code $? 0 "Command should succeed"

# File operations
assert_file_exists "/path/to/file"
assert_file_not_exists "/path/to/file"
assert_file_contains "/path/to/file" "expected_text"

# JSON validation
assert_valid_json "$json_string"
assert_json_property "$json_string" '.key.nested' "expected_value"
```

### Mocking

Mock external commands to isolate tests:

```bash
# Simple mock
mock_command "curl" "mock output" 0

# Mock that captures arguments
mock_command_capture "git" "OK" 0
get_mock_calls "git"  # Retrieve captured arguments
assert_mock_called_with "git" "clone" "some_repo"
```

### Test Helpers

```bash
# Create temporary git repo for testing
repo_dir=$(create_test_git_repo)
cd "$repo_dir"

# Create temporary files
file_path=$(create_temp_file "content" ".txt")

# Environment variable management
set_test_env "MY_VAR" "value"
unset_test_env "MY_VAR"

# Load .env files
load_env ".env"
```

## Test Organization

Each test suite follows this pattern:

```bash
#!/usr/bin/env bash
source test_framework.sh

test_init  # Setup test environment

# Individual tests
test "description of what this tests"
if [[ condition ]]; then
  pass
else
  fail "reason for failure"
fi

test "another test"
# ... assertions ...

test_cleanup  # Cleanup temporary files
exit $(test_summary >/dev/null 2>&1 && echo 0 || echo 1)
```

## Addressing Common Test Issues

### Issue: "I hit a shell heredoc glitch that didn't create the file"

**Root Cause:** Heredocs with variable expansion can fail if not properly quoted and flushed.

**Tests:** The test suite includes cases for:
- Large PR bodies with newlines and special characters
- Files with spaces in paths
- Bodies with special characters (@#$%^&*)
- Long multi-line content

**Best Practices Validated:**
```bash
# ✓ Use single-quoted heredoc for literal content
cat > "$file" << 'EOF'
literal $VAR content
EOF

# ✓ Redirect to/from files directly instead of heredocs with substitution
echo "content" > "$file"

# ✓ Use printf for safer content generation
printf '%s\n' "$content" > "$file"
```

### Issue: "jq error in parsing"

**Root Cause:** Unescaped JSON strings, invalid JSON structure, or missing error handling.

**Tests:** The test suite includes:
- Valid JSON output structure validation
- Null field handling (empty descriptions, missing assignees)
- Complex nested structures (subtasks, linked issues)
- Error response handling (HTTP 404 on missing tickets)

**Best Practices Validated:**
```bash
# ✓ Properly quote jq variables
jq -n --arg title "$title" --arg body "$body" '{title: $title, body: $body}'

# ✓ Handle null/empty fields
jq '.description // ""'  # Use empty string as fallback

# ✓ Validate JSON before parsing
if echo "$response" | jq . >/dev/null 2>&1; then
  # Process valid JSON
fi

# ✓ Check HTTP errors before parsing
if [[ $http_code -ne 200 ]]; then
  echo "API error" >&2
  exit 1
fi
```

## Test Coverage

### git_helper.sh
- [x] Branch creation with various types (feat, fix, docs, etc.)
- [x] Branch name lowercasing and formatting
- [x] Commit with message formatting
- [x] Commit with special characters
- [x] Multiple commits on same branch
- [x] Status reporting
- [x] Push operations
- [x] Error handling for invalid inputs

### fetch_jira.sh
- [x] Ticket key format validation
- [x] URL extraction from JIRA links
- [x] Environment variable requirements
- [x] JSON output structure validation
- [x] Handling null/empty fields
- [x] HTTP error responses
- [x] Base URL configuration

### pr_helper.sh
- [x] Command argument validation
- [x] --body and --body-file handling
- [x] Large body content with newlines
- [x] Special characters in title and body
- [x] Flag acceptance (--draft, --labels, --base, --undraft, --dry-run)
- [x] Error reporting

### apply_model_tiers.sh
- [x] Tier comment parsing
- [x] Model lookup from JSON
- [x] YAML frontmatter patching
- [x] Multiple agent files
- [x] Existing model field replacement
- [x] Invalid tier handling
- [x] Statistics reporting

## Integration with CI/CD

To integrate these tests into GitHub Actions or other CI systems:

```yaml
name: Test Shell Scripts

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run shell script tests
        run: |
          tests/run_all_tests.sh
```

## Debugging Failed Tests

### Enable verbose output

Edit the test file and add `set -x` after `set -euo pipefail`:

```bash
set -euo pipefail
set -x  # Enable debug output
```

### Inspect temporary directories

Modify test_cleanup() to preserve temp files:

```bash
test_cleanup() {
  echo "Temp directory: $TEMP_DIR"
  # Don't delete yet — allows manual inspection
  # rm -rf "$TEMP_DIR"
}
```

### Run individual test

```bash
cd tests/
source test_framework.sh
test_init

# Run one specific test section from a suite
test "description of what this tests"
# ... test code ...

test_cleanup
```

## Contributing New Tests

When adding tests for new shell scripts:

1. Create `test_new_script.sh` in the tests/ directory
2. Source the test framework: `source "$SCRIPT_DIR/test_framework.sh"`
3. Call `test_init` at the start and `test_cleanup` at the end
4. Use the assertion helpers from the framework
5. Add the test file to this README's coverage section
6. Update `run_all_tests.sh` if needed (it auto-discovers tests)

## Known Limitations

- Tests are isolated and do not test inter-script integrations (e.g., pr_helper calling git_helper)
- Mocking does not fully simulate subprocess behavior (e.g., signal handling)
- Some tests are platform-specific (sed syntax differs between BSD/GNU sed on macOS vs Linux)

## References

- [POSIX Shell Command Language](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html)
- [Bash Manual](https://www.gnu.org/software/bash/manual/)
- [Google Shell Style Guide](https://google.github.io/styleguide/shellstyle.html)
- [jq Manual](https://stedolan.github.io/jq/manual/)
