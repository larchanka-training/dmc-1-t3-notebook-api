# Архитектура API

## 1. Назначение

Этот документ определяет архитектуру backend-приложения.

В нем фиксируются:

- роль backend в системе
- архитектурный стиль backend
- основные границы backend-feature
- модель хранения данных backend
- модель синхронизации backend
- модель аутентификации backend
- модель AI-интеграции backend
- зафиксированные backend-технологические решения для Version 1

## 2. Зафиксированные решения для Version 1

Для Version 1 зафиксированы следующие backend-решения:

1. API использует `REST + HTTP + JSON` под префиксом `/api/v1`.
2. Backend использует архитектуру `feature-driven with internal layers`.
3. Основные backend-features — `auth`, `notebooks`, `ai` и `system`.
4. `sync` относится к feature `notebooks` и не является отдельной top-level feature.
5. Общая backend-структура организована через `core`, `db`, `integrations` и `features`.
6. Контент notebook хранится в `PostgreSQL` как `JSONB` snapshot.
7. Долговременные notebook-метаданные включают `id`, `owner_id`, `title`, `revision`, `created_at` и `updated_at`.
8. Runtime outputs по умолчанию не хранятся как durable notebook-state.
9. Синхронизация использует snapshot целого notebook, revision-based conflict detection и `409 Conflict`.
10. Аутентификация поддерживает `Email + OTP` и `Google OAuth`.
11. Аутентифицированное browser-state использует backend-managed secure `HTTP-only` session cookie.
12. В `local/dev` OTP может возвращаться прямо в API response вместо внешней email-доставки.
13. AI-генерация кода использует один block-oriented endpoint.
14. Data access layer использует `SQLAlchemy ORM`.
15. Миграции базы данных используют `Alembic`.
16. Version 1 использует `FastAPI BackgroundTasks` там, где нужен background work, и не вводит отдельную job queue.

## 3. Роль Backend в системе

Backend является server-side границей hosted web application с local-first поведением.

Backend отвечает за:

- аутентификацию
- жизненный цикл session
- персистентность notebook
- получение notebook
- синхронизацию notebook
- access control
- посредничество между системой и AI provider
- operational endpoints
- границы внешних интеграций

Backend не отвечает за выполнение notebook `JavaScript`.

Notebook-код выполняется в browser runtime, а backend остается слоем управления, хранения и интеграций.

## 4. Архитектурный стиль Backend

Backend использует `feature-driven architecture with internal layers`.

Это означает:

- codebase организован по бизнес-feature на верхнем уровне
- каждая feature владеет своим API, схемами, service-логикой и persistence-логикой
- общая инфраструктура вынесена в shared backend-модули

Backend не использует один общий project-wide каталог `routers`, `services` или `repositories` как основную архитектурную границу.

## 5. Верхнеуровневая структура Backend

Структура backend:

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

`main.py` отвечает за:

- bootstrap приложения
- регистрацию middleware
- регистрацию router-ов
- wiring жизненного цикла приложения

### 5.2 `core/`

`core/` содержит общую backend-логику приложения, такую как:

- конфигурация
- security helpers
- общие ошибки
- логирование
- wiring общих зависимостей

### 5.3 `db/`

`db/` содержит общую database-инфраструктуру, такую как:

- управление database session
- конфигурация ORM base
- конфигурация миграций
- общие database helpers

### 5.4 `integrations/`

`integrations/` содержит integration-код, работающий с внешними провайдерами, такой как:

- email delivery
- доступ к LLM provider
- интеграция с Google OAuth provider

### 5.5 `features/`

`features/` содержит бизнес-feature модули:

- `auth`
- `notebooks`
- `ai`
- `system`

## 6. Внутренняя структура Feature-модуля

Каждый feature-модуль следует одной внутренней layered-структуре там, где это нужно:

```text
feature/
  router.py
  schemas.py
  service.py
  repository.py
  models.py
```

### 6.1 `router.py`

Отвечает за:

- определения HTTP routes
- разбор request
- формирование response
- вызов feature-services

### 6.2 `schemas.py`

Отвечает за:

- request DTO
- response DTO
- внутренние модели валидации API

### 6.3 `service.py`

Отвечает за:

- бизнес-правила feature
- orchestration репозиториев и интеграций
- application behavior на уровне транзакций

### 6.4 `repository.py`

Отвечает за:

- data access
- persistence queries
- получение и изменение сущностей

### 6.5 `models.py`

Отвечает за:

- ORM-модели, принадлежащие feature
- database-level определения сущностей

## 7. Ответственности Feature

### 7.1 `auth`

Feature `auth` отвечает за:

- запрос и проверку email OTP
- обработку Google OAuth start и callback
- создание аутентифицированной session
- получение аутентифицированной session
- logout
- связывание внешней identity с внутренней user identity

### 7.2 `notebooks`

Feature `notebooks` отвечает за:

- операции с коллекцией notebook
- операции с отдельным notebook
- долговременное хранение notebook
- контроль ownership notebook
- синхронизацию notebook
- управление revision notebook
- обнаружение sync-конфликтов

### 7.3 `ai`

Feature `ai` отвечает за:

- block-oriented AI generation requests
- передачу notebook-context в LLM layer
- возврат сгенерированного кода для вставки в notebook
- изоляцию provider-specific логики за backend-границей

### 7.4 `system`

Feature `system` отвечает за:

- health endpoints
- operational status endpoints
- легкие infrastructure-facing service endpoints

## 8. Группы API Routes

API сгруппирован под `/api/v1`.

### 8.1 Auth Routes

Канонические auth-routes:

- `POST /api/v1/auth/request-otp`
- `POST /api/v1/auth/verify-otp`
- `GET /api/v1/auth/session`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/google/start`
- `GET /api/v1/auth/google/callback`

### 8.2 Notebook Routes

Канонические notebook-routes:

- `/api/v1/notebooks`
- `/api/v1/notebooks/{notebookId}`
- `/api/v1/notebooks/{notebookId}/sync`

Feature `notebooks` предоставляет collection-endpoints, item-endpoints и notebook-scoped endpoints синхронизации.

### 8.3 AI Routes

Канонический AI-route:

- `POST /api/v1/ai/code-blocks/generate`

Этот endpoint принимает:

- generation mode
- prompt
- текущее содержимое code block
- релевантный notebook-context

### 8.4 System Routes

Канонический system-route:

- `GET /api/v1/system/health`

## 9. Модель хранения данных

Backend хранит следующие основные долговременные сущности:

- `User`
- `AuthSession`
- `OtpChallenge`
- `OAuthAccount`
- `Notebook`

### 9.1 `User`

Сущность `User` представляет внутреннюю аутентифицированную identity продукта.

### 9.2 `AuthSession`

Сущность `AuthSession` представляет backend-managed аутентифицированную browser session.

### 9.3 `OtpChallenge`

Сущность `OtpChallenge` представляет состояние выдачи и проверки one-time password.

### 9.4 `OAuthAccount`

Сущность `OAuthAccount` представляет связь между Google OAuth identity и внутренним `User`.

### 9.5 `Notebook`

Сущность `Notebook` хранит:

- notebook-метаданные
- snapshot notebook-content

Snapshot notebook-content хранится как `JSONB`.

Долговременные notebook-метаданные:

- `id`
- `owner_id`
- `title`
- `revision`
- `created_at`
- `updated_at`

Runtime outputs по умолчанию не входят в durable notebook-record.

## 10. Модель хранения Notebook

Персистентность notebook использует один durable notebook snapshot на каждую синхронизированную revision.

Backend хранит:

- identity notebook
- ownership notebook
- заголовок notebook
- notebook-content как структурированный `JSONB`
- revision-метаданные
- timestamps создания и обновления

Backend не раскладывает notebook-блоки в большой multi-table block graph в Version 1.

## 11. Модель синхронизации

Синхронизация привязана к notebook и основана на snapshot-модели.

Модель sync работает так:

1. Frontend отправляет полный snapshot notebook.
2. Frontend передает `base_revision` notebook.
3. Backend сравнивает revision клиента с durable revision на сервере.
4. Если revision совпадают, backend сохраняет новый snapshot и увеличивает revision.
5. Если revision не совпадают, backend возвращает `409 Conflict`.

Backend не выполняет автоматический merge.

## 12. Архитектура аутентификации

Backend поддерживает два sign-in flow:

- `Email + OTP`
- `Google OAuth`

Оба варианта входа приводят к одной модели аутентифицированного browser-state:

- внутренняя user identity
- backend-managed аутентифицированная session
- secure `HTTP-only` session cookie

### 12.1 Email OTP Flow

Email OTP flow состоит из:

- запроса OTP
- создания OTP challenge
- доставки OTP через email integration в deployed environments
- проверки OTP
- создания аутентифицированной session

В `local/dev` backend может возвращать OTP прямо в API response для разработки.

### 12.2 Google OAuth Flow

Google OAuth flow состоит из:

- запуска входа через Google через backend-route
- redirect к Google OAuth provider
- получения provider callback
- создания или поиска внутренней user identity
- создания аутентифицированной session

## 13. AI Architecture

Backend опосредует весь доступ к LLM provider.

AI-архитектура работает так:

1. Frontend отправляет block-oriented request.
2. Backend валидирует request payload.
3. Backend упаковывает релевантный notebook-context.
4. Backend вызывает LLM integration.
5. Backend возвращает сгенерированный код во frontend.

Backend возвращает код для прямой вставки в выбранный notebook-block.

Backend не раскрывает provider credentials браузеру.

## 14. Интеграции и Background Work

Backend интегрируется с:

- email delivery provider
- LLM provider
- Google OAuth

Provider-specific логика находится в `integrations/`.

Правила background work для Version 1:

- email delivery может использовать `FastAPI BackgroundTasks`
- AI-запросы остаются синхронными backend operations
- backend не вводит отдельную queue system

## 15. Безопасность и Access Control

Backend обеспечивает:

- аутентифицированный доступ к приватным notebook
- проверку ownership notebook
- server-side валидацию session
- правила проверки OTP
- валидацию OAuth state
- server-side защиту provider credentials

Notebook-код и AI-сгенерированный код считаются untrusted.

## 16. Ошибки и Response Semantics

Backend использует стандартную HTTP response semantics.

Основные классы response:

- `200` и `201` для успешных операций чтения и записи
- `401` для неаутентифицированного доступа
- `403` для запрещенного доступа
- `404` для отсутствующих ресурсов
- `409` для sync-конфликтов
- `422` для невалидных request payload

## 17. Связанные документы

- [system_architectureRU.md](../../docs/system_architectureRU.md)
- [tech_stackRU.md](../../docs/tech_stackRU.md)
- [ui_architectureRU.md](../../ui/docs/ui_architectureRU.md)
