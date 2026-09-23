# Aider Workflow Logging Guide

## Overview

The Aider workflow runtime now includes comprehensive logging to both console and log files. This allows you to monitor what's happening when you run `jira2pr run` or `jira2pr resume` commands.

## Logging Architecture

The logging system is centralized in `engine/runtime/logging_config.py` and provides:

- **Console Output**: Real-time visibility of workflow progress on the terminal
- **File Logging**: Persistent log files for debugging and audit trails
- **Structured Logging**: Hierarchical logger names for filtering and organization

## Where to Find Logs

Logs are automatically stored in:

```
<repo-root>/.jira2pr/logs/jira2pr.log
```

For example, if you run a workflow in your current directory:
```bash
jira2pr run feature-workflow PROJ-123
```

The log file will be at:
```
.jira2pr/logs/jira2pr.log
```

## Log Levels

The console output shows **INFO** level and above:
- `INFO` - Important workflow progress milestones
- `WARNING` - Unusual conditions (escalations, parsing issues, etc.)
- `ERROR` - Failures and exceptions
- `DEBUG` - Detailed diagnostic information (also in file only)

The log file contains **DEBUG** level and above (most detailed):
- `DEBUG` - All diagnostic details for troubleshooting
- Plus all `INFO`, `WARNING`, and `ERROR` messages

## Log Format

All log entries follow this format:

```
YYYY-MM-DD HH:MM:SS | LEVEL    | logger.name | message
```

Example:
```
2025-09-22 14:32:10 | INFO     | jira2pr.cli | Starting workflow: feature-workflow for ticket: PROJ-123
2025-09-22 14:32:10 | INFO     | jira2pr.workflow.executor | Executor initialized with backend: aider
2025-09-22 14:32:11 | INFO     | jira2pr.workflow.worker_invoker | Invoking worker agent: planner for state: understand
2025-09-22 14:32:15 | INFO     | jira2pr.backends.aider | Invoking aider with model=gpt-4, files=5
```

## Components Covered

### CLI Entry Points (`jira2pr/cli.py`)
Logs command invocation, target directory, backend selection, and top-level errors.

Example:
```
2025-09-22 14:32:10 | INFO     | jira2pr.cli | Starting workflow: feature-workflow for ticket: PROJ-123
2025-09-22 14:32:10 | DEBUG    | jira2pr.cli | Target directory: /path/to/repo
2025-09-22 14:32:10 | DEBUG    | jira2pr.cli | Backend: aider
```

### Workflow Executor (`runtime/workflow/executor.py`)
Logs workflow state transitions, iterations, terminal conditions, and escalations.

Example:
```
2025-09-22 14:32:11 | INFO     | jira2pr.workflow.executor | Loaded state for PROJ-123: workflow=feature, current_state=understand
2025-09-22 14:32:11 | INFO     | jira2pr.workflow.executor | [Iteration 1] Processing state: understand (attempt 1, total iterations: 1)
2025-09-22 14:32:15 | INFO     | jira2pr.workflow.executor | Supervisor outcome: success, Reason: All criteria met
2025-09-22 14:32:15 | INFO     | jira2pr.workflow.executor | Transitioning to next state: plan
```

### Worker Invoker (`runtime/workflow/worker_invoker.py`)
Logs worker agent invocation, artifact consumption/production, and model selection.

Example:
```
2025-09-22 14:32:11 | INFO     | jira2pr.workflow.worker_invoker | Invoking worker agent: planner for state: understand
2025-09-22 14:32:11 | DEBUG    | jira2pr.workflow.worker_invoker | Worker agent model tier: 2
2025-09-22 14:32:11 | DEBUG    | jira2pr.workflow.worker_invoker | Consumed 2 artifact(s), total content length: 1234
2025-09-22 14:32:15 | INFO     | jira2pr.workflow.worker_invoker | Worker response received, length: 5678 characters
2025-09-22 14:32:15 | INFO     | jira2pr.workflow.worker_invoker | Writing 2 produced artifact(s)
```

### Supervisor Invoker (`runtime/workflow/supervisor_invoker.py`)
Logs supervisor evaluation, success criteria checks, and outcome parsing.

Example:
```
2025-09-22 14:32:15 | INFO     | jira2pr.workflow.supervisor_invoker | Invoking supervisor for state: understand, workflow: feature
2025-09-22 14:32:15 | DEBUG    | jira2pr.workflow.supervisor_invoker | Success criteria: requirement1, requirement2, requirement3
2025-09-22 14:32:17 | INFO     | jira2pr.workflow.supervisor_invoker | Supervisor evaluation result: outcome=success
2025-09-22 14:32:17 | DEBUG    | jira2pr.workflow.supervisor_invoker | Supervisor reason: All requirements met
```

### Aider Backend (`runtime/backends/aider.py`)
Logs aider subprocess invocation, model selection, timeouts, and errors.

Example:
```
2025-09-22 14:32:11 | INFO     | jira2pr.backends.aider | Invoking aider with model=gpt-4, files=5
2025-09-22 14:32:11 | DEBUG    | jira2pr.backends.aider | System prompt length: 2345, User prompt length: 6789
2025-09-22 14:32:11 | DEBUG    | jira2pr.backends.aider | Running command: aider --model gpt-4 --message-file /tmp/... --yes-always --no-auto-commits file1.py file2.py
2025-09-22 14:32:11 | INFO     | jira2pr.backends.aider | Starting aider subprocess with timeout=600s
2025-09-22 14:32:15 | DEBUG    | jira2pr.backends.aider | Aider subprocess completed with return code: 0
2025-09-22 14:32:15 | INFO     | jira2pr.backends.aider | Aider invocation successful, response length: 4567 characters
```

### State Manager (`runtime/workflow/state_manager.py`)
Logs state creation, loading, saving, and archiving operations.

Example:
```
2025-09-22 14:32:10 | INFO     | jira2pr.workflow.state_manager | Creating new workflow state for PROJ-123: workflow=feature, initial_state=understand
2025-09-22 14:32:10 | DEBUG    | jira2pr.workflow.state_manager | State created and saved for PROJ-123
2025-09-22 14:32:11 | INFO     | jira2pr.workflow.state_manager | Loading workflow state for PROJ-123 from /path/to/.jira2pr/state/PROJ-123.yaml
2025-09-22 14:32:15 | DEBUG    | jira2pr.workflow.state_manager | State saved atomically for PROJ-123
```

### Project Loader (`runtime/workflow/loader.py`)
Logs project initialization, configuration loading, and workflow/agent parsing.

Example:
```
2025-09-22 14:32:10 | INFO     | jira2pr.workflow.loader | Loading RuntimeProject from /path/to/repo
2025-09-22 14:32:10 | DEBUG    | jira2pr.workflow.loader | Core directory found: /path/to/repo/.jira2pr
2025-09-22 14:32:10 | INFO     | jira2pr.workflow.loader | Loaded 7 agents
2025-09-22 14:32:10 | INFO     | jira2pr.workflow.loader | Loaded 3 workflows: bugfix, feature, scope-creep
2025-09-22 14:32:10 | INFO     | jira2pr.workflow.loader | RuntimeProject loaded successfully
```

## Example Workflow Log

Here's a sample workflow execution log showing all the key events:

```
2025-09-22 14:32:10 | INFO     | jira2pr.cli | Starting workflow: feature-workflow for ticket: PROJ-123
2025-09-22 14:32:10 | DEBUG    | jira2pr.cli | Target directory: /path/to/repo
2025-09-22 14:32:10 | DEBUG    | jira2pr.cli | Backend: aider
2025-09-22 14:32:10 | INFO     | jira2pr.cli | Project loaded successfully
2025-09-22 14:32:10 | INFO     | jira2pr.cli | Executor initialized with backend: aider
2025-09-22 14:32:10 | INFO     | jira2pr.workflow.loader | Loading RuntimeProject from /path/to/repo
2025-09-22 14:32:10 | INFO     | jira2pr.workflow.loader | Loaded 7 agents
2025-09-22 14:32:10 | INFO     | jira2pr.workflow.loader | Loaded 3 workflows: bugfix, feature, scope-creep
2025-09-22 14:32:10 | INFO     | jira2pr.workflow.loader | RuntimeProject loaded successfully
2025-09-22 14:32:10 | INFO     | jira2pr.workflow.state_manager | Creating new workflow state for PROJ-123: workflow=feature, initial_state=understand
2025-09-22 14:32:10 | INFO     | jira2pr.workflow.executor | Starting new workflow: feature for ticket: PROJ-123
2025-09-22 14:32:10 | INFO     | jira2pr.workflow.executor | Running workflow for ticket: PROJ-123
2025-09-22 14:32:10 | INFO     | jira2pr.workflow.executor | Loaded state for PROJ-123: workflow=feature, current_state=understand
2025-09-22 14:32:11 | DEBUG    | jira2pr.workflow.executor | [Iteration 1] Current state: understand, Terminal: False
2025-09-22 14:32:11 | INFO     | jira2pr.workflow.executor | [Iteration 1] Processing state: understand (attempt 1, total iterations: 1)
2025-09-22 14:32:11 | DEBUG    | jira2pr.workflow.executor | Invoking worker for state: understand
2025-09-22 14:32:11 | INFO     | jira2pr.workflow.worker_invoker | Invoking worker agent: planner for state: understand
2025-09-22 14:32:11 | INFO     | jira2pr.backends.aider | Invoking aider with model=gpt-4, files=2
2025-09-22 14:32:15 | INFO     | jira2pr.backends.aider | Aider invocation successful, response length: 5678 characters
2025-09-22 14:32:15 | INFO     | jira2pr.workflow.worker_invoker | Worker response received, length: 5678 characters
2025-09-22 14:32:15 | INFO     | jira2pr.workflow.executor | Invoking supervisor for state: understand
2025-09-22 14:32:15 | INFO     | jira2pr.workflow.supervisor_invoker | Invoking supervisor for state: understand, workflow: feature
2025-09-22 14:32:15 | INFO     | jira2pr.backends.aider | Invoking aider with model=gpt-4, files=0
2025-09-22 14:32:17 | INFO     | jira2pr.backends.aider | Aider invocation successful, response length: 234 characters
2025-09-22 14:32:17 | INFO     | jira2pr.workflow.supervisor_invoker | Supervisor evaluation result: outcome=success
2025-09-22 14:32:17 | INFO     | jira2pr.workflow.executor | Supervisor outcome: success, Reason: Requirements met
2025-09-22 14:32:17 | INFO     | jira2pr.workflow.executor | Transitioning to next state: plan
2025-09-22 14:32:17 | INFO     | jira2pr.workflow.executor | [Iteration 2] Processing state: plan (attempt 1, total iterations: 2)
... (more iterations) ...
2025-09-22 14:35:30 | INFO     | jira2pr.workflow.executor | Workflow reached terminal state: complete (outcome=success)
2025-09-22 14:35:30 | INFO     | jira2pr.workflow.executor | Final status: completed
2025-09-22 14:35:30 | INFO     | jira2pr.cli | Workflow completed with status: completed
```

## Troubleshooting with Logs

### Aider Invocation Failures

Look for these messages in the log:
```
ERROR | jira2pr.backends.aider | Aider timed out after 600s
ERROR | jira2pr.backends.aider | Aider exited with non-zero code: 1
```

Check the log for the aider command that was run to debug why aider failed.

### Supervisor Parsing Issues

Look for:
```
WARNING | jira2pr.workflow.supervisor_invoker | Supervisor output parsing failed
ERROR | jira2pr.workflow.supervisor_invoker | Invalid outcome value
```

This indicates the supervisor response wasn't valid YAML.

### State Management Issues

Look for:
```
ERROR | jira2pr.workflow.state_manager | State already exists for PROJ-123
ERROR | jira2pr.workflow.state_manager | No workflow state found for PROJ-123
```

### Escalation Events

Look for:
```
WARNING | jira2pr.workflow.executor | Escalating due to retry attempts exhausted
WARNING | jira2pr.workflow.executor | Global iteration cap exceeded
WARNING | jira2pr.workflow.state_manager | Recorded escalation at state plan: max retries exceeded
```

## Viewing Logs

### Real-time Console Output
```bash
jira2pr run feature-workflow PROJ-123
```

The console will show INFO level and above messages as they happen.

### After Execution
View the full log file with all details:
```bash
cat .jira2pr/logs/jira2pr.log
```

### Search Logs
Find specific events:
```bash
# Find all aider invocations
grep "Invoking aider" .jira2pr/logs/jira2pr.log

# Find all escalations
grep "Escalating" .jira2pr/logs/jira2pr.log

# Find errors
grep "ERROR" .jira2pr/logs/jira2pr.log

# Find warnings
grep "WARNING" .jira2pr/logs/jira2pr.log

# Follow a specific workflow
grep "PROJ-123" .jira2pr/logs/jira2pr.log
```

### Tail Live Logs
Monitor a running workflow (in another terminal):
```bash
tail -f .jira2pr/logs/jira2pr.log
```

## Log File Management

Log files are written to `.jira2pr/logs/jira2pr.log` and accumulate over time. Consider:

- **Periodic cleanup**: Delete or archive old log files
- **Log rotation**: Future versions may implement automatic log rotation
- **Size limits**: Log files can grow large on long-running or many workflows

## Configuration

Currently, logging is set to:
- **Console level**: `INFO` (important milestones)
- **File level**: `DEBUG` (all details)

To adjust these levels (requires code change):
Edit `engine/runtime/logging_config.py` and modify the `setup_logging()` call in `cli.py`.

---

**Questions?** Check the log files first — they contain detailed diagnostic information for most issues!
