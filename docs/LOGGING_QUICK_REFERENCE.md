# Logging Quick Reference

## For Users

### View Logs
```bash
# Console output (automatic during execution)
jira2pr run feature-workflow PROJ-123

# View full logs after execution
cat .jira2pr/logs/jira2pr.log

# Follow logs in real-time
tail -f .jira2pr/logs/jira2pr.log

# Search for specific events
grep "ERROR" .jira2pr/logs/jira2pr.log
grep "Escalating" .jira2pr/logs/jira2pr.log
grep "PROJ-123" .jira2pr/logs/jira2pr.log
```

### Log Location
```
<repo-root>/.jira2pr/logs/jira2pr.log
```

### Understanding Log Levels
- `DEBUG` - Detailed diagnostics (file only)
- `INFO` - Important milestones (console + file)
- `WARNING` - Unusual conditions like escalations (console + file)
- `ERROR` - Failures and exceptions (console + file)

---

## For Developers

### Adding Logging to a Module

```python
from runtime.logging_config import get_logger

logger = get_logger("module.submodule")

# In your code
logger.info("High-level event")
logger.debug("Detailed diagnostic info")
logger.warning("Unusual condition")
logger.error("Something failed")
logger.exception("Exception with traceback")  # Use in except blocks
```

### Logger Naming Convention

```
jira2pr.cli                          # CLI commands
jira2pr.workflow.executor            # Workflow orchestration
jira2pr.workflow.state_manager       # State persistence
jira2pr.workflow.worker_invoker      # Worker agent invocation
jira2pr.workflow.supervisor_invoker  # Supervisor evaluation
jira2pr.workflow.loader              # Project loading
jira2pr.backends.aider               # Aider subprocess
```

### Logging Best Practices

✅ **DO:**
- Log at the start of important operations
- Log outcomes (success, failure, transition)
- Log errors with context
- Use hierarchical logger names
- Log model/file/criteria details at DEBUG level

❌ **DON'T:**
- Log large prompt contents (just log lengths)
- Log sensitive information
- Use print() instead of logger
- Catch and suppress exceptions without logging

### Example: Adding Logging to New Code

```python
from runtime.logging_config import get_logger

logger = get_logger("workflow.example")

class MyWorker:
    def process(self, item):
        logger.info(f"Processing item: {item}")
        try:
            result = self._do_work(item)
            logger.debug(f"Work completed, result length: {len(result)}")
            return result
        except Exception as e:
            logger.exception(f"Processing failed for item {item}: {e}")
            raise

    def _do_work(self, item):
        logger.debug(f"Starting detailed work on {item}")
        # ... implementation ...
        logger.debug("Detailed work complete")
```

### Testing Logging

```bash
# Verify syntax
python3 -m py_compile engine/runtime/logging_config.py

# Test logging in isolation
python3 -c "from runtime.logging_config import setup_logging, get_logger; setup_logging(); logger = get_logger('test'); logger.info('Test message')"
```

### Adjusting Log Levels

Edit the setup_logging() call in cmd_run() and cmd_resume():

```python
# Current: shows INFO and above to console
setup_logging(log_dir=target_dir / ".jira2pr" / "logs")

# Alternative: show DEBUG to console too
setup_logging(log_dir=target_dir / ".jira2pr" / "logs", log_level="DEBUG")
```

---

## Architecture

```
setup_logging()  ←── Called from CLI (cmd_run, cmd_resume)
    ├─ Console Handler (INFO level)  → sys.stdout
    └─ File Handler (DEBUG level)    → .jira2pr/logs/jira2pr.log

get_logger(name) ←── Used by all runtime components
    ├─ logger.info()      → Both handlers
    ├─ logger.debug()     → File only
    ├─ logger.warning()   → Both handlers
    ├─ logger.error()     → Both handlers
    └─ logger.exception() → Both handlers (with traceback)
```

---

## Files Modified

| File | Changes |
|------|---------|
| `engine/runtime/logging_config.py` | **NEW** - Centralized logging setup |
| `engine/jira2pr/cli.py` | setup_logging() calls + logger statements in all commands |
| `engine/runtime/workflow/executor.py` | State transition logging, iteration tracking |
| `engine/runtime/backends/aider.py` | Subprocess invocation logging, error handling |
| `engine/runtime/workflow/worker_invoker.py` | Agent selection, artifact handling |
| `engine/runtime/workflow/supervisor_invoker.py` | Evaluation results, YAML parsing errors |
| `engine/runtime/workflow/state_manager.py` | State creation/loading/saving operations |
| `engine/runtime/workflow/loader.py` | Project initialization, configuration loading |

---

## Typical Workflow Log Flow

```
CLI         | Starting workflow...
Loader      | Loading project configuration
Executor    | Running workflow state machine
Worker      | Invoking agent X for state Y
Backend     | Starting subprocess with model Z
Backend     | Subprocess completed successfully
Worker      | Artifact produced
Supervisor  | Evaluating output against criteria
Supervisor  | Evaluation complete: outcome=success
Executor    | Transitioning to next state
StateManager| State saved
Executor    | Workflow complete: final status=completed
CLI         | Workflow execution finished
```

---

## Common Search Patterns

```bash
# Find all state transitions
grep "Transitioning to\|Processing state" .jira2pr/logs/jira2pr.log

# Find all backend calls
grep "Invoking aider\|Starting.*subprocess" .jira2pr/logs/jira2pr.log

# Find escalations
grep -i "escalat" .jira2pr/logs/jira2pr.log

# Find errors and warnings
grep -E "ERROR|WARNING" .jira2pr/logs/jira2pr.log

# Find a specific ticket workflow
grep "YOUR-TICKET-KEY" .jira2pr/logs/jira2pr.log

# Count state transitions
grep "Transitioning to" .jira2pr/logs/jira2pr.log | wc -l

# Track total iterations
grep "total iterations" .jira2pr/logs/jira2pr.log | tail -1

# Get execution time
head -1 .jira2pr/logs/jira2pr.log && tail -1 .jira2pr/logs/jira2pr.log
```
