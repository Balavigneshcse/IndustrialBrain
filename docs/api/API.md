# API Reference

FastAPI server, port 8000. Interactive documentation lives at `http://127.0.0.1:8000/docs`.

Every endpoint except login and health requires:

```http
Authorization: Bearer <token>
```

## Authentication

### `POST /api/auth/login`

```json
{"username": "admin", "password": "Admin@123"}
```

Returns `token` (JWT, valid 24 h), `username`, `displayName` and `role`.

## Documents

- `GET /api/documents`: list documents with status (`ready` or `failed`) and `errorMessage`.
- `POST /api/documents/upload`: multipart upload, field `file`. Supported: PDF, DOCX, TXT, CSV, XLSX, PPTX, HTML, EML, and images (OCR). Extraction failures return `status: "failed"` and are not indexed.
- `DELETE /api/documents/{id}`: removes the record, its index entries and the stored file.

## Dashboard

- `GET /api/dashboard`: document, asset and query counts, asset tags, recent questions, and `aiOnline` (the evidence index is reachable).

## Chat

### `POST /api/chat/query`

```json
{"question": "Why did Pump P-101 fail repeatedly in 2025?", "assetTag": "P-101", "desiredFormat": "quick_answer"}
```

Returns `answer`, `mode` (`extractive` or `assistant`), `confidence` (heuristic), `citations[]` and `queryId`. Questions that name an asset no indexed document mentions get an explicit "no indexed documents mention …" answer with no citations.

- `PATCH /api/chat/{queryId}/feedback` with body `{"feedback": 1 | -1}`.

## Assets and RCA

- `GET /api/assets/{tag}`: Asset 360 evidence (exact tag match; 404 if none).
- `POST /api/rca/{tag}`: RCA brief (`observedProblem`, `probableCauses`, `recordedActions`, `measurements`, `eventDates`, `recommendedInvestigation`, `preventiveActions`, `confidence`, `citations`).
- `GET /api/rca/export/{tag}`: the same brief as a `.docx` download.

## Analytics

- `GET /api/analytics`: top failure modes and actions (term mentions across chunks), and assets ranked by failure mentions.

## Health

- `GET /api/health`
