# Smart Curriculum Activity & Attendance App

A role-based academic portal for attendance, curriculum progress, assignments, assessments, academic risk indicators, and document-grounded academic assistance.

## Problem and objectives

The application brings classroom attendance and academic progress into one place. It provides students with their own attendance and coursework, lets teachers manage assigned classes, and gives administrators institutional configuration and oversight. Academic numbers and risk indicators are calculated from stored records by the backend.

## Features

- Admin, teacher, and student accounts with JWT authentication and role/scope checks.
- Academic years, semesters, departments, classes, divisions, batches, subjects, assignments, and timetables.
- Teacher-created attendance sessions with rotating, expiring QR tokens; student camera scanning or manual token entry; duplicate prevention; teacher monitoring and audited corrections.
- Subject attendance histories, summaries, and defaulter reports.
- Curriculum units/topics and progress, assignment submissions and evaluation, assessments and performance, activities, academic gaps, alerts, and next-best actions.
- Optional PDF-backed academic assistant with document citations, per-user chat history, and Qdrant retrieval. Provider keys remain on the backend.

## Technology and architecture

- **Frontend:** React 19, Vite, Lucide, QRCode SVG, and ZXing browser QR decoding.
- **Backend:** Python 3.13, FastAPI, Pydantic, SQLAlchemy 2, Alembic.
- **Relational database:** MySQL 8.0 (SQLite is used only by isolated verification scripts).
- **RAG:** pypdf extraction and text chunking, a configured OpenAI-compatible embeddings endpoint, Qdrant, and a configured OpenAI-compatible chat-completions endpoint.
- **Authentication:** bearer JWTs, password hashing, role checks, and student/teacher record scoping.

The React app calls `/api`; in development Vite proxies it to FastAPI. The Docker frontend uses Nginx to proxy `/api` to the backend and serve the single-page app. Swagger/OpenAPI is generated at `/docs`.

## Main modules and data

- **Identity:** users, students, teachers, role-based access.
- **Academic structure:** academic years, semesters, departments, classes, divisions, batches, subjects, assignments, timetables.
- **Attendance:** sessions, attendance records, correction/audit history.
- **Academic progress:** curriculum units/topics, topic progress, assignments/submissions, assessments/results, activities, alerts, risk records, recommendations, notifications, and gap snapshots.
- **Academic documents:** document metadata and relational chunk records; vector payloads are stored in the configured Qdrant collection.
- **Assistant:** user-scoped question/answer history and source citations.

The backend has additive Alembic migrations under `backend/migrations/versions`. They preserve existing records; review and back up a database before applying migrations.

## Requirements

- Python 3.10+ (Python 3.13 is used by the backend image).
- Node.js compatible with the installed Vite release (Node 20.19+ or 22.12+).
- MySQL 8.0 for normal application use.
- Optional for the assistant: an embeddings endpoint, Qdrant, and an OpenAI-compatible chat endpoint.
- Docker Compose is optional; it is not required for local development.

## Local setup

### Backend

In PowerShell:

```powershell
cd backend
Copy-Item .env.example .env
# Edit .env: configure DB credentials and a unique JWT_SECRET_KEY.
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create the `attendance_management` database in MySQL if it does not exist. For a new empty database, from `backend` run:

```powershell
python -m app.init_db
alembic upgrade head
```

For an existing database, back it up and run `alembic upgrade head`; do not use `app.init_db` as a production migration substitute. Set `INIT_ADMIN_PASSWORD` and run `python create_admin.py` if an initial administrator is needed.

Start the API from `backend`:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API health: <http://127.0.0.1:8000/api/health>
- Swagger: <http://127.0.0.1:8000/docs>

### Frontend

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

Open <http://127.0.0.1:5173>. Camera scanning requires a secure browser context (HTTPS or localhost) and camera permission.

## Environment configuration

The full backend variable reference is in [`backend/.env.example`](./backend/.env.example). At minimum, local backend use needs:

- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- `JWT_SECRET_KEY` (use a unique high-entropy secret; production requires at least 32 characters)
- `APP_ENV` and production `ALLOWED_ORIGINS` (explicit origins; wildcard CORS is rejected in production)
- `INIT_ADMIN_PASSWORD` only when creating an initial administrator

Optional RAG variables: `EMBEDDING_API_URL`, `EMBEDDING_API_KEY`, `EMBEDDING_MODEL`, `QDRANT_URL`, `QDRANT_API_KEY`, `QDRANT_COLLECTION`, `LLM_API_URL`, `LLM_API_KEY`, and `LLM_MODEL`. Keep provider keys on the backend. The assistant returns an explicit unavailable error when providers are not configured.

## Verification

Run the isolated, SQLite-backed suite from the repository root or `backend`:

```powershell
python backend\verify_all_modules.py
```

It runs `verify_phase2.py`, `verify_phase4.py`, and `verify_phase5.py` without connecting to or changing the configured MySQL database or contacting live AI services. Provider calls in Phase 5 tests are mocked.

Frontend checks:

```powershell
cd frontend
npm run build
npm run lint
```

`backend/verify_module_1*.py` are legacy live-database scripts; some create and clean up records matching their test prefixes. Do not run them against a database containing records you need to preserve. The `live_api_verify.py` and `live_e2e_test.py` scripts also target a running local API/database and are not part of the isolated suite.

## Docker Compose (local/demo)

Docker Compose is an optional local demonstration path. Copy the root template to `.env`, replace both secrets with unique values, and retain your existing database password if using an existing MySQL volume:

```powershell
Copy-Item .env.example .env
# Edit .env before starting services.
docker compose up -d db
docker compose run --rm backend python -m app.init_db
docker compose run --rm backend alembic upgrade head
docker compose up --build -d
```

Open <http://localhost:8080>; the frontend proxies API requests through Nginx. The API is at <http://localhost:8000>. Persistent MySQL data is stored in the `mysql_data` volume. Do not use `docker compose down -v` unless you explicitly intend to delete that database volume. Compose binds its ports to localhost; place a TLS reverse proxy in front before exposing a deployment publicly.

For a frontend hosted separately, set build-time `VITE_API_BASE_URL` to the backend’s public API URL ending in `/api`, and configure backend `ALLOWED_ORIGINS` with the exact frontend origin. Provision MySQL and optional Qdrant separately, apply migrations after backup, and set secrets through the hosting platform—not source code. No paid service or external deployment is performed by this project.

## API reference

FastAPI’s interactive Swagger UI and OpenAPI schema are available at `/docs` and `/openapi.json` when the backend is running. See [`backend/README.md`](./backend/README.md) for routes, authorization scopes, database initialization, migration, and RAG details.

## Demonstration sequence

1. **Admin:** configure academic year/semester, department, class/division/batch, and subject; create teacher/student accounts and subject/class assignments.
2. **Teacher:** sign in, open an assigned class, start attendance, display the live QR, and show token refresh plus live roster updates.
3. **Student:** sign in in a second browser, scan the displayed QR or enter the token, confirm attendance, and show that a duplicate submission is rejected.
4. **Teacher/Admin:** inspect attendance records/reports; use a correction only with an audit reason.
5. **Teacher:** add curriculum units/topics, assignments, or assessments; update progress and evaluate submissions.
6. **Student:** review attendance, progress, assignments, assessment results, and backend-computed recommendations.
7. **Academic assistant:** upload a text-based PDF as an authorized staff account, configure embeddings/Qdrant/LLM, ask a subject-scoped question, and inspect its citations. This step requires real provider configuration and an indexed document.

## Known limitations

- PDF embedding/indexing and assistant calls are synchronous; there is no background job queue.
- Live AI behavior requires separately configured providers and Qdrant; local Phase 5 tests mock those services.
- OCR is not included; scanned image-only PDFs without extractable text are rejected.
- QR tokens expire and rotate, but a live QR can still be shared; location/presence verification is not implemented.
- Some detailed teacher-level aggregate charts and topic-level UI workflows may be limited by current API coverage; see `frontend/README.md`.
