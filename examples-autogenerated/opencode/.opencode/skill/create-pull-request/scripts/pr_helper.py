#!/usr/bin/env python3
# pr_helper.py — Create or update Pull Requests on GitHub or Bitbucket via REST APIs.
# Usage: python3 ./pr_helper.py <command> [options]
# Commands: create, update, fetch-body
# Requires: GITHUB_TOKEN or BITBUCKET_TOKEN environment variable

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
    """Load unset vars from .env at repo root (if present)."""
    try:
        repo_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL, text=True
        ).strip()
    except subprocess.CalledProcessError:
        return

    env_path = Path(repo_root) / ".env"
    if not env_path.is_file():
        return

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


# ─── git helpers ─────────────────────────────────────────────────────────────

def git_output(*args) -> str:
    """Run a git command and return stdout. Exits on failure."""
    result = subprocess.run(["git"] + list(args), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ERROR: git {' '.join(args)} failed: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    return result.stdout.strip()


def detect_platform() -> str:
    remote_url = git_output("config", "--get", "remote.origin.url")
    if "github.com" in remote_url:
        return "github"
    elif "bitbucket.org" in remote_url or "bitbucket.com" in remote_url:
        return "bitbucket"
    else:
        print(f"ERROR: Could not detect platform from remote URL: {remote_url}", file=sys.stderr)
        sys.exit(1)


def extract_owner_repo() -> str:
    remote_url = git_output("config", "--get", "remote.origin.url")
    remote_url = remote_url.removesuffix(".git")
    # HTTPS: https://github.com/owner/repo
    m = re.match(r"https?://[^/]+/([^/]+)/(.+)$", remote_url)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    # SSH: git@github.com:owner/repo
    m = re.match(r"git@[^:]+:([^/]+)/(.+)$", remote_url)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    print(f"ERROR: Could not parse owner/repo from remote URL: {remote_url}", file=sys.stderr)
    sys.exit(1)


def current_branch() -> str:
    return git_output("branch", "--show-current")


def get_auth_token(platform: str) -> str:
    if platform == "github":
        token = os.environ.get("GITHUB_TOKEN", "")
        if not token:
            print("ERROR: GITHUB_TOKEN environment variable not set", file=sys.stderr)
            sys.exit(1)
        return token
    elif platform == "bitbucket":
        token = os.environ.get("BITBUCKET_TOKEN", "")
        if not token:
            print("ERROR: BITBUCKET_TOKEN environment variable not set", file=sys.stderr)
            sys.exit(1)
        return token
    sys.exit(1)


def get_bitbucket_username() -> str:
    username = os.environ.get("BITBUCKET_USERNAME", "")
    if not username:
        print("ERROR: BITBUCKET_USERNAME environment variable not set", file=sys.stderr)
        sys.exit(1)
    return username


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def http_request(method: str, url: str, headers: dict, payload: dict = None) -> tuple[int, dict]:
    """
    Perform an HTTP request. Returns (status_code, parsed_json_body).
    payload is serialised to JSON automatically.
    """
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"_raw": body}


def github_headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }


# ─── CREATE ──────────────────────────────────────────────────────────────────

def create_github_pr(owner_repo: str, token: str, title: str, body: str,
                     base: str, draft: bool, labels: str, branch: str):
    payload = {
        "title": title,
        "body": body,
        "head": branch,
        "draft": draft,
    }
    if base:
        payload["base"] = base
    if labels:
        payload["labels"] = [l.strip() for l in labels.split(",") if l.strip()]

    status, resp = http_request(
        "POST",
        f"https://api.github.com/repos/{owner_repo}/pulls",
        github_headers(token),
        payload,
    )
    if status != 201:
        print(f"ERROR: GitHub API returned HTTP {status}", file=sys.stderr)
        print(json.dumps(resp, indent=2), file=sys.stderr)
        sys.exit(1)

    print(f"PR_URL={resp['html_url']}")
    print(f"PR_NUMBER={resp['number']}")


def create_bitbucket_pr(owner_repo: str, token: str, title: str, body: str,
                        base: str, branch: str):
    payload = {
        "title": title,
        "description": body,
        "source": {"branch": {"name": branch}},
        "destination": {"branch": {"name": base}},
    }
    username = get_bitbucket_username()
    credentials = base64.b64encode(f"{username}:{token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
    }
    status, resp = http_request(
        "POST",
        f"https://api.bitbucket.org/2.0/repositories/{owner_repo}/pullrequests",
        headers,
        payload,
    )
    if status != 201:
        print(f"ERROR: Bitbucket API returned HTTP {status}", file=sys.stderr)
        print(json.dumps(resp, indent=2), file=sys.stderr)
        sys.exit(1)

    pr_url = (resp.get("links") or {}).get("html", {}).get("href", "")
    print(f"PR_URL={pr_url}")
    print(f"PR_NUMBER={resp.get('id')}")


# ─── UPDATE ───────────────────────────────────────────────────────────────────

def update_github_pr(owner_repo: str, token: str, pr_number: str,
                     body: str, title: str):
    payload = {}
    if body:
        payload["body"] = body
    if title:
        payload["title"] = title

    status, resp = http_request(
        "PATCH",
        f"https://api.github.com/repos/{owner_repo}/pulls/{pr_number}",
        github_headers(token),
        payload,
    )
    if status != 200:
        print(f"ERROR: GitHub API returned HTTP {status}", file=sys.stderr)
        print(json.dumps(resp, indent=2), file=sys.stderr)
        sys.exit(1)

    print(f"PR_URL={resp['html_url']}")


def undraft_github_pr(owner_repo: str, token: str, pr_number: str):
    # Step 1: fetch node_id via REST
    status, resp = http_request(
        "GET",
        f"https://api.github.com/repos/{owner_repo}/pulls/{pr_number}",
        github_headers(token),
    )
    if status != 200:
        print(f"ERROR: Could not fetch PR node_id. GitHub API returned HTTP {status}", file=sys.stderr)
        print(json.dumps(resp, indent=2), file=sys.stderr)
        sys.exit(1)

    node_id = resp.get("node_id")
    if not node_id:
        print("ERROR: Could not extract node_id from PR response", file=sys.stderr)
        sys.exit(1)

    # Step 2: GraphQL markPullRequestReadyForReview
    gql_payload = {
        "query": "mutation($id: ID!) { markPullRequestReadyForReview(input: {pullRequestId: $id}) { pullRequest { isDraft } } }",
        "variables": {"id": node_id},
    }
    gql_headers = {
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
    }
    status, resp = http_request("POST", "https://api.github.com/graphql", gql_headers, gql_payload)
    if status != 200:
        print(f"ERROR: GraphQL undraft returned HTTP {status}", file=sys.stderr)
        print(json.dumps(resp, indent=2), file=sys.stderr)
        sys.exit(1)

    errors = resp.get("errors")
    if errors:
        print("ERROR: GraphQL undraft mutation failed", file=sys.stderr)
        print(json.dumps(resp, indent=2), file=sys.stderr)
        sys.exit(1)

    print(f"OK: PR #{pr_number} marked as ready for review")


def update_bitbucket_pr(owner_repo: str, token: str, pr_number: str,
                        body: str, title: str):
    payload = {}
    if body:
        payload["description"] = body
    if title:
        payload["title"] = title

    username = get_bitbucket_username()
    credentials = base64.b64encode(f"{username}:{token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
    }
    status, resp = http_request(
        "PUT",
        f"https://api.bitbucket.org/2.0/repositories/{owner_repo}/pullrequests/{pr_number}",
        headers,
        payload,
    )
    if status != 200:
        print(f"ERROR: Bitbucket API returned HTTP {status}", file=sys.stderr)
        print(json.dumps(resp, indent=2), file=sys.stderr)
        sys.exit(1)

    pr_url = (resp.get("links") or {}).get("html", {}).get("href", "")
    print(f"PR_URL={pr_url}")


# ─── FETCH-BODY ───────────────────────────────────────────────────────────────

def fetch_github_pr_body(owner_repo: str, token: str, pr_number: str):
    status, resp = http_request(
        "GET",
        f"https://api.github.com/repos/{owner_repo}/pulls/{pr_number}",
        github_headers(token),
    )
    if status != 200:
        print(f"ERROR: GitHub API returned HTTP {status}", file=sys.stderr)
        print(json.dumps(resp, indent=2), file=sys.stderr)
        sys.exit(1)
    print(resp.get("body") or "")


def fetch_bitbucket_pr_body(owner_repo: str, token: str, pr_number: str):
    username = get_bitbucket_username()
    credentials = base64.b64encode(f"{username}:{token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
    }
    status, resp = http_request(
        "GET",
        f"https://api.bitbucket.org/2.0/repositories/{owner_repo}/pullrequests/{pr_number}",
        headers,
    )
    if status != 200:
        print(f"ERROR: Bitbucket API returned HTTP {status}", file=sys.stderr)
        print(json.dumps(resp, indent=2), file=sys.stderr)
        sys.exit(1)
    print(resp.get("description") or "")


# ─── Usage ───────────────────────────────────────────────────────────────────

USAGE = """\
Usage: pr_helper.py <command> [options]

Commands:
  create        Create a new Pull Request (POST)
  update        Update an existing Pull Request body/title (PATCH)
  fetch-body    Fetch the current body of an existing PR (GET)

Common Options:
  --dry-run             Show what would happen without executing

Create Options:
  --title <title>       PR title (required)
  --body <body>         PR body in markdown (required unless --body-file)
  --body-file <path>    Read PR body from file instead of --body
  --base <branch>       Base branch (default: repo default branch)
  --labels <l1,l2>      Comma-separated labels (GitHub only)
  --draft               Create as draft PR (GitHub only)

Update Options:
  --pr-number <N>       PR number to update (required)
  --body <body>         New PR body in markdown (required unless --body-file)
  --body-file <path>    Read PR body from file instead of --body
  --title <title>       Update PR title (optional)
  --undraft             Mark PR as ready for review (GitHub only)

Fetch-body Options:
  --pr-number <N>       PR number to fetch (required)

Environment Variables:
  GITHUB_TOKEN          GitHub personal access token (for GitHub repos)
  BITBUCKET_TOKEN       Bitbucket app password (for Bitbucket repos)

Output (create):
  PR_URL=<url>
  PR_NUMBER=<number>

Output (update):
  PR_URL=<url>

Output (fetch-body):
  Raw PR body markdown to stdout

Examples:
  pr_helper.py create --title "feat: add auth" --body "..." --draft --labels "feature"
  pr_helper.py update --pr-number 42 --body-file /tmp/pr_body.md
  pr_helper.py update --pr-number 42 --body-file /tmp/pr_body.md --undraft
  pr_helper.py fetch-body --pr-number 42
"""


# ─── Argument parser ─────────────────────────────────────────────────────────

def parse_args():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(USAGE, end="")
        sys.exit(0)

    command = args[0]
    if command not in ("create", "update", "fetch-body"):
        print(f"ERROR: Unknown command: {command}", file=sys.stderr)
        print("Valid commands: create, update, fetch-body", file=sys.stderr)
        sys.exit(1)

    opts = {
        "command": command,
        "title": "",
        "body": "",
        "base": "",
        "labels": "",
        "draft": False,
        "undraft": False,
        "pr_number": "",
        "dry_run": False,
    }

    i = 1
    while i < len(args):
        a = args[i]
        if a == "--title":
            opts["title"] = args[i + 1]; i += 2
        elif a == "--body":
            opts["body"] = args[i + 1]; i += 2
        elif a == "--body-file":
            path = args[i + 1]
            if not Path(path).is_file():
                print(f"ERROR: Body file not found: {path}", file=sys.stderr)
                sys.exit(1)
            opts["body"] = Path(path).read_text(); i += 2
        elif a == "--base":
            opts["base"] = args[i + 1]; i += 2
        elif a == "--labels":
            opts["labels"] = args[i + 1]; i += 2
        elif a == "--draft":
            opts["draft"] = True; i += 1
        elif a == "--undraft":
            opts["undraft"] = True; i += 1
        elif a == "--pr-number":
            opts["pr_number"] = args[i + 1]; i += 2
        elif a == "--dry-run":
            opts["dry_run"] = True; i += 1
        elif a in ("-h", "--help"):
            print(USAGE, end=""); sys.exit(0)
        else:
            print(f"ERROR: Unknown option: {a}", file=sys.stderr)
            sys.exit(1)

    return opts


# ─── Validation ──────────────────────────────────────────────────────────────

def validate(opts: dict):
    cmd = opts["command"]
    if cmd == "create":
        if not opts["title"]:
            print("ERROR: --title is required for create", file=sys.stderr); sys.exit(1)
        if not opts["body"]:
            print("ERROR: --body or --body-file is required for create", file=sys.stderr); sys.exit(1)
    elif cmd == "update":
        if not opts["pr_number"]:
            print("ERROR: --pr-number is required for update", file=sys.stderr); sys.exit(1)
        if not opts["body"] and not opts["undraft"] and not opts["title"]:
            print("ERROR: --body, --body-file, --title, or --undraft is required for update", file=sys.stderr)
            sys.exit(1)
    elif cmd == "fetch-body":
        if not opts["pr_number"]:
            print("ERROR: --pr-number is required for fetch-body", file=sys.stderr); sys.exit(1)


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    load_env()
    opts = parse_args()
    validate(opts)

    platform = detect_platform()
    owner_repo = extract_owner_repo()
    branch = current_branch()
    token = get_auth_token(platform)
    cmd = opts["command"]

    # ── CREATE ───────────────────────────────────────────────────────────────
    if cmd == "create":
        if opts["dry_run"]:
            print("=== DRY RUN: create ===")
            print(f"Platform: {platform}")
            print(f"Repository: {owner_repo}")
            print(f"Title: {opts['title']}")
            print(f"Branch: {branch} → {opts['base'] or '<default>'}")
            if opts["labels"]:
                print(f"Labels: {opts['labels']}")
            if opts["draft"]:
                print("Draft: true")
            print()
            print("Body:")
            print(opts["body"])
            print()
            if platform == "github":
                print(f"API Call: POST https://api.github.com/repos/{owner_repo}/pulls")
            else:
                print(f"API Call: POST https://api.bitbucket.org/2.0/repositories/{owner_repo}/pullrequests")
        else:
            if platform == "github":
                create_github_pr(owner_repo, token, opts["title"], opts["body"],
                                 opts["base"], opts["draft"], opts["labels"], branch)
            else:
                create_bitbucket_pr(owner_repo, token, opts["title"], opts["body"],
                                    opts["base"], branch)

    # ── UPDATE ───────────────────────────────────────────────────────────────
    elif cmd == "update":
        if opts["dry_run"]:
            print("=== DRY RUN: update ===")
            print(f"Platform: {platform}")
            print(f"Repository: {owner_repo}")
            print(f"PR Number: {opts['pr_number']}")
            if opts["title"]:
                print(f"New Title: {opts['title']}")
            if opts["undraft"]:
                print("Undraft: true")
            if opts["body"]:
                print()
                print("New Body:")
                print(opts["body"])
            print()
            if platform == "github":
                print(f"API Call: PATCH https://api.github.com/repos/{owner_repo}/pulls/{opts['pr_number']}")
                if opts["undraft"]:
                    print("API Call: POST https://api.github.com/graphql (markPullRequestReadyForReview)")
            else:
                print(f"API Call: PUT https://api.bitbucket.org/2.0/repositories/{owner_repo}/pullrequests/{opts['pr_number']}")
        else:
            if opts["body"] or opts["title"]:
                if platform == "github":
                    update_github_pr(owner_repo, token, opts["pr_number"], opts["body"], opts["title"])
                else:
                    update_bitbucket_pr(owner_repo, token, opts["pr_number"], opts["body"], opts["title"])
            if opts["undraft"]:
                if platform == "github":
                    undraft_github_pr(owner_repo, token, opts["pr_number"])
                else:
                    print("WARN: --undraft is not supported on Bitbucket (no draft concept)", file=sys.stderr)

    # ── FETCH-BODY ────────────────────────────────────────────────────────────
    elif cmd == "fetch-body":
        if opts["dry_run"]:
            print("=== DRY RUN: fetch-body ===")
            print(f"Platform: {platform}")
            print(f"Repository: {owner_repo}")
            print(f"PR Number: {opts['pr_number']}")
            if platform == "github":
                print(f"API Call: GET https://api.github.com/repos/{owner_repo}/pulls/{opts['pr_number']}")
            else:
                print(f"API Call: GET https://api.bitbucket.org/2.0/repositories/{owner_repo}/pullrequests/{opts['pr_number']}")
        else:
            if platform == "github":
                fetch_github_pr_body(owner_repo, token, opts["pr_number"])
            else:
                fetch_bitbucket_pr_body(owner_repo, token, opts["pr_number"])


if __name__ == "__main__":
    main()
