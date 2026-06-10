# API Persistence Contract

## 1. Purpose

This document defines the implementation-facing persistence and sync contract for notebook storage in Version 1.

Status:

- target contract for planned Version 1 implementation
- not a description of the current repository implementation state

It covers:

- durable notebook storage shape
- notebook JSON snapshot rules
- revision and sync behavior
- endpoint contracts for notebook persistence
- validation, access control, and conflict behavior

This document is aligned with:

- [../../dmc-1-t3-notebook-mono/docs/system_architecture.md](../../dmc-1-t3-notebook-mono/docs/system_architecture.md)
- [../../dmc-1-t3-notebook-mono/docs/tech_stack.md](../../dmc-1-t3-notebook-mono/docs/tech_stack.md)
- [./api_architecture.md](./api_architecture.md)

## 2. Fixed Contract for Version 1

The following persistence contract is fixed for Version 1:

1. The durable unit is the notebook document.
2. Canonical notebook content is structured `JSON`.
3. Server-side persistence uses `PostgreSQL`, with notebook content stored as `JSONB` snapshot.
4. Sync is explicit and user-initiated.
5. Sync conflicts are explicit and must not be auto-merged.
6. Access control is owner-only for notebooks.
7. Runtime outputs are not part of durable notebook state by default.

## 3. Common Conventions

### 3.1 Content Type

JSON endpoints use:

- request: `Content-Type: application/json`
- response: `Content-Type: application/json`

### 3.2 Authentication

All notebook endpoints require an authenticated session cookie.

Anonymous requests should receive:

- `401 Unauthorized`

Requests for notebooks not owned by the authenticated user should receive:

- `404 Not Found`

This follows the owner-only access model while avoiding existence disclosure for private notebook identifiers.

Alignment note:

- this contract fixes `404 Not Found` as the canonical API behavior for inaccessible private notebooks
- some higher-level or QA documents may still reference `403 Forbidden` for the same scenario
- such references should be treated as pending documentation alignment, not as the source of truth for the API contract

### 3.3 Time Values

Response fields such as `created_at`, `updated_at`, and `last_synced_at` should use ISO 8601 timestamps in UTC.

### 3.4 Error Shape

Recommended error response shape:

```json
{
  "error": {
    "code": "notebook_sync_conflict",
    "message": "The notebook was updated on the server."
  }
}
```

## 4. Durable Model Direction

### 4.1 `users`

Notebook ownership is anchored on the authenticated user.

Minimal user fields relevant to persistence:

- `id`
- `email`
- `created_at`
- `updated_at`

### 4.2 `notebooks`

Recommended notebook fields:

- `id`
- `owner_id`
- `title`
- `content_snapshot`
- `revision`
- `created_at`
- `updated_at`
- `last_synced_at` nullable
- optional `deleted_at` nullable if soft delete is chosen

### 4.3 `content_snapshot`

`content_snapshot` stores the canonical notebook document in `JSONB`.

The backend should persist the document shape close to the frontend canonical model.

## 5. Notebook JSON Shape

### 5.1 Recommended Snapshot Shape

```json
{
  "id": "7e7c6d72-124d-40db-8c03-42f0eab1f451",
  "title": "Notebook title",
  "tags": ["reference", "demo"],
  "blocks": [
    {
      "id": "block-1",
      "type": "text",
      "content": {
        "markdown": "# Heading"
      },
      "meta": {
        "tags": ["intro", "summary"]
      }
    },
    {
      "id": "block-2",
      "type": "code",
      "content": {
        "language": "javascript",
        "source": "const value = 1;"
      },
      "meta": {
        "tags": ["example", "javascript"]
      }
    }
  ],
  "metadata": {
    "version": 1
  }
}
```

### 5.2 Version 1 Rules

- `blocks` order is canonical and significant
- allowed block types are only `text` and `code`
- notebook root includes `tags` as a list of strings
- every block includes `meta.tags` as a list of strings regardless of block type
- `code` blocks use `javascript`
- execution outputs are not stored in the durable snapshot by default
- runtime session state is not part of notebook persistence

## 6. Revision and Sync Contract

### 6.1 Core Fields

- `revision`: latest accepted server revision for the notebook
- `base_revision`: revision the client local copy was based on

### 6.2 Successful Sync Rule

If:

- request `base_revision` matches current server `revision`

then the backend:

- accepts the new `content_snapshot`
- updates the notebook metadata
- increments `revision`
- returns the new revision and timestamps

### 6.3 Conflict Rule

If:

- request `base_revision` does not match current server `revision`

then the backend:

- must not merge automatically
- must not overwrite the server snapshot
- returns an explicit conflict response

### 6.4 Initial Revision Direction

Fixed starting point:

- newly created notebook starts at `revision = 1`

## 7. Response Shapes

### 7.1 Notebook Summary

Used for list responses:

```json
{
  "id": "7e7c6d72-124d-40db-8c03-42f0eab1f451",
  "title": "Notebook title",
  "revision": 4,
  "updated_at": "2026-05-14T10:00:00Z"
}
```

### 7.2 Full Notebook

Used for retrieval and sync responses:

```json
{
  "id": "7e7c6d72-124d-40db-8c03-42f0eab1f451",
  "title": "Notebook title",
  "revision": 4,
  "created_at": "2026-05-14T09:00:00Z",
  "updated_at": "2026-05-14T10:00:00Z",
  "content_snapshot": {
    "id": "7e7c6d72-124d-40db-8c03-42f0eab1f451",
    "title": "Notebook title",
    "tags": ["reference", "demo"],
    "blocks": [
      {
        "id": "block-1",
        "type": "text",
        "content": {
          "markdown": "# Heading"
        },
        "meta": {
          "tags": ["intro", "summary"]
        }
      }
    ],
    "metadata": {
      "version": 1
    }
  }
}
```

## 8. Notebook Endpoints

### 8.1 `GET /api/v1/notebooks`

Returns notebook summaries for the authenticated user only.

#### Success Response

Status:

- `200 OK`

Body:

```json
{
  "items": [
    {
      "id": "7e7c6d72-124d-40db-8c03-42f0eab1f451",
      "title": "Notebook title",
      "revision": 4,
      "updated_at": "2026-05-14T10:00:00Z"
    }
  ]
}
```

### 8.2 `GET /api/v1/notebooks/{notebook_id}`

Returns the full canonical notebook snapshot for a single owned notebook.

#### Success Response

Status:

- `200 OK`

Body:

- full notebook response shape

#### Error Cases

- `401 Unauthorized` if not authenticated
- `404 Not Found` if notebook is not accessible

### 8.3 `POST /api/v1/notebooks`

Creates a notebook owned by the authenticated user.

#### Request

```json
{
  "title": "New notebook",
  "content_snapshot": {
    "title": "New notebook",
    "tags": [],
    "blocks": [],
    "metadata": {
      "version": 1
    }
  }
}
```

Request notes:

- backend may generate notebook `id`
- backend may enforce that root `content_snapshot.id` matches persisted notebook `id`

#### Success Response

Status:

- `201 Created`

Body:

- full notebook response shape

### 8.4 `PATCH /api/v1/notebooks/{notebook_id}`

Updates lightweight notebook metadata without full sync semantics.

Recommended Version 1 usage:

- title updates

#### Request

```json
{
  "title": "Renamed notebook"
}
```

#### Success Response

Status:

- `200 OK`

Body:

- full notebook response shape or a smaller metadata response

Implementation note:

- if `title` is duplicated both in the notebook row and inside `content_snapshot`, backend should keep them consistent

### 8.5 `POST /api/v1/notebooks/{notebook_id}/sync`

Writes the new canonical notebook snapshot if the revision check passes.

#### Request

```json
{
  "base_revision": 4,
  "content_snapshot": {
    "id": "7e7c6d72-124d-40db-8c03-42f0eab1f451",
    "title": "Notebook title",
    "tags": ["reference", "demo"],
    "blocks": [
      {
        "id": "block-2",
        "type": "code",
        "content": {
          "language": "javascript",
          "source": "const value = 1;"
        },
        "meta": {
          "tags": ["example", "javascript"]
        }
      }
    ],
    "metadata": {
      "version": 1
    }
  }
}
```

#### Success Response

Status:

- `200 OK`

Body:

```json
{
  "id": "7e7c6d72-124d-40db-8c03-42f0eab1f451",
  "revision": 5,
  "updated_at": "2026-05-14T10:05:00Z",
  "content_snapshot": {
    "id": "7e7c6d72-124d-40db-8c03-42f0eab1f451",
    "title": "Notebook title",
    "tags": ["reference", "demo"],
    "blocks": [
      {
        "id": "block-2",
        "type": "code",
        "content": {
          "language": "javascript",
          "source": "const value = 1;"
        },
        "meta": {
          "tags": ["example", "javascript"]
        }
      }
    ],
    "metadata": {
      "version": 1
    }
  }
}
```

#### Conflict Response

Status:

- `409 Conflict`

Body:

```json
{
  "error": {
    "code": "notebook_sync_conflict",
    "message": "The notebook was updated on the server."
  },
  "server_revision": 6
}
```

Optional additions:

- include current server snapshot in the conflict response
- or require frontend to re-fetch with `GET /api/v1/notebooks/{notebook_id}`

### 8.6 `DELETE /api/v1/notebooks/{notebook_id}`

Deletes a notebook owned by the authenticated user.

#### Success Response

Status:

- `204 No Content`

Version 1 direction:

- hard delete is the default documented behavior unless a later approved task explicitly switches the API to soft delete

## 9. Validation Rules

### 9.1 Request Validation

Backend should validate:

- authenticated ownership
- request JSON structure
- required fields
- correct `base_revision` type and value
- notebook existence before sync comparison

### 9.2 Snapshot Validation

At minimum, backend should validate:

- root object structure
- `blocks` is an array
- block identifiers are present
- block type is one of allowed Version 1 types
- notebook `tags` is a list of strings
- every block contains `meta.tags` as a list of strings
- `text` blocks have expected text content shape
- `code` blocks have expected code content shape
- notebook `id` consistency if included

### 9.3 Size Constraints

Backend should enforce reasonable limits for:

- total payload size
- block count
- block content length

Exact limits can be fixed in implementation configuration.

## 10. Access Control Rules

Version 1 notebook access control is strict owner-only access:

- users list only their own notebooks
- users retrieve only their own notebooks
- users sync only their own notebooks
- users delete only their own notebooks

Frontend-side filtering is not a security boundary.

## 11. Local and Server State Relationship

The contract assumes:

- frontend `IndexedDB` stores the working copy and unsynced changes
- backend stores the latest accepted durable snapshot
- user-triggered sync is the only point where server state changes from local edits

This means the backend must never assume the client is always online or already synced.

## 12. Risks and Required Behavior

### 12.1 Conflict Handling

Required behavior:

- detect revision mismatch
- reject with `409 Conflict`
- do not auto-merge

### 12.2 Data Loss Prevention

Required behavior:

- do not overwrite newer server state when `base_revision` mismatches
- return enough information for frontend conflict handling

### 12.3 Invalid Snapshot Protection

Required behavior:

- reject malformed notebook JSON
- reject unsupported block types
- reject structurally invalid snapshots

### 12.4 Large Payload Protection

Required behavior:

- enforce request size limits
- keep execution outputs out of durable snapshot by default

## 13. Non-Goals for This Contract

This document does not define:

- exact SQL schema or migrations
- exact ORM models
- block-level diff sync
- collaborative merge logic
- search indexing strategy
- export API

Those can be defined later without changing the core persistence contract above.
