#!/usr/bin/env bash
# create_pr.sh — Creates a Pull Request on GitHub or Bitbucket using REST APIs.
# Usage: ./create_pr.sh [options]
# Requires: curl, git, jq, appropriate auth tokens (GITHUB_TOKEN or BITBUCKET_TOKEN)

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

# Defaults
TITLE=""
BODY=""
BASE=""
LABELS=""
DRAFT=false
DRY_RUN=false

usage() {
  cat <<'EOF'
Usage: create_pr.sh [options]

Detects GitHub or Bitbucket from git remote and creates PR via REST API.

Options:
  --title <title>       PR title (required)
  --body <body>         PR body in markdown (required)
  --body-file <path>    Read PR body from file instead of --body
  --base <branch>       Base branch (default: repo default branch)
  --labels <l1,l2>      Comma-separated labels (GitHub only)
  --draft               Create as draft PR (GitHub only)
  --dry-run             Show what would be created without creating

Environment Variables:
  GITHUB_TOKEN          GitHub personal access token (for GitHub repos)
  BITBUCKET_TOKEN       Bitbucket app password (for Bitbucket repos)

Examples:
  create_pr.sh --title "feat: add auth" --body "## What\nAdded JWT auth" --labels "feature,auth"
  create_pr.sh --title "fix: null check" --body-file /tmp/pr_body.md --draft
EOF
  exit 1
}

# Validate dependencies
for cmd in curl git jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: $cmd is required but not installed." >&2
    exit 1
  fi
done

# Detect platform and extract owner/repo from remote URL
detect_platform() {
  local remote_url
  remote_url=$(git config --get remote.origin.url)
  
  if [[ $remote_url == *"github.com"* ]] || [[ $remote_url == *"github.com/"* ]]; then
    echo "github"
  elif [[ $remote_url == *"bitbucket.org"* ]] || [[ $remote_url == *"bitbucket.com"* ]]; then
    echo "bitbucket"
  else
    echo "ERROR: Could not detect platform from remote URL: $remote_url" >&2
    exit 1
  fi
}

# Extract owner and repo from git remote URL
# Handles both HTTPS (https://github.com/owner/repo.git) and SSH (git@github.com:owner/repo.git)
extract_owner_repo() {
  local remote_url
  remote_url=$(git config --get remote.origin.url)
  
  # Remove .git suffix if present
  remote_url="${remote_url%.git}"
  
  # Extract from HTTPS URL
  if [[ $remote_url =~ https?://[^/]+/([^/]+)/(.+)$ ]]; then
    echo "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
  # Extract from SSH URL
  elif [[ $remote_url =~ git@[^:]+:([^/]+)/(.+)$ ]]; then
    echo "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
  else
    echo "ERROR: Could not parse owner/repo from remote URL: $remote_url" >&2
    exit 1
  fi
}

# Get authentication token based on platform
get_auth_token() {
  local platform=$1
  if [[ "$platform" == "github" ]]; then
    if [[ -z "${GITHUB_TOKEN:-}" ]]; then
      echo "ERROR: GITHUB_TOKEN environment variable not set" >&2
      exit 1
    fi
    echo "$GITHUB_TOKEN"
  elif [[ "$platform" == "bitbucket" ]]; then
    if [[ -z "${BITBUCKET_TOKEN:-}" ]]; then
      echo "ERROR: BITBUCKET_TOKEN environment variable not set" >&2
      exit 1
    fi
    echo "$BITBUCKET_TOKEN"
  fi
}

# Build GitHub PR payload
build_github_payload() {
  local title=$1 body=$2 base=$3 draft=$4 labels=$5
  
  local payload
  payload=$(jq -n \
    --arg title "$title" \
    --arg body "$body" \
    --arg base "$base" \
    --argjson draft "$draft" \
    '{
      title: $title,
      body: $body,
      head: env.CURRENT_BRANCH,
      draft: $draft
    }')
  
  # Add base if provided
  if [[ -n "$base" ]]; then
    payload=$(echo "$payload" | jq --arg base "$base" '.base = $base')
  fi
  
  # Add labels if provided
  if [[ -n "$labels" ]]; then
    local labels_array
    labels_array=$(echo "$labels" | jq -R 'split(",")')
    payload=$(echo "$payload" | jq --argjson labels "$labels_array" '.labels = $labels')
  fi
  
  echo "$payload"
}

# Build Bitbucket PR payload
build_bitbucket_payload() {
  local title=$1 body=$2 base=$3
  
  jq -n \
    --arg title "$title" \
    --arg body "$body" \
    --arg source_branch "$CURRENT_BRANCH" \
    --arg dest_branch "$base" \
    '{
      title: $title,
      description: $body,
      source: {
        branch: {
          name: $source_branch
        }
      },
      destination: {
        branch: {
          name: $dest_branch
        }
      }
    }'
}

# Create GitHub PR via REST API
create_github_pr() {
  local owner_repo=$1 token=$2 title=$3 body=$4 base=$5 draft=$6 labels=$7
  
  local payload
  payload=$(build_github_payload "$title" "$body" "$base" "$draft" "$labels")
  
  local response
  response=$(curl -s -w "\n%{http_code}" -X POST \
    "https://api.github.com/repos/${owner_repo}/pulls" \
    -H "Authorization: token $token" \
    -H "Accept: application/vnd.github.v3+json" \
    -d "$payload")
  
  local http_code
  http_code=$(echo "$response" | tail -n1)
  local body_response
  body_response=$(echo "$response" | head -n-1)
  
  if [[ "$http_code" != "201" ]]; then
    echo "ERROR: GitHub API returned HTTP $http_code" >&2
    echo "$body_response" | jq . 2>/dev/null || echo "$body_response" >&2
    exit 1
  fi
  
  echo "$body_response" | jq -r '.html_url'
}

# Create Bitbucket PR via REST API
create_bitbucket_pr() {
  local owner_repo=$1 token=$2 title=$3 body=$4 base=$5
  
  local payload
  payload=$(build_bitbucket_payload "$title" "$body" "$base")
  
  local response
  response=$(curl -s -w "\n%{http_code}" -X POST \
    "https://api.bitbucket.org/2.0/repositories/${owner_repo}/pullrequests" \
    -u "x-token-auth:$token" \
    -H "Content-Type: application/json" \
    -d "$payload")
  
  local http_code
  http_code=$(echo "$response" | tail -n1)
  local body_response
  body_response=$(echo "$response" | head -n-1)
  
  if [[ "$http_code" != "201" ]]; then
    echo "ERROR: Bitbucket API returned HTTP $http_code" >&2
    echo "$body_response" | jq . 2>/dev/null || echo "$body_response" >&2
    exit 1
  fi
  
  echo "$body_response" | jq -r '.links.self[0].href'
}

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --title)
      TITLE="$2"; shift 2 ;;
    --body)
      BODY="$2"; shift 2 ;;
    --body-file)
      if [[ ! -f "$2" ]]; then
        echo "ERROR: Body file not found: $2" >&2
        exit 1
      fi
      BODY=$(cat "$2"); shift 2 ;;
    --base)
      BASE="$2"; shift 2 ;;
    --labels)
      LABELS="$2"; shift 2 ;;
    --draft)
      DRAFT=true; shift ;;
    --dry-run)
      DRY_RUN=true; shift ;;
    -h|--help)
      usage ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      usage ;;
  esac
done

# Validate required fields
if [[ -z "$TITLE" ]]; then
  echo "ERROR: --title is required" >&2
  exit 1
fi

if [[ -z "$BODY" ]]; then
  echo "ERROR: --body or --body-file is required" >&2
  exit 1
fi

# Get platform and repository info
PLATFORM=$(detect_platform)
OWNER_REPO=$(extract_owner_repo)
CURRENT_BRANCH=$(git branch --show-current)
TOKEN=$(get_auth_token "$PLATFORM")

# Display dry-run info or execute
if [[ "$DRY_RUN" == true ]]; then
  echo "=== DRY RUN ==="
  echo "Platform: $PLATFORM"
  echo "Repository: $OWNER_REPO"
  echo "Title: $TITLE"
  echo "Branch: $CURRENT_BRANCH → ${BASE:-<default>}"
  if [[ -n "$LABELS" ]]; then
    echo "Labels: $LABELS"
  fi
  if [[ "$DRAFT" == true ]]; then
    echo "Draft: true"
  fi
  echo ""
  echo "Body:"
  echo "$BODY"
  echo ""
  if [[ "$PLATFORM" == "github" ]]; then
    echo "API Call: POST https://api.github.com/repos/${OWNER_REPO}/pulls"
    build_github_payload "$TITLE" "$BODY" "$BASE" "$DRAFT" "$LABELS" | jq .
  else
    echo "API Call: POST https://api.bitbucket.org/2.0/repositories/${OWNER_REPO}/pullrequests"
    build_bitbucket_payload "$TITLE" "$BODY" "$BASE" | jq .
  fi
else
  if [[ "$PLATFORM" == "github" ]]; then
    PR_URL=$(create_github_pr "$OWNER_REPO" "$TOKEN" "$TITLE" "$BODY" "$BASE" "$DRAFT" "$LABELS")
  else
    PR_URL=$(create_bitbucket_pr "$OWNER_REPO" "$TOKEN" "$TITLE" "$BODY" "$BASE")
  fi
  echo "$PR_URL"
fi
