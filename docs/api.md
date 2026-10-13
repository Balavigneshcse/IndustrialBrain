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

  Counters are shared through Redis when it is configured.

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
| `POST /api/v1/documents/upload` | Multipart, field `file`. Returns **`202`** with the document (`status: "queued"`) and a `jobId`; a worker processes it in the background. Errors: `415` disallowed type or content that doesn't match its extension (allowed: PDF, DOCX, XLSX, PPTX, TXT, CSV, MD, JSON, XML, HTML, EML, PNG, JPG, TIFF, BMP); `413` over `MAX_UPLOAD_MB` (default 50); `409` the same file (SHA-256) was already uploaded, with `documentId` of the existing one. |
| `GET /api/v1/documents?limit=&offset=` | Newest first. `status` is `queued`, `processing`, `ready` or `failed` (with `errorMessage`); `chunkCount`. |
| `GET /api/v1/documents/{id}` | One document, with the `jobId` of its latest job. |
| `GET /api/v1/documents/{id}/events` | **Server-Sent Events**: a `status` event (`{status, progress, errorMessage}`) on every change, until `ready`/`failed`. |
| `POST /api/v1/documents/{id}/reindex` | Re-run extraction and indexing (`202` + `jobId`). Own documents, or any as admin. `409` if already processing. |
| `DELETE /api/v1/documents/{id}` | Removes the record, its chunks, events and jobs, and the stored file. |
| `GET /api/v1/jobs/{id}` | `{kind, status: queued \| running \| succeeded \| failed, progress 0-100, error, documentId, timestamps}`. |

Processing extracts text (with OCR for scans and images) and splits it at headings and dated log entries. It tags each chunk with its subject equipment (negated mentions such as "no relation to P-101" are excluded), derives dated asset events from record documents, and embeds every chunk.

## Chat

| Method and path | Purpose |
|---|---|
| `POST /api/v1/chat/query` | Body `{question, assetTag?, desiredFormat?}`. Returns `{answer, mode, format, confidence, citations[], assetTag, queryId}`. |
| `PATCH /api/v1/chat/{queryId}/feedback` | Body `{feedback: 1 \| -1 \| null}`, only on your own answers (or as admin). |

About the chat response:
- **`mode`** is `extractive` (no language model yet) or `assistant` (greetings).
- **`citations[].relevance`** is the reranker's relevance probability (0–1), highest first.
- **Insufficient evidence:** if even the best passage is below `MIN_EVIDENCE_SCORE`, the answer says so and has no citations.
- **Unknown assets:** questions naming an asset no document mentions get an explicit "no indexed documents mention …" answer.

## Assets, RCA, analytics, dashboard

| Method and path | Purpose |
|---|---|
| `GET /api/v1/assets` | Equipment from the registry plus tags found in documents: `{tag, name, assetClass, location, criticality, inRegistry, documentCount, failureEvents, lastEventDate}`. |
| `POST /api/v1/assets/import` | Admin. Multipart CSV with header `tag,name,class,location,criticality,manufacturer,notes` (criticality A/B/C or high/medium/low). Upserts and returns `{created, updated, skipped[]}`. Once a registry exists, only registered tags are recognised in documents, so re-index afterwards. |
| `GET /api/v1/assets/{tag}` | Asset 360: registry fields; `timeline` (dated events grouped by date and source, oldest first); `events[]` (`date, kind: failure \| action \| measurement \| reading, label, value, unit, detail, source`); failures, actions, measurements and sources. `404` if nothing is indexed for the tag. |
| `POST /api/v1/rca/{tag}` | RCA brief built from the chunks whose subject is the asset (engineer or admin). |
| `GET /api/v1/rca/export/{tag}` | The same brief as `.docx`. |
| `GET /api/v1/analytics` | Distinct failure and action **events** (asset, date, label), and assets ranked by failure events. |
| `GET /api/v1/dashboard` | Counts, asset tags (registry plus discovered), recent questions. |

## Health and metrics (no auth)

| Path | Purpose |
|---|---|
| `GET /api/v1/health/live` | The process is up. |
| `GET /api/v1/health/ready` | Database, pgvector, uploads, retrieval models, Redis and a live worker (heartbeat within 30 s); `503` with per-check detail if not. In inline mode Redis/worker report `inline`. |
| `GET /metrics` | Prometheus metrics. |
