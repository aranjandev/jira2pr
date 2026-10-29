# Compiler Safeguards Against Deleting Agent-Managed Files

## Overview

`jira2pr init`/`check` never emits, and therefore never prunes, anything the
compiler didn't itself generate. This is what protects agent-managed runtime
data — workflow state instances, archived state, artifact instances — from
being deleted when the generated scaffold (`.github/`, `.jira2pr/agents/`,
etc.) is regenerated after a canonical change.

## How it works: manifest-based pruning

Every file written by `FileWriter.put()`/`copy()`/`copy_tree()` during a run
is recorded in `.jira2pr/.manifest.json`. On the next `init`/`check`, any path
present in the *previous* manifest but not re-emitted this run is considered
stale and is deleted (`init`) or reported (`check`).

Because agent-managed files are never written via the writer in the first
place, they never enter the manifest, and pruning can never touch them:

| Data | Path | Ever in the manifest? |
|------|------|------------------------|
| Workflow state instances | `.jira2pr/state/<TICKET>.yaml` | No — written only by `runtime/workflow/state_manager.py` |
| Archived state | `.jira2pr/state/archive/<TICKET>.yaml` | No — same |
| Artifact instances | `.jira2pr/artifacts/<TICKET>/*.md` | No — written only by `runtime/workflow/worker_invoker.py` |
| Artifact **schemas** (e.g. `plan-schema.md`) | `.jira2pr/artifacts/*.md` | Yes — these are compiler output and are pruned/regenerated normally |
| State **template** | `.jira2pr/state/workflow-state.template.yaml` | Yes — compiler output |

This replaces the previous approach (skip whole-directory assembly with a
warning when a protected directory was non-empty). Manifest pruning is
strictly more precise: it prunes exactly the files the compiler owns, rather
than an entire directory that also might contain agent data. `FileWriter`
still exposes `check_protected_dir()` for adapters that want an advisory
warning, but it is no longer required for correctness.

## Example

```bash
$ jira2pr init --platform copilot --target-dir my-project
Wrote 31 file(s) to my-project

# ... later, after a canonical agent is removed ...

$ jira2pr init --platform copilot --target-dir my-project
Wrote 30 file(s) to my-project
Removed 1 stale file(s)
```

`jira2pr check` reports the same stale files as pending changes (exit code 1)
instead of deleting them, so CI can catch drift before it reaches a real repo.

