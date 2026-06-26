# AI Runtime Operations

## 1. Purpose

This document defines the operational runtime contract for the canonical Version 1 AI path:

- `frontend -> backend -> AWS Bedrock`

It covers:

- required backend runtime configuration
- approved credential delivery paths
- safe secret handling expectations
- minimum readiness and observability checks
- manual smoke and negative smoke procedures
- common failure modes and fast diagnosis steps

This document must remain consistent with:

- `docs/ai-architecture.md`
- `api/docs/ai_contract.md`
- `api/docs/api_architecture.md`
- `docs/tech_stack.md`

## 2. Fixed Operational Decisions

The following operational decisions are fixed for the first AI slice:

1. The canonical runtime provider is `AWS Bedrock`.
2. Provider credentials remain backend-side only.
3. The browser must never receive Bedrock credentials, IAM details, or provider transport payloads.
4. Production-like API runtime secrets are delivered through `AWS Secrets Manager` via `AWS_APP_SECRET_ARN`.
5. Local development may use `.env` for non-secret AI toggles, but long-lived AWS credentials should not be committed into repository files.
6. The backend health surface may expose safe readiness metadata, but it must not expose raw credentials, secret values, or full prompt payloads.
7. The backend AI response `requestId` is the primary correlation id for AI generation diagnostics.

## 3. Required Runtime Configuration

The backend Bedrock path requires the following application settings:

| Variable | Required | Meaning |
|---|---|---|
| `AI_PROVIDER_ENABLED` | yes | Enables the canonical backend AI provider path |
| `AI_PROVIDER_NAME` | yes | Must be `bedrock` for Version 1 |
| `AI_PROVIDER_MODEL` | yes | Bedrock model id approved for the first AI slice |
| `AI_BEDROCK_REGION` | yes | AWS region where the selected model is enabled |
| `AI_BEDROCK_TIMEOUT_SECONDS` | yes | Backend timeout budget for one provider call |
| `AI_BEDROCK_MAX_RETRIES` | yes | SDK transport retry count; does not replace application-level repair retry |

Recommended first-slice model baseline:

- `AI_PROVIDER_MODEL=anthropic.claude-3-haiku`

Recommended first-slice timeout baseline:

- `AI_BEDROCK_TIMEOUT_SECONDS=20`

Recommended first-slice transport retry baseline:

- `AI_BEDROCK_MAX_RETRIES=1`

## 4. Credential Delivery Paths

### 4.1 Local Development

Preferred local credential options:

1. AWS shared config/profile resolution through the default boto3 credential chain
2. Short-lived exported environment variables in the current shell
3. Temporary assumed-role credentials issued by the team's standard AWS access workflow

Do not:

- commit `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, or session tokens into `.env.example`
- paste long-lived credentials into repository docs
- log the resolved credential source or secret values in application logs

### 4.2 Staging and Production-Like Environments

Preferred deployed credential path:

1. ECS task role or equivalent workload identity with Bedrock invoke permissions
2. `AWS_APP_SECRET_ARN` pointing to the single ini-format application secret for non-credential runtime values

The application secret should contain the Bedrock runtime toggles, for example:

```ini
AI_PROVIDER_ENABLED=true
AI_PROVIDER_NAME=bedrock
AI_PROVIDER_MODEL=anthropic.claude-3-haiku
AI_BEDROCK_REGION=us-east-1
AI_BEDROCK_TIMEOUT_SECONDS=20
AI_BEDROCK_MAX_RETRIES=1
```

AWS credentials themselves should come from the runtime identity where possible, not from the same secret blob.

## 5. Minimum AWS Access Requirements

The runtime identity used by the API must be able to:

- resolve the selected AWS region
- invoke the selected Bedrock model in that region
- read the application secret when `AWS_APP_SECRET_ARN` is used

The team must verify model access in the same region configured in `AI_BEDROCK_REGION`.

Region mismatch is a first-class failure mode:

- credentials may be valid
- Bedrock may be reachable
- but the selected model may still be unavailable in the configured region

## 6. Minimum Readiness and Observability

### 6.1 Health Surface

`GET /api/v1/system/health` returns a safe AI readiness block:

- `provider`
- `configured`
- `ready`
- `reason`
- `missing_fields`

This surface is intended to distinguish:

- provider disabled
- incomplete application config
- missing SDK/runtime packaging
- locally ready application wiring

It does not prove live Bedrock authorization by itself.

### 6.2 Correlation

Every AI generation response already returns:

- `requestId`

This id must be used to correlate:

- backend AI service logs
- provider timeout vs unavailable outcomes
- manual smoke observations from the UI

### 6.3 Logging Rules

Allowed in logs:

- `requestId`
- notebook id
- source block id
- provider name
- model id
- attempt number
- failure class such as timeout, unavailable, invalid response, extraction failure, syntax failure

Not allowed in logs:

- raw AWS credentials
- full prompt text
- full notebook context payload
- provider auth headers
- secret values resolved from `AWS_APP_SECRET_ARN`

## 7. Manual Operational Smoke

This smoke is required before calling the real Bedrock path operational in a target environment.

### 7.1 Preconditions

Before the UI flow:

1. The API starts successfully with Bedrock runtime settings present.
2. `GET /api/v1/system/health` returns:
   - `ai.provider = "bedrock"`
   - `ai.configured = true`
   - `ai.ready = true`
3. The target runtime has valid AWS credentials or workload identity.
4. The selected model is enabled in the configured region.
5. The notebook used for smoke is server-backed and already synced.

### 7.2 Backend Readiness Smoke

1. Open `GET /api/v1/system/health`.
2. Confirm the response reports the expected environment and AI readiness.
3. Check API logs for startup without secret leakage.

### 7.3 End-to-End Product Smoke

1. Sign in through a supported auth flow.
2. Open a synced notebook.
3. Ensure the source block is a durable `text` block.
4. Enter a code-generation request such as:

```text
Write JavaScript code that parses a CSV string into an array of objects.
```

5. Trigger AI generation.
6. Confirm the backend responds successfully from the Bedrock-backed path.
7. Confirm the generated code is inserted into the next empty `code` block or a newly created `code` block below the source block.
8. Confirm the inserted code remains editable.
9. Execute the generated code in the notebook runtime and confirm normal execution behavior.

### 7.4 Negative Smoke

Run these targeted failures separately:

1. Missing credentials:
   - expected AI endpoint result: `503 AI_PROVIDER_UNAVAILABLE` or equivalent provider-access failure
   - expected diagnosis: health may still show `ready=true`; failure is at live credential/invoke time
2. Wrong or unavailable model access:
   - expected AI endpoint result: `503 AI_PROVIDER_UNAVAILABLE`
   - expected diagnosis: credentials work, but the model/region authorization path is wrong
3. Region mismatch:
   - expected AI endpoint result: `503 AI_PROVIDER_UNAVAILABLE`
   - expected diagnosis: configured region does not have access to the selected model
4. Timeout-class behavior:
   - expected AI endpoint result: `504 AI_PROVIDER_TIMEOUT`
   - expected diagnosis: provider call exceeded `AI_BEDROCK_TIMEOUT_SECONDS`

## 8. Failure Modes and Quick Diagnosis

| Symptom | Likely class | Quick diagnosis |
|---|---|---|
| `ai.reason = disabled` in health | configuration | `AI_PROVIDER_ENABLED` is false |
| `ai.reason = incomplete-config` in health | configuration | inspect `missing_fields` in health payload |
| `ai.reason = sdk-unavailable` in health | packaging/runtime | ensure `boto3` is installed in the API environment |
| `503 AI_PROVIDER_UNAVAILABLE` on generation | access or connectivity | verify AWS identity, Bedrock model access, region, and outbound network |
| `504 AI_PROVIDER_TIMEOUT` on generation | provider timeout | verify model latency and `AI_BEDROCK_TIMEOUT_SECONDS` |
| frontend AI flow fails before backend call | notebook prerequisite or auth | verify session, synced notebook, and source block type |

Fast diagnosis order:

1. Check `GET /api/v1/system/health`.
2. Check whether the notebook is synced and the source block is `text`.
3. Trigger one AI request and capture `requestId`.
4. Inspect backend logs for that `requestId`.
5. If the failure class is `unavailable`, verify:
   - AWS identity is present
   - the configured region matches model availability
   - Bedrock access is granted for the selected model
   - outbound connectivity to AWS is allowed
6. If the failure class is `timeout`, verify:
   - request latency
   - configured timeout
   - transient provider degradation

## 9. Verification Commands

Backend verification after changes:

```bash
cd api
.venv/bin/python -m pytest tests/unit/ai/test_provider.py tests/integration/system/test_health.py -q
```

Local packaging verification after dependency install:

```bash
cd api
.venv/bin/python -c "import boto3; print(boto3.__version__)"
```

## 10. Current Repository Notes

For this repository state:

- `boto3` must be present in the editable-install dependency set, not only in `requirements.txt`
- `GET /api/v1/system/health` is the canonical operational probe for the backend
- real Bedrock invocation still depends on external AWS access that cannot be proven from repository-only tests
