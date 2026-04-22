---
name: read-jira-ticket
description: 'Fetches a JIRA ticket by key or URL and extracts structured requirements including summary, description, acceptance criteria, subtasks, labels, and priority. Use when given a JIRA ticket link, ticket key, or asked to read/interpret a ticket.'
argument-hint: 'JIRA ticket key (e.g., PROJ-123) or full URL'
---

# Read JIRA Ticket

Fetches a JIRA ticket and produces a structured requirements document that downstream agents can use for planning and implementation.

## When to Use

- User provides a JIRA ticket key (e.g., `PROJ-123`) or URL
- A workflow needs to fetch ticket details before planning
- Asked to "read", "fetch", "interpret", or "understand" a JIRA ticket

## Prerequisites

The following environment variables must be set:
- `JIRA_BASE_URL` — Base URL of the JIRA instance
- `JIRA_API_TOKEN` — API token for authentication
- `JIRA_EMAIL` — Email associated with the API token

## Procedure

1. **Run the fetch script** to retrieve the ticket:
   ```bash
   python3 ./.github/skills/read-jira-ticket/scripts/fetch_jira.py <TICKET_KEY_OR_URL>
   ```
   Reference: [fetch_jira.py](./scripts/fetch_jira.py)

2. **Parse the JSON output** and extract these sections:

3. **Produce a structured requirements document** with the following format:

   ```
   ## Ticket: <KEY> — <Summary>

   **Type:** <issue_type> | **Priority:** <priority> | **Status:** <status>
   **Labels:** <labels> | **Story Points:** <story_points>

   ### Description
   <Cleaned description text>

   ### Requirements
   - <Functional requirement 1>
   - <Functional requirement 2>
   ...

   ### Acceptance Criteria
   - <Criterion 1>
   - <Criterion 2>
   ...
   (If no explicit acceptance criteria found, derive them from the description)

   ### Subtasks
   - [ ] <KEY>: <Summary> (<Status>)
   ...

   ### Related Issues
   - <Relationship type>: <KEY> — <Summary>
   ...

   ### Implementation Hints
   - <Any technical details, component mentions, or architectural hints from the ticket>
   
   ### Additional Notes
   - Plan approval required: <Yes/No based on labels or ticket content> 
   ```

4. **If the script fails:**
   - Check that env vars are set (`echo $JIRA_BASE_URL`, etc.)
   - Verify Python 3 is available (`python3 --version`)
   - Verify the ticket key format (must be `PROJ-123` pattern)
   - Report the error clearly — do not fabricate ticket contents

## Important

- Never invent or assume ticket content that isn't in the API response
- If the description is empty, say so explicitly
- If acceptance criteria are not explicitly stated, derive reasonable criteria from the description and mark them as "Inferred"
- Preserve any code snippets, links, or file references from the ticket
