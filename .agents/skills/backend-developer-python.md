---
name: backend-developer-python
description: Builds and modifies backend application code, with Python as the default backend language. Use when implementing APIs, services, database models, business logic, integrations, background jobs, validation, migrations, or backend tests.
---

# Backend Developer — Python

## Overview

Build reliable, maintainable backend code using the project's existing Python stack. Do not assume the framework until the repository has been inspected. The backend may use FastAPI, Django, Flask, Starlette, Celery, SQLAlchemy, Django ORM, Pydantic, or another Python ecosystem.

The goal is stable behavior, clear boundaries, explicit validation, predictable APIs, and testable business logic.

## Instruction Priority

Project-specific instructions have higher priority than this skill.

When working in a repository, always check and follow:

1. `AGENTS.md`
2. Canonical project documentation
3. Existing codebase conventions
4. This skill

If this skill conflicts with `AGENTS.md`, canonical documentation, or established repository patterns, follow the project-specific source instead.

## When to Use

Use this skill when:

- Implementing or modifying backend APIs
- Creating service-layer business logic
- Working with database models, migrations, or queries
- Adding background jobs or scheduled tasks
- Integrating with external APIs
- Implementing authentication or authorization logic
- Adding backend validation
- Writing backend tests
- Fixing backend bugs

## First Step: Discover the Backend Stack

Before writing code, inspect the project for:

- Framework: FastAPI, Django, Flask, Starlette, or other
- Runtime style: sync, async, or mixed
- Data validation: Pydantic, serializers, dataclasses, custom validators
- Database access: SQLAlchemy, Django ORM, raw SQL, repository layer
- Migration system: Alembic, Django migrations, custom migrations
- Dependency injection or service wiring
- Test framework: pytest, unittest, Django test runner, factory libraries
- API style: REST, GraphQL, RPC, internal service calls
- Existing error response format
- Existing logging and observability patterns

Follow existing project conventions unless there is a clear reason not to.

## Core Principles

### 1. Contract First

Define the API or interface contract before implementation.

For APIs, clarify:

- Request shape
- Response shape
- Status codes
- Error format
- Authentication and authorization requirements
- Pagination/filtering behavior
- Idempotency expectations
- Backward compatibility constraints

Avoid changing existing public contracts unless the task explicitly requires it.

### 2. Validate at System Boundaries

Validate data where it enters the system:

- HTTP request bodies
- Query parameters
- Path parameters
- Environment/configuration values
- Webhook payloads
- External API responses
- Queue messages
- File imports

Internal functions may trust already-validated typed data.

External API responses are untrusted. Validate or normalize them before using them in business logic.

### 3. Keep Business Logic Out of Route Handlers

Route/controller handlers should be thin:

- Parse and validate input
- Call application/service logic
- Translate results into responses
- Handle expected errors consistently

Business rules belong in services, domain modules, or use-case functions that are easy to test without HTTP.

### 4. Use Predictable Error Semantics

Errors should be explicit and consistent.

Define clear behavior for:

- Validation errors
- Authentication failures
- Authorization failures
- Not found errors
- Conflict errors
- External service failures
- Unexpected server errors

Never expose internal stack traces, secrets, SQL errors, or implementation details to clients.

### 5. Respect Sync/Async Boundaries

Do not mix sync and async carelessly.

- Avoid blocking I/O inside async request handlers
- Use the project's existing database/session pattern
- Keep transaction boundaries explicit
- Avoid fire-and-forget tasks unless the project has a safe background execution mechanism
- Make retries and timeouts explicit for external calls

### 6. Database Changes Must Be Safe

For database work:

- Use migrations
- Preserve existing data unless explicitly instructed otherwise
- Consider backward-compatible rollout order
- Add indexes for new query patterns when needed
- Avoid unbounded queries
- Avoid N+1 query patterns
- Keep transactions as small as practical
- Make destructive changes explicit

### 7. Security Is Part of Backend Work

Check for:

- Missing authorization
- Insecure direct object references
- SQL injection
- Unsafe deserialization
- Secret leakage
- Overly broad data exposure
- Missing rate limits where abuse is plausible
- Unsafe file handling
- Trusting client-provided identity or permissions

Authentication proves who the user is. Authorization proves what they may do. Implement both where required.

## Python Code Quality

Prefer:

- Clear function names
- Typed function signatures where the project uses typing
- Small functions with focused responsibilities
- Explicit exceptions for expected failure modes
- Dependency injection or explicit parameters over hidden globals
- Pure functions for business rules where possible
- Structured logging instead of print statements

Avoid:

- Large route handlers
- Broad `except Exception` blocks that hide failures
- Silent fallbacks
- Mutable default arguments
- Global state for request-specific data
- Copy-pasted validation logic
- Adding dependencies without strong justification

## Testing Expectations

Add or update tests for backend behavior changes.

Useful backend tests include:

- Unit tests for business logic
- API tests for request/response behavior
- Authorization tests
- Validation tests
- Database integration tests where queries or migrations change
- Regression tests for bug fixes
- External API integration tests using mocks/fakes

Tests should verify behavior, not implementation details.

## Completion Checklist

Before considering backend work complete:

- [ ] Existing Python backend conventions were followed
- [ ] API/interface contract is explicit
- [ ] Input validation exists at system boundaries
- [ ] Authorization is handled where needed
- [ ] Error behavior is consistent with the project
- [ ] Database queries are bounded and efficient
- [ ] Migrations are included for schema changes
- [ ] External calls have timeout/error handling
- [ ] Tests were added or updated
- [ ] Lint/typecheck/test commands pass, if available
