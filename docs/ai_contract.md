# API AI Contract

## 1. Purpose

This document defines the implementation-facing backend AI contract for block-scoped code generation in Version 1.

Status:

- target contract for planned and ongoing Version 1 implementation
- canonical backend contract for the AI route and its error model
- not a description of the current repository implementation state

It covers:

- the canonical AI route
- request payload shape
- success response shape
- normalized backend error shape
- validation and policy gates before provider invocation
- deterministic post-provider validation and repair rules
- backend versus frontend responsibility boundaries

This document is aligned with:

- [../../docs/ai-architecture.md](../../docs/ai-architecture.md)
- [../../docs/system_architecture.md](../../docs/system_architecture.md)
- [../../docs/tech_stack.md](../../docs/tech_stack.md)
- [./api_architecture.md](./api_architecture.md)

## 2. Fixed Contract for Version 1

The following AI contract is fixed for Version 1:

1. The canonical backend AI route is `POST /api/v1/ai/code-blocks/generate`.
2. The route requires the existing backend-managed secure session cookie.
3. The backend accepts only block-scoped generation or revision requests.
4. Version 1 supports `JavaScript` output only.
5. The source block must be a durable `text` block.
6. Revising code uses the documented convert-code-to-text flow first; the backend still receives a `text` source block.
7. The backend returns proposed code only and does not mutate notebook content.
8. Deterministic validation has priority over LLM-based validation where deterministic checks are sufficient.
9. Extraction or syntax failure triggers one bounded repair retry.
10. `AI_FALLBACK_UNAVAILABLE` is not part of the backend contract for this route; it is a frontend-local fallback concern.

## 3. Common Conventions

### 3.1 Content Type

JSON endpoints use:

- request: `Content-Type: application/json`
- response: `Content-Type: application/json`

### 3.2 Authentication

The route requires an authenticated session cookie.

Anonymous requests should receive:

- `401 Unauthorized`

This `401` behavior is provided by the shared auth/session layer and is not represented by a normalized AI-specific `errorCode`.

### 3.3 User-Facing Message Constraint

All user-facing `message` fields returned by this contract must be:

- concise
- safe to display directly in the UI
- free of secrets, stack traces, hidden prompts, screening internals, provider payload dumps, and infrastructure details

## 4. Route and Responsibility Boundary

### 4.1 Canonical Route

Canonical AI route:

- `POST /api/v1/ai/code-blocks/generate`

This remains the single Version 1 backend API entrypoint for block-scoped AI code generation.

### 4.2 Backend Responsibilities

The backend is responsible for:

- authenticated access enforcement
- notebook access and source-block validation
- prompt policy screening
- unsafe prompt screening
- provider invocation through the backend boundary
- deterministic code extraction
- deterministic JavaScript syntax validation
- bounded repair retry
- normalized success and error shaping

### 4.3 Frontend Responsibilities

The frontend is responsible for:

- building bounded request context
- selecting the source block according to the product flow
- choosing the insertion target
- inserting returned code into the notebook
- preserving prompt draft and request UI state
- offering any optional local fallback UX

The backend does not:

- insert blocks
- replace notebook blocks directly
- execute notebook code
- persist AI history

## 5. Request Contract

### 5.1 Canonical Request Shape

```json
{
  "notebookId": "2d58d140-5532-4ac3-8457-3114a9f4b9f2",
  "sourceBlockId": "blk_text_2",
  "mode": "generate",
  "prompt": "Write JavaScript code that parses this CSV and calculates yearly totals.",
  "context": {
    "language": "javascript",
    "scope": "this",
    "sourceText": "Parse this CSV and calculate yearly totals.",
    "notebookTitle": "Yearly tax analysis",
    "globalsSummary": [
      "csvText",
      "headers"
    ],
    "relevantBlocks": [
      {
        "blockId": "blk_text_1",
        "type": "text",
        "content": "This notebook analyzes yearly tax data exported as CSV."
      },
      {
        "blockId": "blk_code_1",
        "type": "code",
        "content": "const headers = ['year', 'amount'];"
      }
    ]
  },
  "insertionStrategy": "next-empty-or-new-after-source"
}
```

### 5.2 Required Top-Level Fields

| Field | Type | Required | Version 1 rules |
|---|---|---|---|
| `notebookId` | string | yes | Must identify an existing notebook visible to the current user |
| `sourceBlockId` | string | yes | Must identify an existing `text` block inside `notebookId` |
| `mode` | string enum | yes | Allowed values: `generate`, `revise` |
| `prompt` | string | yes | Non-empty, trimmed, code-generation intent only |
| `context` | object | yes | Must satisfy the contract below |
| `insertionStrategy` | string enum | yes | Only `next-empty-or-new-after-source` is allowed in Version 1 |

### 5.3 `context` Object

| Field | Type | Required | Version 1 rules |
|---|---|---|---|
| `language` | string enum | yes | Must be exactly `javascript` |
| `scope` | string enum | no | Defaults to `this`; allowed values: `this`, `notebook` |
| `sourceText` | string | yes | Canonical normalized text sent to the provider |
| `notebookTitle` | string | no | Optional lightweight context only |
| `globalsSummary` | string[] | no | Optional compact list of safe execution globals |
| `relevantBlocks` | array | no | Ordered contextual blocks selected by the frontend context builder |

### 5.4 `context.relevantBlocks[]`

| Field | Type | Required | Version 1 rules |
|---|---|---|---|
| `blockId` | string | yes | Must be unique within the array |
| `type` | string enum | yes | Allowed values: `text`, `code` |
| `content` | string | yes | Canonical block text or code source |

## 6. Request Validation and Policy Gates

### 6.1 Pre-provider Gates

The backend must apply these gates before any provider invocation:

1. Authenticated session is present.
2. `notebookId` resolves to a notebook accessible to the current user.
3. `sourceBlockId` resolves to a block in that notebook.
4. The referenced source block is of durable type `text`.
5. `mode` is either `generate` or `revise`.
6. `context.language` is exactly `javascript`.
7. `prompt` and `context.sourceText` are both non-empty after trim.
8. The request stays inside the fixed Version 1 size limits.
9. `prompt` passes code-intent policy screening.
10. `prompt` passes unsafe prompt screening.

If any pre-provider gate fails, the provider must not be called.

### 6.2 Size and Boundedness Rules

Version 1 request-size limits are fixed as follows:

- `prompt`: 1 to 4,000 UTF-8 characters after trim
- `context.sourceText`: 1 to 12,000 UTF-8 characters after trim
- `context.notebookTitle`: at most 200 UTF-8 characters
- `context.globalsSummary`: at most 50 entries, each at most 120 UTF-8 characters
- `context.relevantBlocks`: at most 20 blocks
- each `context.relevantBlocks[].content`: at most 8,000 UTF-8 characters
- combined textual payload across `prompt`, `context.sourceText`, `notebookTitle`, `globalsSummary`, and `relevantBlocks[].content`: at most 50,000 UTF-8 characters

Requests outside these bounds are invalid requests.

### 6.3 Prompt Policy Rules

Version 1 allows only code-generation and code-revision intent for this route.

- Reject with `AI_PROMPT_REJECTED` when the request asks for explanation, summarization, chat, or other non-code output.
- Reject with `AI_PROMPT_UNSAFE` when the request attempts prompt injection, policy override, credential extraction, hidden instruction disclosure, or other unsafe behavior.
- Blocked or rejected prompts must not be forwarded to the provider.

## 7. Success Response Contract

### 7.1 Canonical Success Shape

```json
{
  "requestId": "air_20260618_0001",
  "status": "success",
  "code": "function parseTaxes(csvText) {\n  return [];\n}",
  "provider": {
    "name": "bedrock",
    "model": "deepseek.v3.2"
  },
  "validation": {
    "extractionApplied": true,
    "syntaxOk": true,
    "repairAttempts": 0
  },
  "warnings": [
    {
      "code": "AI_CONTEXT_TRUNCATED",
      "message": "Some low-priority context blocks were omitted to fit the request budget."
    }
  ]
}
```

### 7.2 Success Field Rules

| Field | Type | Required | Rules |
|---|---|---|---|
| `requestId` | string | yes | Stable request identifier for logs and UI correlation |
| `status` | string literal | yes | Always `success` |
| `code` | string | yes | Plain code string only; never markdown fences or prose wrapper |
| `provider.name` | string | yes | Version 1 canonical value is `bedrock` |
| `provider.model` | string | yes | Provider model identifier used for generation |
| `validation.extractionApplied` | boolean | yes | `true` when the backend normalized provider output into plain code |
| `validation.syntaxOk` | boolean | yes | Must be `true` for every success response |
| `validation.repairAttempts` | integer | yes | Allowed values in Version 1: `0` or `1` |
| `warnings` | array | no | Optional user-displayable warning objects |

### 7.3 Warning Rules

Warnings do not change `status: "success"` and must be safe to show in the UI.

Allowed Version 1 warning codes:

- `AI_CONTEXT_TRUNCATED`
- `AI_COMMENT_ONLY_CODE`

`AI_COMMENT_ONLY_CODE` is the canonical outcome for comment-only or placeholder-only syntactically valid code. This case remains a success with `validation.syntaxOk: true` and a warning; it is not upgraded to a failure.

## 8. Post-provider Contract

After a provider response is received, the backend must:

1. deterministically extract a plain code string
2. deterministically validate JavaScript syntax without executing the code
3. if extraction or syntax validation fails, perform exactly one bounded repair retry
4. rerun extraction and syntax validation on the repair result
5. return either:
   - success when extraction and syntax validation pass
   - a normalized final error when the repair attempt is exhausted or fails

Version 1 bounded repair semantics are fixed:

- initial provider attempt: `1`
- repair attempts: `max 1`
- maximum total provider calls per request: `2`

## 9. Error Contract

### 9.1 Canonical Error Shape

```json
{
  "requestId": "air_20260618_0001",
  "status": "error",
  "errorCode": "AI_PROVIDER_TIMEOUT",
  "message": "The AI provider did not respond in time. Try again.",
  "retryable": true
}
```

### 9.2 Error Response Rules

- `requestId` is required when request parsing succeeded far enough to allocate one; otherwise it may be omitted by framework-level validation or auth middleware.
- `status` is always `error`.
- `errorCode` must come from the catalog below.
- `retryable` indicates whether the same user intent may be attempted again without changing notebook ownership or session state.

### 9.3 Normalized Backend Error Catalog

| HTTP status | `errorCode` | Retryable | Provider call allowed | Meaning |
|---|---|---|---|---|
| `422` | `AI_INVALID_REQUEST` | no | no | Request shape, enum values, size limits, or source-block contract failed |
| `403` | `AI_FORBIDDEN` | no | no | Notebook access is denied for the current authenticated user |
| `400` | `AI_PROMPT_REJECTED` | no | no | Prompt asks for non-code output or otherwise violates code-only policy |
| `400` | `AI_PROMPT_UNSAFE` | no | no | Prompt is blocked by unsafe or policy-evasion screening |
| `503` | `AI_PROVIDER_UNAVAILABLE` | yes | yes | Provider or provider transport is unavailable |
| `504` | `AI_PROVIDER_TIMEOUT` | yes | yes | Provider call exceeded the backend timeout budget |
| `502` | `AI_RESPONSE_INVALID` | yes | yes | Provider response is malformed or unusable before code extraction can complete |
| `502` | `AI_CODE_EXTRACTION_FAILED` | yes | yes | No valid code could be extracted after bounded repair retry |
| `502` | `AI_CODE_SYNTAX_INVALID` | yes | yes | Extracted code remains syntactically invalid after bounded repair retry |

## 10. Contract Examples

### 10.1 Happy Path

Request:

```json
{
  "notebookId": "2d58d140-5532-4ac3-8457-3114a9f4b9f2",
  "sourceBlockId": "blk_text_2",
  "mode": "generate",
  "prompt": "Write JavaScript code that parses this CSV and calculates yearly totals.",
  "context": {
    "language": "javascript",
    "scope": "this",
    "sourceText": "Parse this CSV and calculate yearly totals."
  },
  "insertionStrategy": "next-empty-or-new-after-source"
}
```

Response:

```json
{
  "requestId": "air_20260618_0001",
  "status": "success",
  "code": "function parseTotals(csvText) {\n  return [];\n}",
  "provider": {
    "name": "bedrock",
    "model": "deepseek.v3.2"
  },
  "validation": {
    "extractionApplied": true,
    "syntaxOk": true,
    "repairAttempts": 0
  }
}
```

### 10.2 Prompt Rejection

```json
{
  "requestId": "air_20260618_0002",
  "status": "error",
  "errorCode": "AI_PROMPT_REJECTED",
  "message": "This action accepts only code-generation or code-revision requests.",
  "retryable": false
}
```

### 10.3 Prompt Unsafe

```json
{
  "requestId": "air_20260618_0003",
  "status": "error",
  "errorCode": "AI_PROMPT_UNSAFE",
  "message": "This request cannot be processed safely.",
  "retryable": false
}
```

### 10.4 Provider Unavailable

```json
{
  "requestId": "air_20260618_0004",
  "status": "error",
  "errorCode": "AI_PROVIDER_UNAVAILABLE",
  "message": "The AI provider is temporarily unavailable. Try again.",
  "retryable": true
}
```

### 10.5 Extraction Failure After Repair Exhaustion

```json
{
  "requestId": "air_20260618_0005",
  "status": "error",
  "errorCode": "AI_CODE_EXTRACTION_FAILED",
  "message": "The AI response did not contain usable code. Try again.",
  "retryable": true
}
```

### 10.6 Syntax Invalid After Repair Exhaustion

```json
{
  "requestId": "air_20260618_0006",
  "status": "error",
  "errorCode": "AI_CODE_SYNTAX_INVALID",
  "message": "The generated code was invalid and could not be repaired automatically. Try again.",
  "retryable": true
}
```

## 11. Alignment Notes

- `docs/ai-architecture.md` remains the high-level AI pipeline and product behavior document.
- This document is the canonical backend contract for request and response shape, normalized errors, and backend validation semantics.
- Task files under `docs/plans/tasks/ai-integration-*` may reference this document, but they are not the primary long-lived contract source.
