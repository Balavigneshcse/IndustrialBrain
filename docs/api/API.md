# API Reference (v1)

FastAPI server on port 8000.
- **Machine-readable contract:** `/api/v1/openapi.json`
- **Interactive docs:** `/api/v1/docs`

The Phase 4 frontend generates its client from that contract. The old unversioned `/api/...` paths still work as a hidden alias for the current UI and are removed in Phase 4.

## Conventions

- **Auth:** every endpoint except login, refresh, logout and health requires `Authorization: Bearer <access token>`.
- **Errors:** RFC 7807 `application/problem+json`: `{type, title, status, detail, instance, requestId}`. Validation errors add `errors[]`.
- **Request IDs:** every response carries `X-Request-ID`. Send your own value to correlate requests with logs.
- **Rate limits:** `429` with `Retry-After` on exceeding the per-minute limits:
  - login: 5 per IP
  - chat: 20 per user
  - upload: 30 per user

## Roles

| Action | viewer | engineer | admin |
|---|---|---|---|
| Dashboard, documents list, chat, Asset 360, analytics | ✓ | ✓ | ✓ |
| Upload documents, generate or export RCA | – | ✓ | ✓ |
| Delete documents | – | own | any |
| Manage users | – | – | ✓ |

## Authentication

| Method and path | Purpose |
|---|---|
| `POST /api/v1/auth/login` | Body `{username, password}`. Returns `{token, tokenType, expiresIn, username, displayName, role}` and sets the httpOnly `indusmind_refresh` cookie. `401` wrong credentials; `423` locked after 5 failures (15 minutes). |
| `POST /api/v1/auth/refresh` | Exchanges the refresh cookie for a new access token; the cookie rotates every time. Replaying an old cookie ends all of the user's sessions. |
| `POST /api/v1/auth/logout` | Revokes the refresh cookie (`204`). |
| `GET /api/v1/auth/me` | The current user. |
| `POST /api/v1/auth/change-password` | Body `{currentPassword, newPassword}`. Ends other sessions and returns fresh tokens. |

Access tokens last 15 minutes. Any password change or reset invalidates previously issued tokens.

## Users (admin)

| Method and path | Purpose |
|---|---|
| `GET /api/v1/users` | List users. |
| `POST /api/v1/users` | Body `{username, displayName, email?, role, password}`. Returns `201`; `409` username taken; `422` weak password (at least 8 characters, not the username). |
| `PATCH /api/v1/users/{id}` | Body `{displayName?, email?, role?, isActive?}`. Returns `409` if this would remove the last active admin. Deactivating ends the user's sessions. |
| `POST /api/v1/users/{id}/reset-password` | Body `{newPassword}`. Also unlocks the account and ends its sessions. |

## Documents

| Method and path | Purpose |
|---|---|
| `GET /api/v1/documents?limit=&offset=` | Newest first. Each item has `status` (`ready`, `failed` or `processing`) and `errorMessage`. |
| `POST /api/v1/documents/upload` | Multipart, field `file`, up to `MAX_UPLOAD_MB` (default 50; `413` beyond). Accepts PDF, DOCX, TXT, CSV, XLSX, PPTX, HTML, EML and images (OCR). Unreadable files return `status: "failed"` with a reason and are not indexed. |
| `DELETE /api/v1/documents/{id}` | Removes the record, its indexed chunks and the stored file. |

## Chat

| Method and path | Purpose |
|---|---|
| `POST /api/v1/chat/query` | Body `{question, assetTag?, desiredFormat?}`. Returns `{answer, mode, format, confidence, citations[], assetTag, queryId}`. `mode` is `extractive` (no language model yet) or `assistant` (greetings). Questions naming an asset no document mentions get an explicit "no indexed documents mention …" answer. |
| `PATCH /api/v1/chat/{queryId}/feedback` | Body `{feedback: 1 \| -1 \| null}`, only on your own answers (or as admin). |

## Assets, RCA, analytics, dashboard

| Method and path | Purpose |
|---|---|
| `GET /api/v1/assets/{tag}` | Asset 360 evidence (exact tag match; `404` if none). |
| `POST /api/v1/rca/{tag}` | RCA brief (engineer or admin). |
| `GET /api/v1/rca/export/{tag}` | The same brief as `.docx`. |
| `GET /api/v1/analytics` | Failure and action term mentions, assets ranked by failure mentions. |
| `GET /api/v1/dashboard` | Counts, asset tags, recent questions. |

## Health and metrics (no auth)

| Path | Purpose |
|---|---|
| `GET /api/v1/health/live` | The process is up. |
| `GET /api/v1/health/ready` | Database, pgvector and uploads are usable (`503` with per-check detail if not). |
| `GET /metrics` | Prometheus metrics. |
