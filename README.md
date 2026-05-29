# FastAPI Template (MSD Course)

A simple, extensible FastAPI starter template for students in the Modern Software Development course.

## What is included

- FastAPI app with versioned API routing
- Health check endpoint
- Environment-based configuration with Pydantic Settings
- Basic test setup with Pytest
- Clear folder structure for future growth

## Project structure

```text
.
├── app
│   ├── api
│   │   └── v1
│   │       ├── endpoints
│   │       │   └── health.py
│   │       └── router.py
│   ├── core
│   │   └── config.py
│   └── main.py
├── tests
│   └── test_health.py
├── .env.example
├── pyproject.toml
└── requirements-dev.txt
```

## Quick start

1. Create and activate virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements-dev.txt
```

3. Copy env file:

```bash
cp .env.example .env
```

4. Run app:

```bash
uvicorn app.main:app --reload
```

API docs will be available at:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

## Run tests

See the [Tests](#tests) section below for the full guide. Quick start:

```bash
make test-unit          # default; fast; no Postgres needed
make test-integration   # requires docker compose postgres + notebook_test DB
```

## Tests

### Quick commands

    make test-unit          # default; ~seconds; no Postgres needed
    make test-integration   # requires docker compose postgres + notebook_test DB
    make test-all           # both, sequential

Raw pytest equivalents:

    pytest                                    # unit only (default)
    pytest -m integration                     # integration only
    pytest -m "unit or integration"           # both

### Environment

| Variable | Required for | Default source |
|---|---|---|
| `TEST_DATABASE_URL` | integration | `api/.env.test` (loaded by pytest-env) |

Bring up Postgres and create the test database once:

    docker compose up -d postgres
    docker compose exec postgres psql -U admin -d postgres -c "CREATE DATABASE notebook_test;"

### Naming conventions

| Kind | Path |
|---|---|
| Unit test | `tests/unit/<module>/test_*.py` |
| Integration test | `tests/integration/<feature>/test_*.py` |
| Factory | `tests/factories.py` (or `tests/factories/<feature>.py`) |

Directory placement automatically applies the correct marker — no decorator needed.

### Fixtures (auto-available, no setup required)

| Fixture | Scope | Purpose |
|---|---|---|
| `engine` | session | Async SQLAlchemy engine bound to `TEST_DATABASE_URL` |
| `apply_migrations` | session | Runs `alembic upgrade head` once; gated on `-m integration` |
| `db_session` | function | Async session with per-test transaction rollback (SAVEPOINT pattern) |
| `client` | function | `httpx.AsyncClient` against the FastAPI app, with DB dependency overridden to share `db_session` |
| `authenticated_client` | function | `client` with placeholder session cookie (TODO: real auth) |

### Artifacts

All reports are written to `api/reports/` (gitignored, overwritten each run):

| File | Produced by |
|---|---|
| `junit-unit.xml` | `make test-unit` |
| `coverage-unit.xml` | `make test-unit` |
| `junit-integration.xml` | `make test-integration` |
| `coverage-integration.xml` | `make test-integration` |

## How to extend

- Add new endpoints in `app/api/v1/endpoints/`
- Include endpoint routers inside `app/api/v1/router.py`
- Add business logic/services in new modules (for example: `app/services/`)
- Add database layer later (`app/db/`) when needed

