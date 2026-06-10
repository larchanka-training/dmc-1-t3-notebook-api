# API Architecture

## 1. Purpose

This document defines the architecture of the backend application.

It fixes:

- the backend role in the system
- the backend architectural style
- the main backend feature boundaries
- the backend persistence model
- the backend sync model
- the backend authentication model
- the backend AI integration model
- the fixed backend technology decisions for Version 1

## 2. Fixed Version 1 Decisions

The following backend decisions are fixed for Version 1:

1. The API uses `REST + HTTP + JSON` under the `/api/v1` prefix.
2. The backend architecture is `feature-driven with internal layers`.
3. The main backend features are `auth`, `notebooks`, `ai`, and `system`.
4. `sync` belongs to the `notebooks` feature and is not a separate top-level feature.
5. Shared backend structure is organized into `core`, `db`, `integrations`, and `features`.
6. Notebook content is stored in `PostgreSQL` as a `JSONB` snapshot.
7. Durable notebook metadata includes `id`, `owner_id`, `title`, `revision`, `created_at`, and `updated_at`.
8. The canonical notebook snapshot includes notebook-level `tags` and block-level `meta.tags` for both `text` and `code` blocks.
9. Notebook retrieval and sync responses return these tag lists as part of the notebook payload.
10. Runtime outputs are not stored as durable notebook state by default.
11. Synchronization uses whole-notebook snapshots with revision-based conflict detection and `409 Conflict`.
12. Authentication supports `Email + OTP` and `Google OAuth`.
13. Authenticated browser state uses a backend-managed secure `HTTP-only` session cookie.
14. In `local/dev`, OTP may be returned in the API response instead of using external email delivery.
15. AI code generation uses one block-oriented endpoint.
16. The data access layer uses `SQLAlchemy ORM`.
17. Database migrations use `Alembic`.
18. Version 1 uses `FastAPI BackgroundTasks` where background work is needed and does not introduce a dedicated job queue.

## 3. Backend Role in the System

The backend is the server-side boundary of a hosted web application with local-first behavior.

The backend is responsible for:

- authentication
- session lifecycle
- notebook persistence
- notebook retrieval
- notebook synchronization
- access control
- AI provider mediation
- operational endpoints
- external integration boundaries

The backend is not responsible for executing notebook `JavaScript`.

Notebook code executes in the browser runtime, while the backend remains the control, storage, and integration plane.

## 4. Backend Architectural Style

The backend uses `feature-driven architecture with internal layers`.

This means:

- the codebase is organized by business feature at the top level
- each feature owns its own API, schemas, service logic, and persistence logic
- shared infrastructure is extracted into shared backend modules

The backend does not use one global project-wide `routers`, `services`, or `repositories` directory as the primary architectural boundary.

## 5. Top-Level Backend Structure

The backend structure is:

```text
api/app/
  main.py
  core/
  db/
  integrations/
  features/
    auth/
    notebooks/
    ai/
    system/
```

### 5.1 `main.py`

`main.py` is responsible for:

- application bootstrap
- middleware registration
- router registration
- application lifecycle wiring

### 5.2 `core/`

`core/` contains shared backend application logic such as:

- configuration
- security helpers
- shared errors
- logging
- common dependency wiring

### 5.3 `db/`

`db/` contains shared database infrastructure such as:

- database session management
- ORM base configuration
- migration configuration
- shared database helpers

### 5.4 `integrations/`

`integrations/` contains provider-facing integration code such as:

- email delivery
- LLM provider access
- Google OAuth provider integration

### 5.5 `features/`

`features/` contains the business feature modules:

- `auth`
- `notebooks`
- `ai`
- `system`

## 6. Feature Module Internal Structure

Each feature module follows the same internal layered pattern where needed:

```text
feature/
  router.py
  schemas.py
  service.py
  repository.py
  models.py
```

### 6.1 `router.py`

Responsible for:

- HTTP route definitions
- request parsing
- response shaping
- calling feature services

### 6.2 `schemas.py`

Responsible for:

- request DTOs
- response DTOs
- internal API validation models

### 6.3 `service.py`

Responsible for:

- feature business rules
- orchestration of repositories and integrations
- transaction-level application behavior

### 6.4 `repository.py`

Responsible for:

- data access
- persistence queries
- entity retrieval and mutation

### 6.5 `models.py`

Responsible for:

- ORM models owned by the feature
- database-level entity definitions

## 7. Feature Responsibilities

### 7.1 `auth`

The `auth` feature is responsible for:

- email OTP request and verification
- Google OAuth start and callback handling
- authenticated session creation
- authenticated session retrieval
- logout
- mapping external identity to internal user identity

### 7.2 `notebooks`

The `notebooks` feature is responsible for:

- notebook collection operations
- notebook item operations
- notebook durable storage
- notebook ownership enforcement
- notebook synchronization
- notebook revision management
- sync conflict detection

### 7.3 `ai`

The `ai` feature is responsible for:

- block-oriented AI generation requests
- passing notebook context to the LLM layer
- returning generated code for notebook insertion
- isolating provider-specific logic behind the backend boundary

### 7.4 `system`

The `system` feature is responsible for:

- health endpoints
- operational status endpoints
- infrastructure-facing lightweight service endpoints

## 8. API Route Groups

The API is grouped under `/api/v1`.

### 8.1 Auth Routes

Canonical auth routes:

- `POST /api/v1/auth/request-otp`
- `POST /api/v1/auth/verify-otp`
- `GET /api/v1/auth/session`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/google/start`
- `GET /api/v1/auth/google/callback`

### 8.2 Notebook Routes

Canonical notebook routes:

- `/api/v1/notebooks`
- `/api/v1/notebooks/{notebookId}`
- `/api/v1/notebooks/{notebookId}/sync`

The notebook feature exposes collection, item, and notebook-scoped synchronization endpoints.

### 8.3 AI Routes

Canonical AI route:

- `POST /api/v1/ai/code-blocks/generate`

This endpoint accepts:

- generation mode
- prompt
- current code block content
- relevant notebook context

### 8.4 System Routes

Canonical system route:

- `GET /api/v1/system/health`

## 9. Persistence Model

The backend persists the following core durable entities:

- `User`
- `AuthSession`
- `OtpChallenge`
- `OAuthAccount`
- `Notebook`

### 9.1 `User`

The `User` entity represents the internal authenticated product identity.

### 9.2 `AuthSession`

The `AuthSession` entity represents the backend-managed authenticated browser session.

### 9.3 `OtpChallenge`

The `OtpChallenge` entity represents one-time password issuance and verification state.

### 9.4 `OAuthAccount`

The `OAuthAccount` entity represents the link between a Google OAuth identity and the internal `User`.

### 9.5 `Notebook`

The `Notebook` entity stores:

- notebook metadata columns
- notebook content snapshot

The notebook content snapshot is stored as `JSONB`.

The durable notebook metadata is:

- `id`
- `owner_id`
- `title`
- `revision`
- `created_at`
- `updated_at`

Runtime outputs are not part of the durable notebook record by default.

## 10. Notebook Storage Model

Notebook persistence uses one durable notebook snapshot per synchronized revision.

The backend stores:

- notebook identity
- notebook ownership
- notebook title
- notebook-level `tags`
- notebook content as structured `JSONB`
- revision metadata
- created and updated timestamps

The backend does not decompose notebook blocks into a large multi-table block graph for Version 1.

Block-level tags remain part of the snapshot inside each block `meta` object.

## 11. Synchronization Model

Synchronization is notebook-scoped and snapshot-based.

The sync model works as follows:

1. The frontend sends a full notebook snapshot.
2. The frontend includes the notebook `base_revision`.
3. The backend compares the client revision with the durable server revision.
4. If the revisions match, the backend persists the new snapshot and increments the revision.
5. If the revisions do not match, the backend returns `409 Conflict`.

The backend does not perform automatic merge.

## 12. Authentication Architecture

The backend supports two sign-in flows:

- `Email + OTP`
- `Google OAuth`

Both sign-in flows produce the same authenticated browser session model:

- internal user identity
- backend-managed authenticated session
- secure `HTTP-only` session cookie

### 12.1 Email OTP Flow

The email OTP flow consists of:

- requesting an OTP
- creating an OTP challenge
- delivering the OTP through the email integration in deployed environments
- verifying the OTP
- creating the authenticated session

In `local/dev`, the backend may return the OTP in the API response for development use.

### 12.2 Google OAuth Flow

The Google OAuth flow consists of:

- starting Google sign-in through a backend route
- redirecting to the Google OAuth provider
- receiving the provider callback
- resolving or creating the internal user identity
- creating the authenticated session

## 13. AI Architecture

The backend mediates all access to the LLM provider.

The AI architecture works as follows:

1. The frontend sends a block-oriented request.
2. The backend validates the request payload.
3. The backend packages the relevant notebook context.
4. The backend calls the LLM integration.
5. The backend returns generated code to the frontend.

The backend returns code for direct insertion into the selected notebook block.

The backend does not expose provider credentials to the browser.

## 14. Integrations and Background Work

The backend integrates with:

- an email delivery provider
- an LLM provider
- Google OAuth

Provider-specific logic lives in `integrations/`.

Version 1 background work rules are:

- email delivery may use `FastAPI BackgroundTasks`
- AI requests remain synchronous backend operations
- the backend does not introduce a separate queue system

## 15. Security and Access Control

The backend enforces:

- authenticated access to private notebooks
- notebook ownership validation
- server-side session validation
- OTP verification rules
- OAuth state validation
- server-side protection of provider credentials

Notebook code and AI-generated code are treated as untrusted.

## 16. Error and Response Semantics

The backend uses standard HTTP response semantics.

The main response classes are:

- `200` and `201` for successful read and write operations
- `401` for unauthenticated access
- `403` for forbidden access
- `404` for missing resources
- `409` for sync conflicts
- `422` for invalid request payloads

## 17. Related Documents

- [system_architecture.md](../../docs/system_architecture.md)
- [tech_stack.md](../../docs/tech_stack.md)
- [ui_architecture.md](../../ui/docs/ui_architecture.md)
