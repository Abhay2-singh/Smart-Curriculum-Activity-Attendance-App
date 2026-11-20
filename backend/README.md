# Attendance Management System - Backend Foundation (Module 1A)

This is the backend foundation for the Attendance Management System built with **FastAPI**, **SQLAlchemy**, and **MySQL 8.0**.

---

## Prerequisites

- **Python 3.13** (or Python 3.10+) installed.
- **MySQL Server 8.0** running locally.
- **Git** version control.

---

## Database Setup

Before running the application, ensure the MySQL server is running and the initial database exists.

Execute the following SQL command in your MySQL client (e.g., MySQL Workbench, Command Line, or DBeaver):

```sql
CREATE DATABASE IF NOT EXISTS attendance_management;
```

---

## Environment Setup

### 1. Create and Activate Virtual Environment

Navigate to the `backend` directory:

```bash
cd backend
```

Create Python virtual environment `.venv`:

```bash
python -m venv .venv
```

Activate the virtual environment:

- **Windows (PowerShell):**
  ```powershell
  .\.venv\Scripts\Activate.ps1
  ```
- **Windows (Command Prompt):**
  ```cmd
  .\.venv\Scripts\activate.bat
  ```
- **Linux / macOS:**
  ```bash
  source .venv/bin/activate
  ```

### 2. Install Dependencies

With the virtual environment activated, run:

```bash
pip install -r requirements.txt
```

### 3. Configure `.env` File

Copy `.env.example` to `.env` if not already created:

- **Windows (PowerShell):**
  ```powershell
  Copy-Item .env.example .env
  ```
- **Linux / macOS:**
  ```bash
  cp .env.example .env
  ```

Edit `.env` and set your local MySQL database credentials:

```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_actual_mysql_password
DB_NAME=attendance_management

APP_ENV=development
APP_PORT=8000
```

> ⚠️ **IMPORTANT**: Never commit `.env` or hard-code secrets into source files. `.env` is listed in `.gitignore`.

---

## Running the Server

Start the FastAPI application using Uvicorn:

```bash
uvicorn app.main:app --reload --port 8000
```

The server will start at `http://127.0.0.1:8000`.

---

## API Endpoints & Verification

### 1. Health Check
- **Endpoint:** `GET /api/health`
- **Description:** Verifies backend runtime status.
- **Sample Response:**
  ```json
  {
    "status": "ok",
    "message": "Attendance Management System API is running"
  }
  ```

### 2. Database Health Check
- **Endpoint:** `GET /api/health/database`
- **Description:** Verifies MySQL database connection.
- **Sample Response (Success):**
  ```json
  {
    "status": "ok",
    "database": "connected",
    "database_name": "attendance_management",
    "host": "localhost",
    "port": 3306
  }
  ```

## Phase 2 Academic Features

Phase 2 extends the existing FastAPI, SQLAlchemy, and MySQL backend. It adds curriculum progress, assignments and submissions, assessments and results, student activities, academic gap/risk analysis, alerts, recommendations, notifications, and an academic-document/RAG foundation. Existing student, teacher, department, subject, semester, and QR attendance models are reused.

The new API routes are available under `/api`:

- Curriculum: `/curriculum/units`, `/curriculum/subjects/{subject_id}`, and `/curriculum/topics/{topic_id}/progress`
- Assignments: `/assignments`, `/assignments/{assignment_id}/submissions`, and `/submissions/{submission_id}/evaluate`
- Assessments: `/assessments`, `/assessments/{assessment_id}/results`, `/assessments/performance`, and `/assessments/subject-averages`
- Activities: `/activities`, `/activities/{activity_id}/participation`, `/activities/history`, and `/activities/statistics`
- Academic analysis: `/analytics/gaps`, `/analytics/analyze`, `/analytics/risks`, `/analytics/gap-history`, `/alerts`, and `/recommendations`
- Notifications: `/notifications` and `/notifications/{notification_id}/read`
- Academic documents: `POST /documents`, `GET /documents`, `POST /documents/{document_id}/replace`, and `DELETE /documents/{document_id}`. PDF extraction, chunking, embeddings, and vector indexing run synchronously. Subject documents inherit department, semester, and academic-year scope; admins may additionally scope documents to a class/course.
- Academic assistant: `POST /assistant/query`, `GET /assistant/history`, and `DELETE /assistant/history`. Answers use authorized document excerpts and, for students, the authenticated student's actual attendance, syllabus, assignment, and assessment data. History belongs to the authenticated user.
- Recommendations and staff insights: `GET /recommendations/next-best-action` computes prioritized recommendations from current database records; `GET /analytics/insights` provides teacher-scoped class and admin institutional summaries.
- QR attendance uses `POST /api/attendance-sessions` to open a session and `POST /api/attendance/mark` to submit the current QR token. Teacher/admin clients rotate the QR token with `POST /api/attendance-sessions/{session_id}/refresh-token`; the previous token is invalidated immediately. `GET /api/attendance-sessions/{session_id}/monitor` returns the enrolled roster and live present/absent/not-marked counts. Student session listings omit the QR token.
- Configure QR token life and automatic refresh cadence with `ATTENDANCE_QR_TOKEN_TTL_SECONDS` and `ATTENDANCE_QR_REFRESH_INTERVAL_SECONDS`. The refresh cadence must be positive and shorter than token life. Run `alembic upgrade head` from `backend` to add `attendance_sessions.qr_token_expires_at`; existing session expirations are retained as a migration fallback.

Use the interactive Swagger UI at `http://127.0.0.1:8000/docs` to inspect request and response schemas. Authenticated endpoints require a bearer access token. Student and teacher routes are scoped to their own data and assigned academic groups.

### Environment and credentials

Copy `.env.example` to `.env` and set database credentials and a unique JWT key. An empty JWT key generates an ephemeral key in development; production startup requires `JWT_SECRET_KEY` to be set. Generate one with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set `INIT_ADMIN_PASSWORD` before creating an initial admin account. The optional college demo seeder requires `INIT_ADMIN_PASSWORD`, `SEED_TEACHER_PASSWORD`, and `SEED_STUDENT_PASSWORD`; it uses these environment values for the seeded accounts and updates those seeded accounts' password hashes when rerun. Do not reuse production credentials for demo data. The previous built-in fallback login passwords have been removed; rotate any credentials already used to seed an existing database.

### Database migration

Run commands from the `backend` directory after configuring `.env`.

- **Existing database:** back up the database, then run `alembic upgrade head`. The Phase 2 migration only adds the 16 Phase 2 tables and uses `checkfirst`; it does not drop or rewrite existing tables. The migration intentionally has no destructive downgrade.
- **New empty database:** create the database, run `python -m app.init_db` to create the existing schema, then run `alembic upgrade head` to record/apply the additive migration.

Do not run `python -m app.init_db` as a substitute for migrations on a production database. Review and back up the target database before upgrading.

### Run and test

Start the backend from `backend`:

```powershell
uvicorn app.main:app --reload --port 8000
```

Run the isolated SQLite-backed Phase 2 integration checks (no MySQL database or external AI service is contacted):

```powershell
python verify_phase2.py
```

The script exercises authentication/role checks, curriculum progress, assignment submission and evaluation, assessment calculations, activity participation, QR token marking/expiry/duplicate handling, gap/risk calculations, alert persistence, and RAG configuration guards.

Run the complete safe verification entry point from the repository root or this directory:

```powershell
python verify_all_modules.py
```

It locates its own directory and runs only the isolated Phase 2, Phase 4, Phase 5, and Phase 6 checks. These tests use SQLite and mocked AI/vector providers; they do not contact the configured MySQL database or external services. `verify_module_1*.py`, `live_api_verify.py`, and `live_e2e_test.py` are legacy live-database/API scripts. Some legacy module scripts create and delete rows under test-specific prefixes. Do not run them against a database whose records must be preserved.

Run the isolated SQLite-backed Phase 4 QR-attendance checks:

```powershell
python verify_phase4.py
```

The script covers QR token rotation and redaction, role and enrollment checks, valid and rejected attendance submissions, duplicate prevention, session monitoring, and attendance summaries without using the configured production database.

Run the isolated Phase 5 RAG, scope, history, recommendation, insight, and migration checks:

```powershell
python verify_phase5.py
```

Provider and vector-database calls in this verifier are mocked. For a live assistant, configure the services above, apply `alembic upgrade head`, upload an authorized text-based PDF, and query it through the authenticated API.

### RAG, assistant, and recommendations configuration

The assistant uses the configured embedding endpoint, Qdrant vector collection, and an OpenAI-compatible chat-completions endpoint. Set `EMBEDDING_API_URL` (and `EMBEDDING_MODEL`/`EMBEDDING_API_KEY` when required), `QDRANT_URL` (and `QDRANT_API_KEY` when required), and `LLM_API_URL`, `LLM_MODEL`, and optionally `LLM_API_KEY`. `LLM_API_URL` must be the full chat-completions endpoint. For Groq, configure `LLM_API_URL=https://api.groq.com/openai/v1/chat/completions`, choose a Groq-supported `LLM_MODEL`, and set `LLM_API_KEY` to a newly rotated key in the backend environment or deployment secret store. No provider, API key, or model is hardcoded; missing provider configuration returns an explicit HTTP 503. Keep all keys server-side and never set them in frontend environment variables.

Uploads accept valid, text-extractable PDFs only, enforce configured byte/page/chunk limits, and synchronously create embeddings in bounded batches. Retrieval filters active documents against the authenticated user's subject, department, class, academic year, and semester scope before reading source text. Answers include source citations; document-specific questions without relevant passages receive an explicit insufficient-information response. Documents are deleted from Qdrant and the relational store together, with best-effort vector restoration if the relational delete fails.

Numerical attendance, syllabus, assignment, assessment, and risk values in next-best actions and staff insights are computed by backend services. The language model explains provided evidence only; it is instructed not to calculate official values or treat uploaded document text as executable instructions.

### Production configuration

Set `APP_ENV=production`, a unique `JWT_SECRET_KEY` of at least 32 characters, and an explicit comma-separated `ALLOWED_ORIGINS` list. Production startup rejects a missing/weak JWT secret and wildcard CORS. Database health failures return a generic `503` response and log only the exception type; do not expose connection details to clients.

---

## Swagger / OpenAPI Documentation

Interactive API documentation is automatically generated by FastAPI:

- **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
