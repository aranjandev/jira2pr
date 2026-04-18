# Shell Script Test Suite - Implementation Guide

## Overview

The following test suites have been created for the jira2pr shell scripts. They focus on:

1. **Argument validation** — Ensuring scripts properly handle command-line arguments
2. **Error handling** — Verifying error messages and exit codes
3. **Output formatting** — Testing JSON, heredoc, and file content handling
4. **Integration points** — Testing where scripts interact with external commands (git, curl, jq)

## Test Files Created

### 1. test_framework.sh
Core testing utilities including:
- **Assertions**: `assert_eq`, `assert_contains`, `assert_exit_code`, `assert_file_exists`, `assert_valid_json`
- **Mocking**: Mock external commands to isolate script logic
- **Helpers**: Temporary file creation, environment variable management

### 2. Individual Test Suites

| Script | Test File | Coverage |
|--------|-----------|----------|
| git_helper.sh | test_git_helper.sh | Branch creation, commits, status |
| fetch_jira.sh | test_fetch_jira.sh | Ticket key validation, JSON output parsing |
| pr_helper.sh | test_pr_helper.sh | Argument validation, file handling |
| apply_model_tiers.sh | test_apply_model_tiers.sh | Tier patching, YAML frontmatter |

### 3. run_all_tests.sh
Master test runner that:
- Discovers and runs all test files
- Aggregates results
- Provides formatted summary

## Running the Tests

```bash
# Run all tests
cd tests/
./run_all_tests.sh

# Run individual test suite
./test_git_helper.sh
./test_fetch_jira.sh
./test_pr_helper.sh
./test_apply_model_tiers.sh
```

## Key Features Tested

### Addressing the Reported Issues

The errors you mentioned:
1. **"I hit a shell heredoc glitch that didn't create the file"**
   - Tests verify: Large multi-line bodies, special characters, proper file creation
   - Best practice: Use file redirection instead of heredocs with variable expansion

2. **"jq error in parsing"**
   - Tests verify: Valid JSON output structure, null field handling, error responses
   - Best practice: Quote all jq variables, handle null fields gracefully

### test_git_helper.sh
Tests the git-operations skill:
- [x] Branch name formatting (lowercase, dashes)
- [x] Commit message handling
- [x] Error handling for invalid types
- [x] Status reporting
- [x] Multiple commits  
- [x] Special characters in messages

### test_fetch_jira.sh
Tests the read-jira-ticket skill:
- [x] Ticket key format validation
- [x] URL extraction from JIRA links
- [x] Environment variable requirements
- [x] JSON output validation
- [x] Null field handling
- [x] HTTP error responses

### test_pr_helper.sh
Tests the create-pull-request skill:
- [x] Argument validation (--title, --body, --body-file)
- [x] Large body handling (heredoc robustness)
- [x] Special characters in title/body
- [x] Flag support (--draft, --labels, --base, --undraft)
- [x] File validation

### test_apply_model_tiers.sh
Tests the apply_model_tiers script:
- [x] Tier comment parsing
- [x] Model field insertion
- [x] YAML frontmatter handling
- [x] Multiple file processing
- [x] Existing field replacement
- [x] Error handling

## Test Framework Quick Reference

### Using the Framework in Your Own Tests

```bash
#!/usr/bin/env bash
source test_framework.sh

test_init  # Setup environment

# Your test
test "description of what you're testing"
if [[ some_condition ]]; then
  pass
else
  fail "reason why it failed"
fi

test_cleanup
test_summary
```

### Common Assertions

```bash
# String assertions
assert_eq "$actual" "$expected"
assert_contains "$string" "$substring"

# File assertions  
assert_file_exists "/path/to/file"
assert_file_contains "/path/to/file" "text"

# JSON assertions
assert_valid_json "$json_string"
assert_json_property "$json" ".key" "value"

# Exit codes
assert_exit_code $? 0
```

## Fixing Reported Issues

### Issue 1: Heredoc Glitch with File Creation

**Problem:** `The PR body file was not created deterministically due to heredoc parsing issues`

**Solution:** Use direct file redirection instead of heredocs with variable expansion:

```bash
# ✓ GOOD - Safe file creation
cat > "$file" << 'EOF'
literal content without variables
EOF

# ✗ BAD - Can fail with special content
cat > "$file" << 'EOF'
content with $VARIABLES and special chars
EOF

# ✓ BETTER - Use printf or echo with redirection
printf '%s\n' "$content" > "$file"
echo "$content" > "$file"
```

**Tests Validating This:**
- `test_pr_helper.sh`:  Long PR body with newlines
- `test_pr_helper.sh`: Special characters and Unicode handling

### Issue 2: jq Parsing Errors

**Problem:** `jq returned errors when parsing JSON responses`

**Solution:** Properly escape variables and handle null fields:

```bash
# ✗ BAD - Unquoted variables can break JSON
jq -n --arg body $body_var '{body: $body}'

# ✓ GOOD - Properly quoted variables
jq -n --arg body "$body_var" '{body: $body}'

# ✓ HANDLE NULL - Default to empty string
jq '.description // ""'

# ✓ VALIDATE - Check JSON before parsing
if echo "$response" | jq . >/dev/null 2>&1; then
  # Process JSON
fi
```

**Tests Validating This:**
- `test_fetch_jira.sh`: JSON structure validation
- `test_fetch_jira.sh`: Null field handling
- `test_fetch_jira.sh`: HTTP error responses

## Integration with CI/CD

Add to `.github/workflows/test.yml`:

```yaml
name: Test Shell Scripts

on: [push, pull_request]

jobs:
  shell-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run shell script tests
        run: |
          chmod +x tests/run_all_tests.sh
          tests/run_all_tests.sh
```

## Troubleshooting

### Test Failures

1. **"No such file or directory"** — Check that scripts use proper path handling
2. **"jq: parse error"** — Verify JSON is properly escaped
3. **"git: command not found"** — Install git or mock the command

### Debug Mode

Add to any test file to see detailed output:

```bash
set -x  # Enable debug output
```

## Best Practices Summary

| Issue | Solution | Test Coverage |
|-------|----------|---------------|
| Heredoc failures | Use file redirection | pr_helper large body tests |
| jq parsing errors | Quote variables, handle null | fetch_jira JSON tests |
| Git branch issues | Validate branch names | git_helper format tests |
| Model tier patching | Use sed carefully | apply_model_tiers tests |
| Special characters | Proper escaping | All suites include edge cases |

## Next Steps

1. **Run the test suite** — `./run_all_tests.sh`
2. **Review failing tests** — Check the test output for specific issues
3. **Fix scripts** — Update scripts based on test results
4. **Add to CI/CD** — Integrate tests into your workflow
5. **Extend coverage** — Add tests for new edge cases as they arise

## References

- [POSIX Shell Test](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/test.html)
- [Bash Parameter Expansion](https://www.gnu.org/software/bash/manual/html_node/Parameter-Expansion.html)
- [jq Manual](https://stedolan.github.io/jq/)
- [Git Bash Scripting](https://git-scm.com/docs/gittutorial-2)
