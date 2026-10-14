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
| `POST /api/v1/chat/query` | Body `{question, assetTag?, desiredFormat?, history?}`. Waits for the complete answer and returns a `ChatAnswer` (below). |
| `POST /api/v1/chat/stream` | Same body. **Server-Sent Events** while the answer is written. See the event list below. |
| `PATCH /api/v1/chat/{queryId}/feedback` | Body `{feedback: 1 \| -1 \| null}`, only on your own answers (or as admin). |

**Request body:**
- `desiredFormat`: `quick_answer` (default), `paragraph`, `bullet`, `table` or `report`, which are free text; or `work_order` / `checklist`, which are structured JSON validated against a schema and also returned in `structured`.
- `history`: earlier turns `[{role: "user" | "assistant", content}]`. The last 3 exchanges are used to rewrite a follow-up such as "why was that needed?" as a standalone question, which the response returns in `question`.

**`ChatAnswer`:**

| Field | Meaning |
|---|---|
| `answer` | Markdown text. Facts carry `[S1]`-style markers that refer to `citations[].label`. |
| `mode` | `llm`: written by the language model from the sources. `extractive`: evidence summary, because the model is offline or disabled; `notice` then says so. `assistant`: a greeting. `no-evidence`: refused before generation (unknown asset, or nothing relevant enough). |
| `refused` | `true` when the system declined to answer (an answer starting with "Insufficient evidence:", or `no-evidence`). |
| `evidenceStrength` | `high`, `medium` or `low`, from the reranker relevance of the **cited** sources and the checks below. It replaces the old confidence percentage. The thresholds are provisional until Phase 7 calibrates them. |
| `grounding` | The automatic checks: `citedSources`; `invalidCitations` (`[S#]` markers that name no source, which are removed from the answer); `ungroundedNumbers` (numbers found in no source); `miscitedNumbers` (found in a source other than the one cited); `unsupportedSentences` (factual statements without a citation); `claims`. |
| `warnings` | The same findings, as sentences for display. |
| `notice` | For example, "LLM offline: showing top evidence." |
| `citations[]` | The sources given to the model, in rank order: `label` (`S1`…), `cited`, `filename`, `page`, `excerpt`, and `relevance` (reranker probability 0–1). |
| `model`, `question`, `structured`, `queryId` | Model tag; the question actually answered; work-order or checklist JSON; query log id. |
| `confidence` | **Deprecated.** The relevance of the best cited source; use `evidenceStrength`. |

**Stream events** (`text/event-stream`, each `data` is JSON):
1. `status`: `{stage: rewriting | retrieving | generating | queued, position?}`. `queued` means every model slot is busy; `position` 1 means the question is next.
2. `sources`: `{question, citations[]}`, the evidence given to the model.
3. `token` (repeated): `{text}`, as generated. Free-text formats only.
4. `done`: the final `ChatAnswer`, checked and normalized. Display this instead of the streamed text.
5. `error`: a problem body, for example `429` when the model's queue is full.

**Stopping:** close the connection to stop. Generation stops on the GPU too, and the partial answer is logged with `mode: "stopped"`.

**Other rules:**
- **Insufficient evidence:** if even the best passage is below `MIN_EVIDENCE_SCORE`, the answer says so (`no-evidence`, no citations). If relevant documents exist but lack the specific fact, the model answers "Insufficient evidence: …".
- **Unknown assets:** questions naming an asset that no document mentions get an explicit "no indexed documents mention …" answer.
- **Load:** at most `LLM_CONCURRENCY` (2) answers are generated at once, and the rest wait in order. With more than `LLM_MAX_QUEUE` (16) waiting, the API answers `429` with `Retry-After: 30`.

## Assets, RCA, analytics, dashboard

| Method and path | Purpose |
|---|---|
| `GET /api/v1/assets` | Equipment from the registry plus tags found in documents: `{tag, name, assetClass, location, criticality, inRegistry, documentCount, failureEvents, lastEventDate}`. |
| `POST /api/v1/assets/import` | Admin. Multipart CSV with header `tag,name,class,location,criticality,manufacturer,notes` (criticality A/B/C or high/medium/low). Upserts and returns `{created, updated, skipped[]}`. Once a registry exists, only registered tags are recognised in documents, so re-index afterwards. |
| `GET /api/v1/assets/{tag}` | Asset 360: registry fields; `timeline` (dated events grouped by date and source, oldest first); `events[]` (`date, kind: failure \| action \| measurement \| reading, label, value, unit, detail, source`); failures, actions, measurements and sources. `404` if nothing is indexed for the tag. |
| `POST /api/v1/rca/{tag}` | RCA brief (engineer or admin). The language model drafts it as schema-validated JSON from the asset's 6 most relevant chunks, which takes about 15–30 s. `observedProblem`, `probableCauses`, `recordedActions`, `recommendedInvestigation` and `preventiveActions` carry `[S#]` citations. `measurements` and `eventDates` come from the index, not the model. Also returns `mode`, `evidenceStrength`, `grounding`, `warnings`, `notice` and `citations[]` with `label` and `cited`. Falls back to the extractive brief if the model is offline. |
| `GET /api/v1/rca/export/{tag}` | The same brief as `.docx`. Briefs are cached for 15 minutes per asset and evidence, so this exports the one just shown. |
| `GET /api/v1/analytics` | Distinct failure and action **events** (asset, date, label), and assets ranked by failure events. |
| `GET /api/v1/dashboard` | Counts, asset tags (registry plus discovered), recent questions; `aiOnline` and `llmStatus` (whether the language model is reachable, and its detail). |

## Health and metrics (no auth)

| Path | Purpose |
|---|---|
| `GET /api/v1/health/live` | The process is up. |
| `GET /api/v1/health/ready` | Database, pgvector, uploads, retrieval models, Redis and a live worker (heartbeat within 30 s); `503` with per-check detail if one fails. In inline mode Redis and the worker report `inline`. The `llm` check (model loaded, share on the GPU) is **optional**: if it fails, the status is `degraded` but HTTP `200`, because answers fall back to extractive. |
| `GET /metrics` | Prometheus metrics, including `indusmind_llm_calls_total{kind,outcome}`, `indusmind_llm_call_seconds`, `indusmind_llm_tokens_total`, `indusmind_llm_queue_waiting` and `indusmind_llm_circuit_open`. |
