#!/usr/bin/env bash
# pr_helper.sh — Create or update Pull Requests on GitHub or Bitbucket via REST APIs.
# Usage: ./pr_helper.sh <command> [options]
# Commands: create, update, fetch-body
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

# ─── Defaults ────────────────────────────────────────────────────────────────
COMMAND=""
TITLE=""
BODY=""
BASE=""
LABELS=""
DRAFT=false
UNDRAFT=false
DRY_RUN=false
PR_NUMBER=""

# ─── Usage ───────────────────────────────────────────────────────────────────
usage() {
  cat <<'EOF'
Usage: pr_helper.sh <command> [options]

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
  pr_helper.sh create --title "feat: add auth" --body "..." --draft --labels "feature"
  pr_helper.sh update --pr-number 42 --body-file /tmp/pr_body.md
  pr_helper.sh update --pr-number 42 --body-file /tmp/pr_body.md --undraft
  pr_helper.sh fetch-body --pr-number 42
EOF
  exit 1
}

# ─── Validate dependencies ──────────────────────────────────────────────────
for cmd in curl git jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: $cmd is required but not installed." >&2
    exit 1
  fi
done

# ─── Shared helpers ─────────────────────────────────────────────────────────

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

extract_owner_repo() {
  local remote_url
  remote_url=$(git config --get remote.origin.url)
  remote_url="${remote_url%.git}"

  if [[ $remote_url =~ https?://[^/]+/([^/]+)/(.+)$ ]]; then
    echo "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
  elif [[ $remote_url =~ git@[^:]+:([^/]+)/(.+)$ ]]; then
    echo "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
  else
    echo "ERROR: Could not parse owner/repo from remote URL: $remote_url" >&2
    exit 1
  fi
}

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

# ─── CREATE helpers ──────────────────────────────────────────────────────────

build_github_create_payload() {
  local title=$1 body=$2 base=$3 draft=$4 labels=$5

  local payload
  payload=$(jq -n \
    --arg title "$title" \
    --arg body "$body" \
    --arg head "$CURRENT_BRANCH" \
    --argjson draft "$draft" \
    '{title: $title, body: $body, head: $head, draft: $draft}')

  if [[ -n "$base" ]]; then
    payload=$(echo "$payload" | jq --arg base "$base" '.base = $base')
  fi

  if [[ -n "$labels" ]]; then
    local labels_array
    labels_array=$(echo "$labels" | jq -R 'split(",")')
    payload=$(echo "$payload" | jq --argjson labels "$labels_array" '.labels = $labels')
  fi

  echo "$payload"
}

build_bitbucket_create_payload() {
  local title=$1 body=$2 base=$3

  jq -n \
    --arg title "$title" \
    --arg body "$body" \
    --arg source_branch "$CURRENT_BRANCH" \
    --arg dest_branch "$base" \
    '{
      title: $title,
      description: $body,
      source: { branch: { name: $source_branch } },
      destination: { branch: { name: $dest_branch } }
    }'
}

create_github_pr() {
  local owner_repo=$1 token=$2 title=$3 body=$4 base=$5 draft=$6 labels=$7

  local payload
  payload=$(build_github_create_payload "$title" "$body" "$base" "$draft" "$labels")

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

  local pr_url pr_number
  pr_url=$(echo "$body_response" | jq -r '.html_url')
  pr_number=$(echo "$body_response" | jq -r '.number')
  echo "PR_URL=${pr_url}"
  echo "PR_NUMBER=${pr_number}"
}

create_bitbucket_pr() {
  local owner_repo=$1 token=$2 title=$3 body=$4 base=$5

  local payload
  payload=$(build_bitbucket_create_payload "$title" "$body" "$base")

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

  local pr_url pr_id
  pr_url=$(echo "$body_response" | jq -r '.links.html.href // .links.self[0].href')
  pr_id=$(echo "$body_response" | jq -r '.id')
  echo "PR_URL=${pr_url}"
  echo "PR_NUMBER=${pr_id}"
}

# ─── UPDATE helpers ──────────────────────────────────────────────────────────

update_github_pr() {
  local owner_repo=$1 token=$2 pr_number=$3 body=$4 title=$5

  local payload
  payload=$(jq -n --arg body "$body" '{body: $body}')
  if [[ -n "$title" ]]; then
    payload=$(echo "$payload" | jq --arg title "$title" '.title = $title')
  fi

  local response
  response=$(curl -s -w "\n%{http_code}" -X PATCH \
    "https://api.github.com/repos/${owner_repo}/pulls/${pr_number}" \
    -H "Authorization: token $token" \
    -H "Accept: application/vnd.github.v3+json" \
    -d "$payload")

  local http_code
  http_code=$(echo "$response" | tail -n1)
  local body_response
  body_response=$(echo "$response" | head -n-1)

  if [[ "$http_code" != "200" ]]; then
    echo "ERROR: GitHub API returned HTTP $http_code" >&2
    echo "$body_response" | jq . 2>/dev/null || echo "$body_response" >&2
    exit 1
  fi

  echo "PR_URL=$(echo "$body_response" | jq -r '.html_url')"
}

undraft_github_pr() {
  local owner_repo=$1 token=$2 pr_number=$3

  # GitHub REST API does not support setting draft=false.
  # We must use the GraphQL API with the pull request's node_id.

  # Step 1: fetch the node_id via REST
  local response
  response=$(curl -s -w "\n%{http_code}" \
    "https://api.github.com/repos/${owner_repo}/pulls/${pr_number}" \
    -H "Authorization: token $token" \
    -H "Accept: application/vnd.github.v3+json")

  local http_code
  http_code=$(echo "$response" | tail -n1)
  local body_response
  body_response=$(echo "$response" | head -n-1)

  if [[ "$http_code" != "200" ]]; then
    echo "ERROR: Could not fetch PR node_id. GitHub API returned HTTP $http_code" >&2
    echo "$body_response" | jq . 2>/dev/null || echo "$body_response" >&2
    exit 1
  fi

  local node_id
  node_id=$(echo "$body_response" | jq -r '.node_id')
  if [[ -z "$node_id" || "$node_id" == "null" ]]; then
    echo "ERROR: Could not extract node_id from PR response" >&2
    exit 1
  fi

  # Step 2: call GraphQL markPullRequestReadyForReview
  local gql_payload
  gql_payload=$(jq -n --arg id "$node_id" \
    '{query: "mutation($id: ID!) { markPullRequestReadyForReview(input: {pullRequestId: $id}) { pullRequest { isDraft } } }", variables: {id: $id}}')

  local gql_response
  gql_response=$(curl -s -w "\n%{http_code}" -X POST \
    "https://api.github.com/graphql" \
    -H "Authorization: bearer $token" \
    -H "Content-Type: application/json" \
    -d "$gql_payload")

  local gql_http_code
  gql_http_code=$(echo "$gql_response" | tail -n1)
  local gql_body
  gql_body=$(echo "$gql_response" | head -n-1)

  if [[ "$gql_http_code" != "200" ]]; then
    echo "ERROR: GraphQL undraft returned HTTP $gql_http_code" >&2
    echo "$gql_body" | jq . 2>/dev/null || echo "$gql_body" >&2
    exit 1
  fi

  # Check for GraphQL-level errors
  local gql_errors
  gql_errors=$(echo "$gql_body" | jq -r '.errors // empty')
  if [[ -n "$gql_errors" && "$gql_errors" != "null" ]]; then
    echo "ERROR: GraphQL undraft mutation failed" >&2
    echo "$gql_body" | jq . >&2
    exit 1
  fi

  echo "OK: PR #${pr_number} marked as ready for review"
}

update_bitbucket_pr() {
  local owner_repo=$1 token=$2 pr_number=$3 body=$4 title=$5

  local payload
  payload=$(jq -n --arg body "$body" '{description: $body}')
  if [[ -n "$title" ]]; then
    payload=$(echo "$payload" | jq --arg title "$title" '.title = $title')
  fi

  local response
  response=$(curl -s -w "\n%{http_code}" -X PUT \
    "https://api.bitbucket.org/2.0/repositories/${owner_repo}/pullrequests/${pr_number}" \
    -u "x-token-auth:$token" \
    -H "Content-Type: application/json" \
    -d "$payload")

  local http_code
  http_code=$(echo "$response" | tail -n1)
  local body_response
  body_response=$(echo "$response" | head -n-1)

  if [[ "$http_code" != "200" ]]; then
    echo "ERROR: Bitbucket API returned HTTP $http_code" >&2
    echo "$body_response" | jq . 2>/dev/null || echo "$body_response" >&2
    exit 1
  fi

  local pr_url
  pr_url=$(echo "$body_response" | jq -r '.links.html.href // .links.self[0].href')
  echo "PR_URL=${pr_url}"
}

# ─── FETCH-BODY helper ──────────────────────────────────────────────────────

fetch_github_pr_body() {
  local owner_repo=$1 token=$2 pr_number=$3

  local response
  response=$(curl -s -w "\n%{http_code}" \
    "https://api.github.com/repos/${owner_repo}/pulls/${pr_number}" \
    -H "Authorization: token $token" \
    -H "Accept: application/vnd.github.v3+json")

  local http_code
  http_code=$(echo "$response" | tail -n1)
  local body_response
  body_response=$(echo "$response" | head -n-1)

  if [[ "$http_code" != "200" ]]; then
    echo "ERROR: GitHub API returned HTTP $http_code" >&2
    echo "$body_response" | jq . 2>/dev/null || echo "$body_response" >&2
    exit 1
  fi

  echo "$body_response" | jq -r '.body'
}

fetch_bitbucket_pr_body() {
  local owner_repo=$1 token=$2 pr_number=$3

  local response
  response=$(curl -s -w "\n%{http_code}" \
    "https://api.bitbucket.org/2.0/repositories/${owner_repo}/pullrequests/${pr_number}" \
    -u "x-token-auth:$token" \
    -H "Content-Type: application/json")

  local http_code
  http_code=$(echo "$response" | tail -n1)
  local body_response
  body_response=$(echo "$response" | head -n-1)

  if [[ "$http_code" != "200" ]]; then
    echo "ERROR: Bitbucket API returned HTTP $http_code" >&2
    echo "$body_response" | jq . 2>/dev/null || echo "$body_response" >&2
    exit 1
  fi

  echo "$body_response" | jq -r '.description'
}

# ─── Parse command ───────────────────────────────────────────────────────────

if [[ $# -eq 0 ]]; then
  usage
fi

COMMAND="$1"
shift

case "$COMMAND" in
  create|update|fetch-body) ;;
  -h|--help) usage ;;
  *)
    echo "ERROR: Unknown command: $COMMAND" >&2
    echo "Valid commands: create, update, fetch-body" >&2
    exit 1
    ;;
esac

# ─── Parse options ───────────────────────────────────────────────────────────

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
    --undraft)
      UNDRAFT=true; shift ;;
    --pr-number)
      PR_NUMBER="$2"; shift 2 ;;
    --dry-run)
      DRY_RUN=true; shift ;;
    -h|--help)
      usage ;;
    *)
      echo "ERROR: Unknown option: $1" >&2
      usage ;;
  esac
done

# ─── Validate per-command requirements ───────────────────────────────────────

case "$COMMAND" in
  create)
    if [[ -z "$TITLE" ]]; then
      echo "ERROR: --title is required for create" >&2
      exit 1
    fi
    if [[ -z "$BODY" ]]; then
      echo "ERROR: --body or --body-file is required for create" >&2
      exit 1
    fi
    ;;
  update)
    if [[ -z "$PR_NUMBER" ]]; then
      echo "ERROR: --pr-number is required for update" >&2
      exit 1
    fi
    if [[ -z "$BODY" && "$UNDRAFT" == false && -z "$TITLE" ]]; then
      echo "ERROR: --body, --body-file, --title, or --undraft is required for update" >&2
      exit 1
    fi
    ;;
  fetch-body)
    if [[ -z "$PR_NUMBER" ]]; then
      echo "ERROR: --pr-number is required for fetch-body" >&2
      exit 1
    fi
    ;;
esac

# ─── Resolve platform context ───────────────────────────────────────────────

PLATFORM=$(detect_platform)
OWNER_REPO=$(extract_owner_repo)
CURRENT_BRANCH=$(git branch --show-current)
TOKEN=$(get_auth_token "$PLATFORM")

# ─── Execute command ─────────────────────────────────────────────────────────

case "$COMMAND" in

  # ── CREATE ───────────────────────────────────────────────────────────────
  create)
    if [[ "$DRY_RUN" == true ]]; then
      echo "=== DRY RUN: create ==="
      echo "Platform: $PLATFORM"
      echo "Repository: $OWNER_REPO"
      echo "Title: $TITLE"
      echo "Branch: $CURRENT_BRANCH → ${BASE:-<default>}"
      [[ -n "$LABELS" ]] && echo "Labels: $LABELS"
      [[ "$DRAFT" == true ]] && echo "Draft: true"
      echo ""
      echo "Body:"
      echo "$BODY"
      echo ""
      if [[ "$PLATFORM" == "github" ]]; then
        echo "API Call: POST https://api.github.com/repos/${OWNER_REPO}/pulls"
        build_github_create_payload "$TITLE" "$BODY" "$BASE" "$DRAFT" "$LABELS" | jq .
      else
        echo "API Call: POST https://api.bitbucket.org/2.0/repositories/${OWNER_REPO}/pullrequests"
        build_bitbucket_create_payload "$TITLE" "$BODY" "$BASE" | jq .
      fi
    else
      if [[ "$PLATFORM" == "github" ]]; then
        create_github_pr "$OWNER_REPO" "$TOKEN" "$TITLE" "$BODY" "$BASE" "$DRAFT" "$LABELS"
      else
        create_bitbucket_pr "$OWNER_REPO" "$TOKEN" "$TITLE" "$BODY" "$BASE"
      fi
    fi
    ;;

  # ── UPDATE ───────────────────────────────────────────────────────────────
  update)
    if [[ "$DRY_RUN" == true ]]; then
      echo "=== DRY RUN: update ==="
      echo "Platform: $PLATFORM"
      echo "Repository: $OWNER_REPO"
      echo "PR Number: $PR_NUMBER"
      [[ -n "$TITLE" ]] && echo "New Title: $TITLE"
      [[ "$UNDRAFT" == true ]] && echo "Undraft: true"
      if [[ -n "$BODY" ]]; then
        echo ""
        echo "New Body:"
        echo "$BODY"
      fi
      echo ""
      if [[ "$PLATFORM" == "github" ]]; then
        echo "API Call: PATCH https://api.github.com/repos/${OWNER_REPO}/pulls/${PR_NUMBER}"
        [[ "$UNDRAFT" == true ]] && echo "API Call: POST https://api.github.com/graphql (markPullRequestReadyForReview)"
      else
        echo "API Call: PUT https://api.bitbucket.org/2.0/repositories/${OWNER_REPO}/pullrequests/${PR_NUMBER}"
      fi
    else
      # Update body/title if provided
      if [[ -n "$BODY" || -n "$TITLE" ]]; then
        if [[ "$PLATFORM" == "github" ]]; then
          update_github_pr "$OWNER_REPO" "$TOKEN" "$PR_NUMBER" "$BODY" "$TITLE"
        else
          update_bitbucket_pr "$OWNER_REPO" "$TOKEN" "$PR_NUMBER" "$BODY" "$TITLE"
        fi
      fi
      # Undraft if requested (GitHub only; Bitbucket has no draft concept)
      if [[ "$UNDRAFT" == true ]]; then
        if [[ "$PLATFORM" == "github" ]]; then
          undraft_github_pr "$OWNER_REPO" "$TOKEN" "$PR_NUMBER"
        else
          echo "WARN: --undraft is not supported on Bitbucket (no draft concept)" >&2
        fi
      fi
    fi
    ;;

  # ── FETCH-BODY ─────────────────────────────────────────────────────────
  fetch-body)
    if [[ "$DRY_RUN" == true ]]; then
      echo "=== DRY RUN: fetch-body ==="
      echo "Platform: $PLATFORM"
      echo "Repository: $OWNER_REPO"
      echo "PR Number: $PR_NUMBER"
      if [[ "$PLATFORM" == "github" ]]; then
        echo "API Call: GET https://api.github.com/repos/${OWNER_REPO}/pulls/${PR_NUMBER}"
      else
        echo "API Call: GET https://api.bitbucket.org/2.0/repositories/${OWNER_REPO}/pullrequests/${PR_NUMBER}"
      fi
    else
      if [[ "$PLATFORM" == "github" ]]; then
        fetch_github_pr_body "$OWNER_REPO" "$TOKEN" "$PR_NUMBER"
      else
        fetch_bitbucket_pr_body "$OWNER_REPO" "$TOKEN" "$PR_NUMBER"
      fi
    fi
    ;;

esac
