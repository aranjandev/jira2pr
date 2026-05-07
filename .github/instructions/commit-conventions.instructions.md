---
description: "Conventional commit message format and rules for writing git commit messages. Covers type prefixes, scope conventions, body format, footer references, and breaking change notation."
---
# Commit Message Conventions

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

## Format

```
<type>(<scope>): <short description>

<optional body>

<optional footer(s)>
```

## Rules

### Header (first line)
- **Max 72 characters**
- **Lowercase** type and description (no capital first letter)
- **No period** at the end
- **Imperative mood**: "add feature" not "added feature" or "adds feature"

### Type
| Type | When to Use |
|------|-------------|
| `feat` | New feature or user-facing capability |
| `fix` | Bug fix |
| `refactor` | Code restructuring with no behavior change |
| `test` | Adding or updating tests only |
| `docs` | Documentation changes only |
| `chore` | Build scripts, CI config, tooling |
| `perf` | Performance improvement |
| `style` | Formatting, whitespace (no code change) |
| `ci` | CI/CD pipeline changes |

### Scope
- Use the component or module name: `auth`, `api`, `db`, `ui`
- Keep it short (1 word preferred)
- Omit if the change spans multiple components

### Body
- Separated from header by a blank line
- Explain **what** and **why**, not **how**
- Wrap at 72 characters

### Footer
- Reference JIRA tickets: `Refs: PROJ-123`
- Breaking changes: `BREAKING CHANGE: <description>`

## Examples

```
feat(auth): add JWT token refresh endpoint

Adds a /auth/refresh endpoint that accepts a valid refresh token
and returns a new access token. Tokens are validated against the
signing key before issuing a replacement.

Refs: PROJ-123
```

```
fix(api): handle null response from payment gateway

The payment gateway occasionally returns null instead of an error
object when the service is degraded. This adds a null check and
returns a structured error response.

Refs: PROJ-456
```

```
refactor(db): extract query builder from repository

Refs: PROJ-789
```

```
feat(api)!: change pagination response format

BREAKING CHANGE: pagination now uses cursor-based format instead of
offset-based. The response shape changes from { page, total } to
{ cursor, hasMore }.

Refs: PROJ-321
```
