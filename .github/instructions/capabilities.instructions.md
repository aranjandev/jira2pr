---
description: "How each capability resolves to a runtime binding."
---

# Capabilities

| Capability | Type | Resolution |
|------------|------|------------|
| `diff.read` | context | native platform tool |
| `git.commit` | action | `python3 .jira2pr/runtime/integrations/git.py commit <message> <files_from>` |
| `git.push` | action | `python3 .jira2pr/runtime/integrations/git.py push` |
| `git.status` | context | `python3 .jira2pr/runtime/integrations/git.py status` |
| `jira.read` | context | `python3 .jira2pr/runtime/integrations/jira.py <ticket_key_or_url>` |
| `pr.create` | action | `python3 .jira2pr/runtime/integrations/github.py create --title <title> --body-file <body_file>` |
| `pr.update` | action | `python3 .jira2pr/runtime/integrations/github.py update --pr-number <pr_number> --body-file <body_file>` |
| `test.results` | context | native platform tool |
| `web.search` | context | native platform tool |
