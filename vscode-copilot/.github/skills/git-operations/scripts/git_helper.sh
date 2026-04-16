#!/usr/bin/env bash
# git_helper.sh — Git automation for branch creation, committing, and pushing.
# Usage: ./git_helper.sh <command> [args...]
# Commands:
#   create-branch <ticket-key> <type>   — Create and checkout a new branch
#   commit <message>                     — Stage all changes and commit
#   push                                 — Push current branch to origin
#   status                               — Show current branch and status summary

set -euo pipefail

# Load unset vars from .env at repo root (if present)
_repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -n "$_repo_root" && -f "$_repo_root/.env" ]]; then
  while IFS='=' read -r _k _v; do
    [[ -z "$_k" || "$_k" =~ ^[[:space:]]*# ]] && continue
    if [[ -z "${!_k+x}" ]]; then
      _v="${_v#[\"']}" ; _v="${_v%[\"']}"
      export "${_k}=${_v}"
    fi
  done < <(grep -E '^[^#].*=' "$_repo_root/.env" 2>/dev/null || true)
fi
unset _repo_root _k _v 2>/dev/null || true

usage() {
  cat <<'EOF'
Usage: git_helper.sh <command> [args...]

Commands:
  create-branch <ticket-key> <type>
      Create a branch named <type>/<ticket-key-lowercase>.
      Types: feat, fix, chore, refactor, docs, test
      Example: git_helper.sh create-branch PROJ-123 feat
        → creates branch: feat/proj-123

  commit "<message>"
      Stage all changes (git add -A) and commit with the given message.
      Example: git_helper.sh commit "feat(auth): add JWT validation"

  push
      Push the current branch to origin, setting upstream if needed.

  status
      Print current branch name, ahead/behind counts, and changed file summary.
EOF
  exit 1
}

if [[ $# -lt 1 ]]; then
  usage
fi

COMMAND="$1"
shift

case "$COMMAND" in
  create-branch)
    if [[ $# -lt 2 ]]; then
      echo "ERROR: create-branch requires <ticket-key> and <type>" >&2
      echo "Usage: git_helper.sh create-branch PROJ-123 feat" >&2
      exit 1
    fi
    TICKET_KEY="$1"
    TYPE="$2"

    # Validate type
    VALID_TYPES="feat fix chore refactor docs test"
    if [[ ! " $VALID_TYPES " =~ " $TYPE " ]]; then
      echo "ERROR: Invalid branch type '$TYPE'. Must be one of: $VALID_TYPES" >&2
      exit 1
    fi

    # Derive branch name: type/ticket-key-lowercase
    BRANCH_NAME="${TYPE}/$(echo "$TICKET_KEY" | tr '[:upper:]' '[:lower:]')"

    # Check if branch already exists
    if git rev-parse --verify "$BRANCH_NAME" &>/dev/null; then
      echo "Branch '$BRANCH_NAME' already exists. Checking out."
      git checkout "$BRANCH_NAME"
    else
      # Ensure we're on main/master before branching
      DEFAULT_BRANCH=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")
      echo "Creating branch '$BRANCH_NAME' from '$DEFAULT_BRANCH'..."
      git checkout "$DEFAULT_BRANCH" 2>/dev/null || git checkout main 2>/dev/null || git checkout master
      git pull --ff-only origin "$DEFAULT_BRANCH" 2>/dev/null || true
      git checkout -b "$BRANCH_NAME"
    fi

    echo "On branch: $BRANCH_NAME"
    ;;

  commit)
    if [[ $# -lt 1 ]]; then
      echo "ERROR: commit requires a message" >&2
      echo "Usage: git_helper.sh commit \"feat(scope): description\"" >&2
      exit 1
    fi
    MESSAGE="$1"

    # Check there are changes to commit
    if git diff --quiet && git diff --cached --quiet; then
      echo "No changes to commit."
      exit 0
    fi

    git add -A
    git commit -m "$MESSAGE"
    echo "Committed: $MESSAGE"
    echo "Files changed: $(git diff --name-only HEAD~1 2>/dev/null | wc -l | tr -d ' ')"
    ;;

  push)
    CURRENT_BRANCH=$(git branch --show-current)
    if [[ -z "$CURRENT_BRANCH" ]]; then
      echo "ERROR: Not on any branch (detached HEAD?)" >&2
      exit 1
    fi

    # Push with upstream tracking
    git push -u origin "$CURRENT_BRANCH"
    echo "Pushed branch '$CURRENT_BRANCH' to origin."
    ;;

  status)
    CURRENT_BRANCH=$(git branch --show-current)
    echo "Branch: $CURRENT_BRANCH"
    echo ""

    # Ahead/behind
    UPSTREAM=$(git rev-parse --abbrev-ref '@{upstream}' 2>/dev/null || echo "")
    if [[ -n "$UPSTREAM" ]]; then
      AHEAD=$(git rev-list --count "$UPSTREAM..HEAD" 2>/dev/null || echo "0")
      BEHIND=$(git rev-list --count "HEAD..$UPSTREAM" 2>/dev/null || echo "0")
      echo "Upstream: $UPSTREAM (ahead: $AHEAD, behind: $BEHIND)"
    else
      echo "Upstream: not set"
    fi

    echo ""
    echo "Changes:"
    git status --short
    ;;

  *)
    echo "ERROR: Unknown command '$COMMAND'" >&2
    usage
    ;;
esac
