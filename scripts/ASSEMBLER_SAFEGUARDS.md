# Assemble.py Safeguards Against Trampling Protected Directories

## Overview

The `assemble.py` script now includes safeguards to prevent overwriting existing agent-managed files in `.github/state/archive/` and `.github/artifacts/` directories. When these directories contain files, assembly is skipped with clear warnings to the user.

## Protected Directories

### 1. `.github/state/archive/`
- **Purpose**: Contains archived workflow state files from completed workflows
- **File pattern**: `*.md` files (e.g., `PROJ-123.md`)
- **Management**: Agent-managed (created by `pr-author` skill during workflow completion)
- **Protection**: If this directory exists and contains files, state assembly is skipped

### 2. `.github/artifacts/`
- **Purpose**: Contains the `REGISTRY.md` file that accumulates completed workflow entries
- **File pattern**: `REGISTRY.md` (append-only artifact registry)
- **Management**: Agent-managed (updated by `register-artifact` skill)
- **Protection**: If this directory exists and contains files, artifacts assembly is skipped

## How It Works

### Detection Mechanism
```python
# FileWriter.check_protected_dir() method
def check_protected_dir(self, rel_path: str | Path) -> bool:
    """Check if a directory exists and has files.
    Return True if it exists and is not empty."""
    dir_path = self._target / rel_path
    if not dir_path.is_dir():
        return False
    return any(dir_path.iterdir())
```

### Assembly Flow
When `assemble.py` runs with the `copilot` platform:

1. **State Assembly** (`_assemble_state`):
   - Checks if `.github/state/archive/` exists and has files
   - If yes: Issues warning and skips state assembly
   - If no: Assembles state templates (`SCHEMA.md`, `workflow-state.tpl.md`)

2. **Artifacts Assembly** (`_assemble_artifacts`):
   - Checks if `.github/artifacts/` exists and has files
   - If yes: Issues warning and skips artifacts assembly
   - If no: Assembles artifacts schema (`SCHEMA.md`)

### Warning Output
When protected directories are detected, the summary includes clear warnings:

```
Wrote 34 file(s) to .github/

Warnings:
  ⚠️  .github/state/archive/ is not empty. Skipping state assembly to protect archived workflow state files.
  ⚠️  .github/artifacts/REGISTRY.md is agent-managed. Skipping artifacts assembly to protect accumulated workflow registry.
```

## Examples

### Example 1: Fresh Repository Setup
```bash
$ python3 scripts/assemble.py --target-dir my-project --platform copilot
Wrote 37 file(s) to my-project
```
✅ All files assembled normally. Protected directories don't exist yet.

### Example 2: Subsequent Assembly (Protected Dirs Exist)
```bash
$ python3 scripts/assemble.py --target-dir my-project --platform copilot
Wrote 34 file(s) to my-project

Warnings:
  ⚠️  .github/state/archive/ is not empty. Skipping state assembly to protect archived workflow state files.
  ⚠️  .github/artifacts/REGISTRY.md is agent-managed. Skipping artifacts assembly to protect accumulated workflow registry.
```
✅ Protected directories are skipped. Existing agent-managed files remain untouched.

## Implementation Details

### Changes to `FileWriter` (`scripts/assembler/writer.py`)
- Added `_warnings: list[str]` field to track warnings
- Added `check_protected_dir(rel_path)` method to detect non-empty directories
- Added `add_warning(message)` method to queue warnings
- Updated `summary()` to display warnings in output

### Changes to `CopilotAssembler` (`scripts/assembler/platforms/copilot.py`)
- Updated `_assemble_state()` to check for `.github/state/archive/` before assembly
- Updated `_assemble_artifacts()` to check for `.github/artifacts/` before assembly
- Both methods issue warnings and return early if protected directories are detected

### Tests (`tests/test_assembler.py`)
Added 6 new tests in `TestProtectionMechanisms` class:
- `test_state_archive_protection`: Verifies state/ skipping and warning
- `test_artifacts_protection`: Verifies artifacts/ skipping and warning
- `test_both_protected_dirs_exist`: Tests both protections simultaneously
- `test_check_protected_dir_empty_dir_not_protected`: Empty dirs don't trigger protection
- `test_nonexistent_dir_not_protected`: Nonexistent dirs don't trigger protection
- `test_file_writer_add_warning`: Tests warning mechanism

## Behavior Matrix

| Scenario | State Assembly | Artifacts Assembly | Files Written | Warning Issued |
|----------|---|---|---|---|
| Fresh setup (no protected dirs) | ✅ | ✅ | 37 | ❌ |
| Protected dirs exist with files | ❌ | ❌ | 34 | ✅ |
| Empty protected dirs | ✅ | ✅ | 37 | ❌ |
| Mixed (one protected, one empty) | ✅ | ❌ | 36 | ✅ |

## User Guidance

### When You See Warnings
The warnings indicate that `assemble.py` has detected agent-managed files. This is **expected and safe**:
- Your existing archived state files are protected
- Your artifact registry is protected
- Only non-protected files are updated during assembly

### What If You WANT to Reset Protected Dirs?
If you need to clear protected directories:
```bash
# Backup first
cp -r .github/state/archive .github/state/archive.backup
cp .github/artifacts/REGISTRY.md .github/artifacts/REGISTRY.md.backup

# Clear the directories
rm -rf .github/state/archive
rm .github/artifacts/REGISTRY.md

# Re-run assembly
python3 scripts/assemble.py --target-dir . --platform copilot
```

## Related Skills
- `manage-state`: Creates and updates workflow state files in `.github/state/`
- `register-artifact`: Appends completed workflows to `.github/artifacts/REGISTRY.md`
- `git-operations`: Archives state files to `.github/state/archive/`
