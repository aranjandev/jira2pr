#!/usr/bin/env bash
# fetch_jira.sh — Fetches a JIRA ticket and outputs structured JSON.
# Usage: ./fetch_jira.sh <TICKET_KEY_OR_URL>
# Requires: JIRA_API_TOKEN, JIRA_BASE_URL environment variables, curl, jq

set -euo pipefail

# Load unset vars from .env at repo root (if present)
_env_file=""
_repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -n "$_repo_root" && -f "$_repo_root/.env" ]]; then
  _env_file="$_repo_root/.env"
elif [[ -f .env ]]; then
  _env_file=".env"
elif [[ -f "$HOME/.jira2pr.env" ]]; then
  _env_file="$HOME/.jira2pr.env"
fi

if [[ -n "$_env_file" ]]; then
  while IFS='=' read -r _k _v; do
    [[ -z "$_k" || "$_k" =~ ^[[:space:]]*# ]] && continue
    [[ "$_k" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]] || continue
    if [[ -z "${!_k+x}" ]]; then
      _v="${_v#[\"']}" ; _v="${_v%[\"']}"
      export "${_k}=${_v}"
    fi
  done < <(grep -E '^[^#].*=' "$_env_file" 2>/dev/null || true)
fi
unset _repo_root _env_file _k _v 2>/dev/null || true

usage() {
  echo "Usage: $0 <TICKET_KEY_OR_URL>"
  echo ""
  echo "Examples:"
  echo "  $0 PROJ-123"
  echo "  $0 https://yourcompany.atlassian.net/browse/PROJ-123"
  echo ""
  echo "Required env vars:"
  echo "  JIRA_BASE_URL  — e.g., https://yourcompany.atlassian.net"
  echo "  JIRA_API_TOKEN — Personal access token or API token"
  echo "  JIRA_EMAIL     — Email associated with the API token"
  exit 1
}

if [[ $# -lt 1 ]]; then
  usage
fi

# Validate dependencies
for cmd in curl jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: $cmd is required but not installed" >&2
    exit 1
  fi
done

# Use JIRA_EMAIL if set, otherwise fall back to JIRA_USER (accepted as a deprecated alias)
JIRA_EMAIL="${JIRA_EMAIL:-${JIRA_USER:-}}"

# Validate env vars
for var in JIRA_BASE_URL JIRA_API_TOKEN JIRA_EMAIL; do
  if [[ -z "${!var:-}" ]]; then
    echo "ERROR: $var environment variable is not set" >&2
    exit 1
  fi
done

INPUT="$1"

# Extract ticket key from URL or use as-is
if [[ "$INPUT" =~ ^https?:// ]]; then
  TICKET_KEY=$(echo "$INPUT" | grep -oE '[A-Z][A-Z0-9]+-[0-9]+' | head -1)
  if [[ -z "$TICKET_KEY" ]]; then
    echo "ERROR: Could not extract ticket key from URL: $INPUT" >&2
    exit 1
  fi
else
  TICKET_KEY="$INPUT"
fi

# Validate ticket key format
if [[ ! "$TICKET_KEY" =~ ^[A-Z][A-Z0-9]+-[0-9]+$ ]]; then
  echo "ERROR: Invalid ticket key format: $TICKET_KEY (expected e.g., PROJ-123)" >&2
  exit 1
fi

API_URL="${JIRA_BASE_URL%/}/rest/api/3/issue/${TICKET_KEY}"

# Fetch the ticket
HTTP_RESPONSE=$(curl -s -w "\n%{http_code}" \
  -H "Authorization: Basic $(printf '%s:%s' "$JIRA_EMAIL" "$JIRA_API_TOKEN" | base64)" \
  -H "Accept: application/json" \
  "$API_URL")

HTTP_BODY=$(echo "$HTTP_RESPONSE" | sed '$d')
HTTP_CODE=$(echo "$HTTP_RESPONSE" | tail -1)

if [[ "$HTTP_CODE" -ne 200 ]]; then
  echo "ERROR: JIRA API returned HTTP $HTTP_CODE for $TICKET_KEY" >&2
  echo "$HTTP_BODY" >&2
  exit 1
fi

# Extract and structure the relevant fields
echo "$HTTP_BODY" | jq '{
  key: .key,
  summary: .fields.summary,
  status: .fields.status.name,
  priority: .fields.priority.name,
  issue_type: .fields.issuetype.name,
  assignee: (.fields.assignee.displayName // "Unassigned"),
  reporter: (.fields.reporter.displayName // "Unknown"),
  labels: (.fields.labels // []),
  components: [.fields.components[]?.name],
  story_points: (.fields.customfield_10016 // null),
  sprint: (.fields.sprint.name // null),
  description: (
    if .fields.description then
      [.fields.description.content[]? |
        if .type == "paragraph" then
          [.content[]?.text | select(type == "string")] | join("")
        elif .type == "heading" then
          "\n## " + ([.content[]?.text | select(type == "string")] | join(""))
        elif .type == "bulletList" then
          [.content[]? | "- " + ([.content[]?.content[]?.text | select(type == "string")] | join(""))] | join("\n")
        elif .type == "orderedList" then
          [.content[]? | [.content[]?.content[]?.text | select(type == "string")] | join("")] |
          to_entries | map("\(.key + 1). \(.value)") | join("\n")
        elif .type == "codeBlock" then
          "```\n" + ([.content[]?.text | select(type == "string")] | join("")) + "\n```"
        else
          [.content[]?.text | select(type == "string")] | join("")
        end
      ] | join("\n")
    else
      ""
    end
  ),
  acceptance_criteria: (
    if .fields.customfield_10035 then
      .fields.customfield_10035
    elif .fields.description then
      [.fields.description.content[]? |
        select(
          (.type == "heading" and any(.content[]?.text; type == "string" and test("acceptance|criteria|done|definition"; "i")))
          or
          (.type == "paragraph" and any(.content[]?.text; type == "string" and test("acceptance|criteria|given|when|then"; "i")))
        ) | [.content[]?.text | select(type == "string")] | join("")
      ] | join("\n")
    else
      null
    end
  ),
  subtasks: [.fields.subtasks[]? | {key: .key, summary: .fields.summary, status: .fields.status.name}],
  linked_issues: [.fields.issuelinks[]? | {
    type: .type.name,
    key: (.outwardIssue.key // .inwardIssue.key),
    summary: (.outwardIssue.fields.summary // .inwardIssue.fields.summary)
  }],
  created: .fields.created,
  updated: .fields.updated,
  url: ("'"${JIRA_BASE_URL%/}"'" + "/browse/" + .key)
}'
