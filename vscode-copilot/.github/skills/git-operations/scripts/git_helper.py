#!/usr/bin/env python3
# git_helper.py — Git automation for branch creation, committing, and pushing.
# Usage: ./git_helper.py <command> [args...]
# Commands:
#   create-branch <ticket-key> <type>   — Create and checkout a new branch
#   commit <message>                     — Stage all changes and commit
#   push                                 — Push current branch to origin
#   status                               — Show current branch and status summary

import os
import re
import subprocess
import sys
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

def git(*args, check=True, capture=False):
    """Run a git command. Returns stdout string if capture=True."""
    cmd = ["git"] + list(args)
    if capture:
        result = subprocess.run(cmd, text=True, capture_output=True)
        if check and result.returncode != 0:
            print(f"ERROR: git {' '.join(args)} failed:\n{result.stderr.strip()}", file=sys.stderr)
            sys.exit(1)
        return result.stdout.strip()
    else:
        result = subprocess.run(cmd)
        if check and result.returncode != 0:
            sys.exit(result.returncode)
        return None


def current_branch():
    return git("branch", "--show-current", capture=True)


# ─── Commands ────────────────────────────────────────────────────────────────

VALID_TYPES = {"feat", "fix", "chore", "refactor", "docs", "test"}


def cmd_create_branch(ticket_key: str, branch_type: str):
    if branch_type not in VALID_TYPES:
        print(f"ERROR: Invalid branch type '{branch_type}'. Must be one of: {', '.join(sorted(VALID_TYPES))}", file=sys.stderr)
        sys.exit(1)

    branch_name = f"{branch_type}/{ticket_key.lower()}"

    # Check if branch already exists
    result = subprocess.run(
        ["git", "rev-parse", "--verify", branch_name],
        capture_output=True
    )
    if result.returncode == 0:
        print(f"Branch '{branch_name}' already exists. Checking out.")
        git("checkout", branch_name)
    else:
        # Determine default branch
        try:
            default = git("symbolic-ref", "refs/remotes/origin/HEAD", capture=True)
            default = default.replace("refs/remotes/origin/", "")
        except SystemExit:
            default = "main"

        print(f"Creating branch '{branch_name}' from '{default}'...")

        # Checkout default branch, try fallbacks
        checked_out = False
        for base in [default, "main", "master"]:
            r = subprocess.run(["git", "checkout", base], capture_output=True)
            if r.returncode == 0:
                checked_out = True
                break
        if not checked_out:
            print("ERROR: Could not checkout default branch", file=sys.stderr)
            sys.exit(1)

        subprocess.run(["git", "pull", "--ff-only", "origin", default], capture_output=True)
        git("checkout", "-b", branch_name)

    print(f"On branch: {branch_name}")


def cmd_commit(message: str):
    # Check if there are any changes
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
    unstaged = subprocess.run(["git", "diff", "--quiet"], capture_output=True)
    if staged.returncode == 0 and unstaged.returncode == 0:
        print("No changes to commit.")
        sys.exit(0)

    git("add", "-A")
    git("commit", "-m", message)
    print(f"Committed: {message}")

    # Count changed files
    try:
        files = git("diff", "--name-only", "HEAD~1", capture=True)
        count = len([f for f in files.splitlines() if f])
        print(f"Files changed: {count}")
    except SystemExit:
        pass


def cmd_push():
    branch = current_branch()
    if not branch:
        print("ERROR: Not on any branch (detached HEAD?)", file=sys.stderr)
        sys.exit(1)

    git("push", "-u", "origin", branch)
    print(f"Pushed branch '{branch}' to origin.")


def cmd_status():
    branch = current_branch()
    print(f"Branch: {branch}")
    print()

    upstream = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "@{upstream}"],
        capture_output=True, text=True
    )
    if upstream.returncode == 0:
        u = upstream.stdout.strip()
        ahead = git("rev-list", "--count", f"{u}..HEAD", capture=True)
        behind = git("rev-list", "--count", f"HEAD..{u}", capture=True)
        print(f"Upstream: {u} (ahead: {ahead}, behind: {behind})")
    else:
        print("Upstream: not set")

    print()
    print("Changes:")
    subprocess.run(["git", "status", "--short"])


# ─── Usage ───────────────────────────────────────────────────────────────────

USAGE = """\
Usage: git_helper.py <command> [args...]

Commands:
  create-branch <ticket-key> <type>
      Create a branch named <type>/<ticket-key-lowercase>.
      Types: feat, fix, chore, refactor, docs, test
      Example: git_helper.py create-branch PROJ-123 feat
        → creates branch: feat/proj-123

  commit "<message>"
      Stage all changes (git add -A) and commit with the given message.
      Example: git_helper.py commit "feat(auth): add JWT validation"

  push
      Push the current branch to origin, setting upstream if needed.

  status
      Print current branch name, ahead/behind counts, and changed file summary.
"""


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    load_env()

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(USAGE, end="")
        sys.exit(0 if len(sys.argv) >= 2 else 1)

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "create-branch":
        if len(args) < 2:
            print("ERROR: create-branch requires <ticket-key> and <type>", file=sys.stderr)
            print("Usage: git_helper.py create-branch PROJ-123 feat", file=sys.stderr)
            sys.exit(1)
        cmd_create_branch(args[0], args[1])

    elif command == "commit":
        if len(args) < 1:
            print("ERROR: commit requires a message", file=sys.stderr)
            print('Usage: git_helper.py commit "feat(scope): description"', file=sys.stderr)
            sys.exit(1)
        cmd_commit(args[0])

    elif command == "push":
        cmd_push()

    elif command == "status":
        cmd_status()

    else:
        print(f"ERROR: Unknown command '{command}'", file=sys.stderr)
        print(USAGE, end="", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
