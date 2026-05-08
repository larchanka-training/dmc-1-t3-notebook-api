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

```bash
pytest
```

## How to extend

- Add new endpoints in `app/api/v1/endpoints/`
- Include endpoint routers inside `app/api/v1/router.py`
- Add business logic/services in new modules (for example: `app/services/`)
- Add database layer later (`app/db/`) when needed

