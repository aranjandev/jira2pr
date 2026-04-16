---
description: "Project coding standards and conventions for source code files. Covers naming, formatting, error handling, testing, and architectural patterns."
applyTo: "**/*.{ts,tsx,js,jsx,py,java,go,rs,rb,cs,kt,swift}"
---

<!-- CUSTOMIZE: Replace the content below with your actual project coding standards. These instructions auto-attach whenever the agent edits source files matching the applyTo glob above. Adjust the glob pattern to match your project's languages. -->

# Coding Standards

## Naming Conventions

<!-- CUSTOMIZE: Define your naming rules -->
- Files: <!-- e.g., kebab-case for TS, snake_case for Python -->
- Classes/Types: <!-- e.g., PascalCase -->
- Functions/Methods: <!-- e.g., camelCase for TS, snake_case for Python -->
- Constants: <!-- e.g., UPPER_SNAKE_CASE -->
- Private members: <!-- e.g., prefixed with _, no prefix -->

## Code Organization

<!-- CUSTOMIZE: Define your file structure rules -->
- Imports: <!-- e.g., stdlib → third-party → local, sorted alphabetically -->
- Export style: <!-- e.g., named exports only, no default exports -->
- Max file length: <!-- e.g., ~300 lines, split if larger -->

## Error Handling

<!-- CUSTOMIZE: Define your error handling patterns -->
- Pattern: <!-- e.g., Result types, try/catch, error returns -->
- External calls: <!-- e.g., always wrap in try/catch with typed errors -->
- User-facing errors: <!-- e.g., use error codes, never expose stack traces -->

## Testing

<!-- CUSTOMIZE: Define your testing standards -->
- Framework: <!-- e.g., Jest, pytest, JUnit -->
- Location: <!-- e.g., co-located as *.test.ts, separate tests/ directory -->
- Coverage expectations: <!-- e.g., new code must have tests, aim for >80% -->
- Test naming: <!-- e.g., "should <expected behavior> when <condition>" -->

## Patterns to Follow

<!-- CUSTOMIZE: List patterns specific to your project -->
- <!-- e.g., Use repository pattern for data access -->
- <!-- e.g., Use dependency injection, no service locators -->
- <!-- e.g., All API responses wrap in { data, error, meta } -->

## Anti-Patterns to Avoid

<!-- CUSTOMIZE: List things the agent should never do -->
- <!-- e.g., No any types in TypeScript -->
- <!-- e.g., No string concatenation for SQL queries -->
- <!-- e.g., No console.log in production code (use logger) -->
