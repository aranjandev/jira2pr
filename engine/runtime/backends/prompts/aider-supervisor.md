Perform only the supervisor evaluation defined by the provided supervisor instructions.

This is an evaluation-only invocation.

The read-only files are evidence. Do not modify them, fix them, request additional files, or propose repository edits.

Evaluate only the success criteria listed in the current supervisor context.

The editable JSON file is the only output of this invocation.

Write the supervisor decision to that JSON file using Aider's file-editing mechanism.

The JSON decision must contain only:
- outcome
- reason
- feedback
- violations

If tests or lint failed, report that failure in the JSON decision. Do not attempt to fix the failures.

If implementation evidence is incomplete, report failure or escalation according to the supervisor contract. Do not request additional repository files.

After writing the JSON decision file, stop immediately.

Do not inspect, modify, or request any other repository file.