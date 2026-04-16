# Project Instructions

<!-- CUSTOMIZE: Replace this entire file with your project-specific instructions. The sections below are templates — fill in each one with details relevant to your codebase. -->

## Code Style

<!-- CUSTOMIZE: Describe your language, formatting, and naming conventions. Reference key files that exemplify your patterns. -->

- Language: Shell script, Python <!-- e.g., TypeScript, Python, Java -->
- Formatter: <!-- e.g., Prettier, Black, google-java-format -->
- Linting: <!-- e.g., ESLint, Ruff, Checkstyle -->
- Key patterns to follow: see <!-- path/to/exemplary/file -->

## Architecture

<!-- CUSTOMIZE: Describe major components, service boundaries, and the reasoning behind structural decisions. -->

- Project type: <!-- e.g., monorepo, microservice, monolith -->
- Key directories:
  - `src/` — <!-- purpose -->
  - `tests/` — <!-- purpose -->
- Data flow: <!-- brief description of request lifecycle -->

## Build and Test

<!-- CUSTOMIZE: Commands the agent should use. Be explicit — agents will attempt to run these. -->

```bash
# Install dependencies
# <!-- e.g., npm install, pip install -r requirements.txt -->

# Run tests
# <!-- e.g., npm test, pytest -->

# Build
# <!-- e.g., npm run build, make -->

# Lint
# <!-- e.g., npm run lint, ruff check . -->
```

## Conventions

<!-- CUSTOMIZE: Patterns that differ from common practices. Include specific examples so the agent doesn't guess. -->

- Error handling: <!-- e.g., "Use Result types, never throw exceptions" -->
- API responses: <!-- e.g., "Always wrap in { data, error, meta } envelope" -->
- Database: <!-- e.g., "All queries go through the repository layer" -->
- Testing: <!-- e.g., "Unit tests co-located with source files as *.test.ts" -->

## Dependencies

<!-- CUSTOMIZE: Rules about adding or upgrading dependencies. -->

- Allowed package registries: <!-- e.g., npm, PyPI -->
- Approval required for new dependencies: <!-- yes/no, process -->
- Pinning strategy: <!-- e.g., exact versions, caret ranges -->

## Environment

<!-- CUSTOMIZE: Required environment variables and how to set them up. -->

- Required env vars for the agent tools:
  - `JIRA_API_TOKEN` — Personal access token for JIRA REST API
  - `JIRA_BASE_URL` — Base URL of your JIRA instance (e.g., `https://yourcompany.atlassian.net`)
  - GitHub CLI (`gh`) must be authenticated via `gh auth login`
