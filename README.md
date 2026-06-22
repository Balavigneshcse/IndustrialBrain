# IndusMind AI

**Industrial Asset Intelligence & RCA Copilot**

IndusMind AI converts fragmented maintenance records, inspection reports, OEM guidance, safety procedures, and operating data into a searchable industrial knowledge layer. It answers natural-language questions with source citations, builds an Asset 360° history, and creates evidence-linked root-cause investigation briefs.

> The included industrial documents are synthetic demonstration data. RCA output is decision support and requires engineering verification.

## Why this project is different

- Evidence-first RAG with source document, page, excerpt, relevance, and confidence
- Asset 360° view connecting failures, measurements, maintenance actions, and dates
- RCA support that separates observations, probable contributors, investigation steps, and prevention
- Gemini generation when an API key is available
- Fully usable offline evidence-summary fallback when it is not
- JWT authentication with Admin and Engineer roles
- PostgreSQL production profile plus an H2 zero-setup demonstration profile
- Embedded persistent ChromaDB; no separate vector server

## Technology stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite |
| Main API | Java 21+, Spring Boot 3.5, Spring Security, JPA |
| AI service | Python 3.11+, FastAPI |
| Structured data | PostgreSQL; H2 demo fallback |
| Vector data | ChromaDB persistent local mode |
| Generation | Google Gemini API, optional |
| Extraction | PyPDF, python-docx, CSV |
| OCR | Tesseract OCR, optional for scanned PDFs |

## Quick start — easiest demo mode

### Prerequisites

- Java 21 or newer
- Maven 3.9+
- Node.js LTS
- Python 3.11+
- Git

Open PowerShell in the repository root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-all.ps1 -DemoMode
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\load-sample-data.ps1
```

Open [http://localhost:5173](http://localhost:5173).

### Demo accounts

| Role | Username | Password |
|---|---|---|
| Administrator | `admin` | `Admin@123` |
| Engineer | `engineer` | `Engineer@123` |

Try:

> Why did Pump P-101 fail repeatedly in 2025?

Stop all services:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop-all.ps1
```

## PostgreSQL mode

1. Install PostgreSQL and create the database:

```powershell
psql -U postgres -f .\database\create-database.sql
```

2. Configure environment variables if your credentials differ:

```powershell
$env:DB_URL="jdbc:postgresql://localhost:5432/indusmind"
$env:DB_USER="postgres"
$env:DB_PASSWORD="your-password"
```

3. Start without `-DemoMode`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-all.ps1
```

Spring JPA creates the application tables.

## Optional Gemini setup

1. Create a key in [Google AI Studio](https://aistudio.google.com/).
2. Copy `ai-service/.env.example` to `ai-service/.env`.
3. Set:

```text
GEMINI_API_KEY=your-key
GEMINI_MODEL=gemini-2.5-flash
```

Never commit `.env`. Without a key, the system automatically uses offline evidence-summary mode.

## Optional scanned-PDF OCR

Install Tesseract OCR, then set `TESSERACT_CMD` in `ai-service/.env`, for example:

```text
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

Text PDFs, DOCX, TXT, and CSV work without Tesseract.

## Verification

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\health-check.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\smoke-test.ps1
```

Individual builds:

```powershell
cd backend
mvn test

cd ..\ai-service
.\.venv\Scripts\python.exe -m pytest -q

cd ..\frontend
npm.cmd run build
```

## Repository structure

```text
frontend/       React application
backend/        Spring Boot API and security
ai-service/     FastAPI extraction, retrieval, generation, RCA
sample-data/    Synthetic industrial demonstration corpus
database/       PostgreSQL initialization
scripts/        Setup, start, stop, health, sample-load, smoke-test
docs/           Architecture, evaluation, detailed documentation
presentation/   Hackathon presentation deck
demo-video/     Narration script and shot list
```

## Architecture

React communicates only with Spring Boot. Spring Boot owns authentication, metadata, query logs, and access control. FastAPI processes locally stored files, extracts entities, builds page-aware chunks, searches ChromaDB, and returns answers with evidence. Gemini is an optional generation layer, not a runtime dependency.

See [system architecture](docs/architecture/system-architecture.md) and [data flow](docs/architecture/data-flow.md).

## Security and limitations

- Passwords are BCrypt-hashed.
- API access uses signed, expiring JWTs.
- API keys and database passwords are excluded from Git.
- The demo accounts must be changed before production use.
- The prototype is not a certified predictive-maintenance or safety system.
- Scanned PDFs require local OCR dependencies.
- The synthetic benchmark is functional validation, not independent industrial validation.

## Submission assets

- Detailed report: `docs/IndusMind_AI_Detailed_Project_Report.docx`
- Presentation: `presentation/IndusMind_AI_Hackathon_Pitch.pptx`
- Demo script: `demo-video/DEMO_SCRIPT.md`
- Benchmark: `docs/evaluation/benchmark.md`

## License

Apache License 2.0. See `LICENSE` and `NOTICE.md`.

