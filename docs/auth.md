# API Authentication Contract

## 1. Purpose

This document defines the implementation-facing authentication contract for the backend API.

Status:

- target contract for planned Version 1 implementation
- not a description of the current repository implementation state

It covers:

- supported authentication flows for Version 1
- request and response shapes
- session and cookie behavior
- validation and error semantics
- backend persistence direction for auth-related records

This document is aligned with:

- [../../dmc-1-t3-notebook-mono/docs/system_architecture.md](../../dmc-1-t3-notebook-mono/docs/system_architecture.md)
- [../../dmc-1-t3-notebook-mono/docs/tech_stack.md](../../dmc-1-t3-notebook-mono/docs/tech_stack.md)
- [./api_architecture.md](./api_architecture.md)

## 2. Fixed Contract for Version 1

The following auth contract is fixed for Version 1:

1. Primary sign-in method: `Email + OTP`.
2. Optional additional sign-in method: `Google OAuth`.
3. Authenticated browser state is carried by a backend-managed secure `HTTP-only` session cookie.
4. Frontend auth state is derived from backend session validation.
5. Frontend must not depend on frontend-readable bearer tokens.

Important boundary:

- the external auth contract is `session cookie` based
- backend may implement that session with an opaque session identifier or `JWT` inside the cookie
- that internal choice must not change the API contract

## 3. Common Conventions

### 3.1 Content Type

JSON endpoints use:

- request: `Content-Type: application/json`
- response: `Content-Type: application/json`

### 3.2 Authentication Transport

Protected endpoints rely on the session cookie sent automatically by the browser.

The frontend should use credentialed requests so cookies are included.

### 3.3 Time Values

Response fields such as `created_at`, `updated_at`, `expires_at`, and `authenticated_at` should use ISO 8601 timestamps in UTC.

### 3.4 Error Shape

Recommended error response shape:

```json
{
  "error": {
    "code": "otp_invalid",
    "message": "The provided OTP code is invalid."
  }
}
```

The exact wording may vary, but `code` values should remain stable enough for frontend handling.

## 4. User Summary Shape

Authenticated responses should return a compact user shape:

```json
{
  "user": {
    "id": "0f1b9d40-59d8-4d77-b90d-2e0bcedd91b5",
    "email": "user@example.com",
    "display_name": null
  }
}
```

Minimum user fields:

- `id`
- `email`
- optional `display_name`

## 5. Email + OTP Endpoints

### 5.1 `POST /api/v1/auth/request-otp`

Creates an OTP challenge for a normalized email.

#### Request

```json
{
  "email": "user@example.com"
}
```

#### Success Response

Status:

- `200 OK`

Body:

```json
{
  "challenge_id": "otp_ch_123",
  "expires_in_seconds": 300,
  "dev_otp": "123456"
}
```

Response notes:

- `dev_otp` must be returned only in explicitly allowed `local/dev` environments
- production responses must not include `dev_otp`

#### Validation Rules

- email must be present
- email must be normalized
- email format must be valid

#### Error Cases

- `422 Unprocessable Entity` for invalid payload
- `429 Too Many Requests` for rate limit or throttle violations

Example:

```json
{
  "error": {
    "code": "otp_request_rate_limited",
    "message": "Too many OTP requests. Try again later."
  }
}
```

### 5.2 `POST /api/v1/auth/verify-otp`

Verifies the OTP challenge and establishes an authenticated session.

#### Request

```json
{
  "challenge_id": "otp_ch_123",
  "otp_code": "123456"
}
```

#### Success Response

Status:

- `200 OK`

Body:

```json
{
  "user": {
    "id": "0f1b9d40-59d8-4d77-b90d-2e0bcedd91b5",
    "email": "user@example.com",
    "display_name": null
  },
  "authenticated_at": "2026-05-14T10:00:00Z"
}
```

Additional behavior:

- response must set the session cookie
- successful verification must invalidate the OTP challenge

#### Error Cases

- `422 Unprocessable Entity` for invalid payload format
- `401 Unauthorized` for invalid or expired OTP challenge
- `409 Conflict` if the challenge is no longer valid because it was replaced or already consumed
- `429 Too Many Requests` for attempt exhaustion or throttle violations

Recommended error codes:

- `otp_invalid`
- `otp_expired`
- `otp_challenge_not_found`
- `otp_attempt_limit_exceeded`

### 5.3 Optional `POST /api/v1/auth/resend-otp`

This endpoint is optional for the first implementation slice.

If implemented, it should either:

- create a fresh challenge and invalidate the previous one
- or resend only under tightly controlled limits

## 6. Session Endpoints

### 6.1 `GET /api/v1/auth/session`

Returns the current authenticated session state.

#### Success Response for Authenticated User

Status:

- `200 OK`

Body:

```json
{
  "authenticated": true,
  "user": {
    "id": "0f1b9d40-59d8-4d77-b90d-2e0bcedd91b5",
    "email": "user@example.com",
    "display_name": null
  }
}
```

#### Success Response for Anonymous User

Status:

- `200 OK`

Body:

```json
{
  "authenticated": false,
  "user": null
}
```

This endpoint should allow the frontend to bootstrap auth state without guessing from cookie visibility.

### 6.2 `POST /api/v1/auth/logout`

Invalidates the current session.

#### Success Response

Status:

- `200 OK`

Body:

```json
{
  "logged_out": true
}
```

Additional behavior:

- invalidate the backend-side session or equivalent token state
- clear the session cookie in the response

## 7. Google OAuth Endpoints

### 7.1 `GET /api/v1/auth/google/start`

Starts the Google OAuth flow.

Behavior:

- generate and persist OAuth state
- redirect the browser to Google authorization

Response:

- `302 Found` redirect to provider

### 7.2 `GET /api/v1/auth/google/callback`

Handles the provider callback.

Behavior:

- validate OAuth state
- resolve or create the user
- establish the authenticated session
- set the session cookie
- redirect the browser to the frontend application

Response:

- `302 Found` redirect back to frontend

Error behavior:

- invalid or missing state should result in a controlled auth error flow
- do not leak raw provider failure details to the user

## 8. Session Cookie Contract

### 8.1 Required Properties

Production session cookies should use:

- `HttpOnly`
- `Secure`
- `SameSite=Lax` or stricter if compatible with final UX
- `Path=/`

Recommended direction:

- bounded lifetime
- explicit rotation and invalidation strategy

### 8.2 Local Development

If local HTTPS is available, keep `Secure` enabled.

If not, local-only configuration may relax `Secure`, but this must stay environment-gated and never leak into production.

### 8.3 Cookie Payload Choice

The cookie may contain:

- an opaque session identifier
- or a signed token such as `JWT`

This is internal backend implementation detail.

The frontend must treat both cases identically.

## 9. Validation and Security Rules

### 9.1 Email + OTP Rules

Recommended Version 1 OTP constraints:

- numeric `6-digit` OTP
- `5 to 10 minute` expiration
- strict per-challenge attempt limit
- throttling by email and IP
- challenge invalidation after successful verification

### 9.2 Input Handling

- normalize email before lookup or creation
- validate `otp_code` as a constrained code value, not free text
- reject malformed JSON or missing required fields
- validate all OAuth redirect-state parameters

### 9.3 Logging Rules

- do not log OTP values in production
- do not log raw session secrets
- log auth failures with safe structured metadata

### 9.4 Session Security

- session identifiers or signed tokens must be high-entropy
- session validation must remain backend-side
- protected notebook endpoints must require a valid active session
- logout must invalidate future use of the current session

If `JWT` is used internally:

- signing must be backend-side
- verification must be backend-side
- token lifetime must be bounded
- revocation behavior must be defined explicitly

## 10. Suggested Persistence Direction

The backend will likely need auth-related records for:

- `users`
- `otp_challenges`
- `sessions`
- optional `oauth_accounts`

Recommended minimal fields:

### 10.1 `users`

- `id`
- `email`
- `display_name` nullable
- `created_at`
- `updated_at`

### 10.2 `otp_challenges`

- `id`
- `email`
- `otp_hash` or equivalent non-plain storage
- `expires_at`
- `attempt_count`
- `max_attempts`
- `consumed_at` nullable
- `created_at`

### 10.3 `sessions`

- `id`
- `user_id`
- `created_at`
- `expires_at`
- `revoked_at` nullable
- optional metadata such as IP or user agent if needed

## 11. Expected Frontend Handling

The frontend should handle the following states explicitly:

- `unknown`
- `anonymous`
- `authenticating`
- `authenticated`
- `session_expired`

The frontend should also react explicitly to:

- `401 Unauthorized`
- `403 Forbidden`
- `409 Conflict` where applicable
- `429 Too Many Requests`

## 12. Non-Goals for This Contract

This document does not define:

- provider-specific Google OAuth credentials
- exact cookie name
- exact internal ORM models
- exact migration implementation
- password authentication

Those can be fixed in implementation tasks later without changing the contract above.
