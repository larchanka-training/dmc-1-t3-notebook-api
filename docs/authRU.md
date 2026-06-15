# Контракт аутентификации API

## 1. Назначение

Этот документ определяет контракт аутентификации backend API с точки зрения реализации.

Статус:

- целевой контракт для планируемой реализации Version 1
- не описание текущего состояния реализации в репозитории

Документ охватывает:

- поддерживаемые потоки аутентификации для Version 1
- формы request и response
- поведение session и cookie
- семантику валидации и ошибок
- направление персистентности backend для auth-связанных записей

Документ согласован с:

- [../../dmc-1-t3-notebook-mono/docs/system_architecture.md](../../dmc-1-t3-notebook-mono/docs/system_architecture.md)
- [../../dmc-1-t3-notebook-mono/docs/tech_stack.md](../../dmc-1-t3-notebook-mono/docs/tech_stack.md)
- [./api_architecture.md](./api_architecture.md)

## 2. Зафиксированный контракт для Version 1

Следующий auth-контракт зафиксирован для Version 1:

1. Основной метод входа: `Email + OTP`.
2. Дополнительный опциональный метод входа: `Google OAuth`.
3. Аутентифицированное browser-state передается через backend-managed secure `HTTP-only` session cookie.
4. Auth-state на frontend выводится из backend session validation.
5. Frontend не должен зависеть от bearer-токенов, читаемых на стороне frontend.

Важная граница:

- внешний auth-контракт основан на `session cookie`
- backend может реализовать эту session через opaque session identifier или `JWT` внутри cookie
- этот внутренний выбор не должен менять API-контракт

## 3. Общие соглашения

### 3.1 Content Type

JSON endpoints используют:

- request: `Content-Type: application/json`
- response: `Content-Type: application/json`

### 3.2 Транспорт аутентификации

Защищенные endpoints полагаются на session cookie, автоматически отправляемую браузером.

Frontend должен использовать credentialed requests, чтобы cookie включались в запрос.

### 3.3 Временные значения

Поля response, такие как `created_at`, `updated_at`, `expires_at` и `authenticated_at`, должны использовать ISO 8601 timestamps в UTC.

### 3.4 Форма ошибки

Рекомендуемая форма error response:

```json
{
  "error": {
    "code": "otp_invalid",
    "message": "The provided OTP code is invalid."
  }
}
```

Точная формулировка может отличаться, но значения `code` должны оставаться достаточно стабильными для обработки на frontend.

## 4. Форма краткого описания пользователя

Аутентифицированные responses должны возвращать компактную форму пользователя:

```json
{
  "user": {
    "id": "0f1b9d40-59d8-4d77-b90d-2e0bcedd91b5",
    "email": "user@example.com",
    "display_name": null
  }
}
```

Минимальные поля пользователя:

- `id`
- `email`
- опционально `display_name`

## 5. Endpoints Email + OTP

### 5.1 `POST /api/v1/auth/request-otp`

Создает OTP challenge для нормализованного email.

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

Примечания к response:

- `dev_otp` должен возвращаться только в явно разрешенных окружениях `local/dev`
- production responses не должны включать `dev_otp`

#### Правила валидации

- email должен присутствовать
- email должен быть нормализован
- формат email должен быть валидным

#### Случаи ошибок

- `422 Unprocessable Entity` для невалидного payload
- `429 Too Many Requests` при нарушении rate limit или throttle

Пример:

```json
{
  "error": {
    "code": "otp_request_rate_limited",
    "message": "Too many OTP requests. Try again later."
  }
}
```

### 5.2 `POST /api/v1/auth/verify-otp`

Проверяет OTP challenge и устанавливает аутентифицированную session.

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

Дополнительное поведение:

- response должен устанавливать session cookie
- успешная верификация должна инвалидировать OTP challenge

#### Случаи ошибок

- `422 Unprocessable Entity` для невалидного формата payload
- `401 Unauthorized` для невалидного или истекшего OTP challenge
- `409 Conflict`, если challenge больше не валиден, потому что был заменен или уже использован
- `429 Too Many Requests` при исчерпании попыток или нарушении throttle

Рекомендуемые коды ошибок:

- `otp_invalid`
- `otp_expired`
- `otp_challenge_not_found`
- `otp_attempt_limit_exceeded`

### 5.3 Опциональный `POST /api/v1/auth/resend-otp`

Этот endpoint опционален для первого implementation slice.

Если реализован, он должен либо:

- создавать новый challenge и инвалидировать предыдущий
- либо повторно отправлять OTP только при строго контролируемых лимитах

## 6. Session Endpoints

### 6.1 `GET /api/v1/auth/session`

Возвращает текущее состояние аутентифицированной session.

#### Success Response для аутентифицированного пользователя

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

#### Success Response для анонимного пользователя

Status:

- `200 OK`

Body:

```json
{
  "authenticated": false,
  "user": null
}
```

Этот endpoint должен позволять frontend инициализировать auth-state без предположений на основе видимости cookie.

### 6.2 `POST /api/v1/auth/logout`

Инвалидирует текущую session.

#### Success Response

Status:

- `200 OK`

Body:

```json
{
  "logged_out": true
}
```

Дополнительное поведение:

- инвалидировать session на стороне backend или эквивалентное token-state
- очистить session cookie в response

## 7. Google OAuth Endpoints

### 7.1 `GET /api/v1/auth/google/start`

Запускает поток Google OAuth.

Поведение:

- сгенерировать и сохранить OAuth state
- перенаправить браузер на авторизацию Google

Response:

- `302 Found` redirect к провайдеру

### 7.2 `GET /api/v1/auth/google/callback`

Обрабатывает callback провайдера.

Поведение:

- проверить OAuth state
- найти или создать пользователя
- установить аутентифицированную session
- установить session cookie
- перенаправить браузер в frontend-приложение

Response:

- `302 Found` redirect обратно на frontend

Поведение при ошибке:

- невалидный или отсутствующий state должен приводить к контролируемому auth error flow
- не раскрывать пользователю сырые детали ошибок провайдера

## 8. Контракт Session Cookie

### 8.1 Обязательные свойства

Production session cookies должны использовать:

- `HttpOnly`
- `Secure`
- `SameSite=Lax` или строже, если совместимо с финальным UX
- `Path=/`

Рекомендуемое направление:

- ограниченный срок жизни
- явная стратегия ротации и инвалидации

### 8.2 Локальная разработка

Если локальный HTTPS доступен, оставляйте `Secure` включенным.

Если нет, конфигурация только для local может ослабить `Secure`, но это должно оставаться привязанным к окружению и никогда не попадать в production.

### 8.3 Выбор содержимого Cookie

Cookie может содержать:

- opaque session identifier
- или подписанный token, например `JWT`

Это внутренняя деталь реализации backend.

Frontend должен обрабатывать оба случая одинаково.

## 9. Правила валидации и безопасности

### 9.1 Правила Email + OTP

Рекомендуемые ограничения OTP для Version 1:

- числовой `6-digit` OTP
- срок действия `5 to 10 minute`
- строгий лимит попыток на challenge
- throttling по email и IP
- инвалидация challenge после успешной верификации

### 9.2 Обработка ввода

- нормализовать email перед lookup или созданием
- валидировать `otp_code` как ограниченное кодовое значение, а не произвольный текст
- отклонять malformed JSON или отсутствующие обязательные поля
- валидировать все OAuth redirect-state параметры

### 9.3 Правила логирования

- не логировать значения OTP в production
- не логировать сырые session secrets
- логировать auth failures с безопасными structured metadata

### 9.4 Безопасность Session

- session identifiers или signed tokens должны иметь высокую энтропию
- session validation должна оставаться на стороне backend
- защищенные notebook endpoints должны требовать валидную активную session
- logout должен инвалидировать дальнейшее использование текущей session

Если внутри используется `JWT`:

- подпись должна выполняться на стороне backend
- верификация должна выполняться на стороне backend
- срок жизни token должен быть ограничен
- поведение revocation должно быть явно определено

## 10. Рекомендуемое направление персистентности

Backend, вероятно, потребуются auth-связанные записи для:

- `users`
- `otp_challenges`
- `sessions`
- опционально `oauth_accounts`

Рекомендуемые минимальные поля:

### 10.1 `users`

- `id`
- `email`
- `display_name` nullable
- `created_at`
- `updated_at`

### 10.2 `otp_challenges`

- `id`
- `email`
- `otp_hash` или эквивалентное хранение не в открытом виде
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
- опциональные metadata, такие как IP или user agent, если нужны

## 11. Ожидаемая обработка на Frontend

Frontend должен явно обрабатывать следующие состояния:

- `unknown`
- `anonymous`
- `authenticating`
- `authenticated`
- `session_expired`

Frontend также должен явно реагировать на:

- `401 Unauthorized`
- `403 Forbidden`
- `409 Conflict` где применимо
- `429 Too Many Requests`

## 12. Вне scope этого контракта

Этот документ не определяет:

- provider-specific Google OAuth credentials
- точное имя cookie
- точные внутренние ORM models
- точную реализацию миграций
- password authentication

Это может быть зафиксировано в implementation tasks позже без изменения контракта выше.
