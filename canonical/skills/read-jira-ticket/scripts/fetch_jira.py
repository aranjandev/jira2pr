#!/usr/bin/env python3
# fetch_jira.py — Fetches a JIRA ticket and outputs structured JSON.
# Usage: python3 ./fetch_jira.py <TICKET_KEY_OR_URL>
# Requires: JIRA_API_TOKEN, JIRA_BASE_URL, JIRA_EMAIL environment variables

import base64
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path


# ─── .env loader ─────────────────────────────────────────────────────────────

def load_env():
    """Load unset vars from .env at repo root, .env in cwd, or ~/.jira2pr.env."""
    candidates = []

    try:
        repo_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
        candidates.append(Path(repo_root) / ".env")
    except subprocess.CalledProcessError:
        pass

    candidates.append(Path(".env"))
    candidates.append(Path.home() / ".jira2pr.env")

    for env_path in candidates:
        if env_path.is_file():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("\"'")
                    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
                        os.environ.setdefault(key, value)
            break  # Only load first found file


# ─── ADF description parser ──────────────────────────────────────────────────

def _extract_text(node) -> str:
    """Recursively extract plain text from an ADF inline node."""
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        text = node.get("text", "")
        return text if isinstance(text, str) else ""
    parts = []
    for child in node.get("content", []):
        parts.append(_extract_text(child))
    return "".join(parts)


def parse_adf_node(node) -> str:
    """Convert a single top-level ADF block node to markdown-ish text."""
    if not isinstance(node, dict):
        return ""

    node_type = node.get("type", "")
    content = node.get("content", [])

    if node_type == "paragraph":
        return "".join(_extract_text(c) for c in content)

    elif node_type == "heading":
        text = "".join(_extract_text(c) for c in content)
        return f"\n## {text}"

    elif node_type == "bulletList":
        lines = []
        for item in content:
            item_text = "".join(
                _extract_text(c)
                for block in item.get("content", [])
                for c in block.get("content", [])
            )
            lines.append(f"- {item_text}")
        return "\n".join(lines)

    elif node_type == "orderedList":
        lines = []
        for idx, item in enumerate(content, start=1):
            item_text = "".join(
                _extract_text(c)
                for block in item.get("content", [])
                for c in block.get("content", [])
            )
            lines.append(f"{idx}. {item_text}")
        return "\n".join(lines)

    elif node_type == "codeBlock":
        code = "".join(_extract_text(c) for c in content)
        return f"```\n{code}\n```"

    else:
        # Fallback: extract any text
        return "".join(_extract_text(c) for c in content)


def parse_adf_description(description_field) -> str:
    """Convert the JIRA ADF description object to a plain-text string."""
    if not description_field or not isinstance(description_field, dict):
        return ""
    blocks = description_field.get("content", [])
    parts = [parse_adf_node(b) for b in blocks]
    return "\n".join(p for p in parts if p)


def extract_acceptance_criteria(fields: dict) -> str:
    """Extract acceptance criteria from a custom field or from description headings."""
    # Custom field (common in Jira Cloud)
    ac = fields.get("customfield_10035")
    if ac:
        return ac if isinstance(ac, str) else json.dumps(ac)

    # Try to find an AC heading in the description
    desc = fields.get("description")
    if not desc or not isinstance(desc, dict):
        return ""

    ac_pattern = re.compile(r"acceptance|criteria|done|definition", re.IGNORECASE)
    ac_inline = re.compile(r"acceptance|criteria|given|when|then", re.IGNORECASE)

    results = []
    for node in desc.get("content", []):
        node_type = node.get("type", "")
        content = node.get("content", [])
        texts = [_extract_text(c) for c in content]
        flat = " ".join(t for t in texts if isinstance(t, str))

        if node_type == "heading" and ac_pattern.search(flat):
            results.append(flat)
        elif node_type == "paragraph" and ac_inline.search(flat):
            results.append(flat)

    return "\n".join(results)


# ─── HTTP helper ─────────────────────────────────────────────────────────────

def https_get(url: str, headers: dict) -> tuple[int, str]:
    """Perform a GET request. Returns (status_code, response_body)."""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


# ─── Main ────────────────────────────────────────────────────────────────────

USAGE = """\
Usage: fetch_jira.py <TICKET_KEY_OR_URL>

Examples:
  fetch_jira.py PROJ-123
  fetch_jira.py https://yourcompany.atlassian.net/browse/PROJ-123

Required env vars:
  JIRA_BASE_URL  — e.g., https://yourcompany.atlassian.net
  JIRA_API_TOKEN — Personal access token or API token
  JIRA_EMAIL     — Email associated with the API token (also accepted as JIRA_USER)
"""


def main():
    load_env()

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(USAGE, end="")
        sys.exit(0 if len(sys.argv) >= 2 else 1)

    # JIRA_EMAIL fallback to JIRA_USER
    if not os.environ.get("JIRA_EMAIL") and os.environ.get("JIRA_USER"):
        os.environ["JIRA_EMAIL"] = os.environ["JIRA_USER"]

    for var in ("JIRA_BASE_URL", "JIRA_API_TOKEN", "JIRA_EMAIL"):
        if not os.environ.get(var):
            print(f"ERROR: {var} environment variable is not set", file=sys.stderr)
            sys.exit(1)

    base_url = os.environ["JIRA_BASE_URL"].rstrip("/")
    token = os.environ["JIRA_API_TOKEN"]
    email = os.environ["JIRA_EMAIL"]

    # Parse ticket key from argument (may be a URL)
    raw = sys.argv[1]
    if raw.startswith("http://") or raw.startswith("https://"):
        match = re.search(r"[A-Z][A-Z0-9]+-[0-9]+", raw)
        if not match:
            print(f"ERROR: Could not extract ticket key from URL: {raw}", file=sys.stderr)
            sys.exit(1)
        ticket_key = match.group(0)
    else:
        ticket_key = raw

    if not re.match(r"^[A-Z][A-Z0-9]+-[0-9]+$", ticket_key):
        print(f"ERROR: Invalid ticket key format: {ticket_key} (expected e.g., PROJ-123)", file=sys.stderr)
        sys.exit(1)

    # Build auth header
    credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Accept": "application/json",
    }

    url = f"{base_url}/rest/api/3/issue/{ticket_key}"
    status, body = https_get(url, headers)

    if status != 200:
        print(f"ERROR: JIRA API returned HTTP {status} for {ticket_key}", file=sys.stderr)
        print(body, file=sys.stderr)
        sys.exit(1)

    data = json.loads(body)
    fields = data.get("fields", {})

    # Build structured output matching the shell script's jq output
    result = {
        "key": data.get("key"),
        "summary": fields.get("summary"),
        "status": (fields.get("status") or {}).get("name"),
        "priority": (fields.get("priority") or {}).get("name"),
        "issue_type": (fields.get("issuetype") or {}).get("name"),
        "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
        "reporter": (fields.get("reporter") or {}).get("displayName", "Unknown"),
        "labels": fields.get("labels") or [],
        "components": [c.get("name") for c in (fields.get("components") or []) if c.get("name")],
        "story_points": fields.get("customfield_10016"),
        "sprint": (fields.get("sprint") or {}).get("name") if isinstance(fields.get("sprint"), dict) else None,
        "description": parse_adf_description(fields.get("description")),
        "acceptance_criteria": extract_acceptance_criteria(fields),
        "subtasks": [
            {
                "key": st.get("key"),
                "summary": (st.get("fields") or {}).get("summary"),
                "status": ((st.get("fields") or {}).get("status") or {}).get("name"),
            }
            for st in (fields.get("subtasks") or [])
        ],
        "linked_issues": [
            {
                "type": (link.get("type") or {}).get("name"),
                "key": (link.get("outwardIssue") or link.get("inwardIssue") or {}).get("key"),
                "summary": (
                    (link.get("outwardIssue") or {}).get("fields", {}).get("summary")
                    or (link.get("inwardIssue") or {}).get("fields", {}).get("summary")
                ),
            }
            for link in (fields.get("issuelinks") or [])
        ],
        "created": fields.get("created"),
        "updated": fields.get("updated"),
        "url": f"{base_url}/browse/{data.get('key')}",
    }

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
