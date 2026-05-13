# AGENTS

## Purpose

This file is the bootstrap entry point for AI agents working in the `api` repository.

It defines the canonical API documentation set, the local source-of-truth order, and the backend-specific execution constraints.

## Canonical Language

Use only English project documents as execution context.

Do not rely on Russian companion documents for implementation decisions.

## Required Reading Order

Before any non-trivial API task, read:

1. The current approved task artifact:
   - issue
   - change request
   - sprint task
   - explicitly approved task comment
2. [docs/api_architecture.md](./docs/api_architecture.md)
3. Repository-specific operational and domain documents when they exist:
   - `docs/auth.md`
   - `docs/ci-cd.md`
   - API testing strategy documents in `docs/`
4. Monorepo-level project documents when this repository is checked out inside the mono repository:
   - [../docs/requirements.md](../docs/requirements.md)
   - [../docs/project.md](../docs/project.md)
   - [../docs/system_architecture.md](../docs/system_architecture.md)
   - [../docs/tech_stack.md](../docs/tech_stack.md)
   - [../docs/qa-plan.md](../docs/qa-plan.md)
5. The actual API code, tests, migrations, and existing patterns
6. Relevant skill files in `.agent/skills/` or `.agents/` when the current task explicitly matches that skill

## Source of Truth Order

When sources conflict, use this precedence:

1. Current approved task artifact
2. `../docs/requirements.md` when available
3. `./docs/api_architecture.md`
4. Monorepo system-level documents when available
5. Local auth, CI/CD, and testing documents when present
6. Existing API code, tests, and migrations

## Mandatory API Rules

- Follow `feature-driven architecture with internal layers`.
- Keep the API under the `/api/v1` contract.
- Keep `auth`, `notebooks`, `ai`, and `system` as the main backend features.
- Treat `sync` as part of the `notebooks` feature.
- Keep notebook persistence aligned with the `JSONB` snapshot model.
- Keep sync aligned with whole-notebook snapshot exchange, `base_revision`, and `409 Conflict`.
- Preserve the documented `Email + OTP` and `Google OAuth` authentication model.
- Preserve secure `HTTP-only` session-cookie auth state.
- Validate data at system boundaries.
- Keep business logic out of route handlers.
- Add migrations for schema changes.
- Do not add backend dependencies without approval.
- Add or update backend tests for behavior changes.
- Run relevant lint, type, test, and migration verification before claiming completion.

## Supplemental Agent Instructions

Skill files under `.agent/skills/` or `.agents/` are supplemental execution aids.

They do not override task scope, project requirements, or architecture documents.

## Related Documents

- [docs/api_architecture.md](./docs/api_architecture.md)
- [../docs/requirements.md](../docs/requirements.md)
- [../docs/system_architecture.md](../docs/system_architecture.md)
- [../docs/tech_stack.md](../docs/tech_stack.md)
