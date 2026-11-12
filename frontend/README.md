# Smart Curriculum Activity & Attendance App — Frontend

The frontend is the existing React 19 + Vite application. It uses the FastAPI endpoints under `/api`; it does not contain seeded dashboard statistics or a separate mock data layer.

## Run locally

Start the backend and database using the instructions in [`../backend/README.md`](../backend/README.md), then run:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

The Vite development server proxies `/api` to `http://127.0.0.1:8000`. The app uses same-origin `/api` requests by default, which also works behind the Docker Nginx proxy. For a separately hosted frontend, set `VITE_API_BASE_URL` to the backend API base URL, including `/api`, before building.

Production build and lint:

```powershell
npm run build
npm run lint
```

## Frontend integration

- Login uses `POST /api/auth/login`; persisted sessions are revalidated with `GET /api/auth/me`. Routes and sidebar links are role allow-listed, and 401 responses clear the session.
- QR attendance sessions keep the existing attendance models and routes. Each session has a cryptographically random, expiring QR token that rotates through the authenticated teacher refresh endpoint; student session lists do not expose tokens. Attendance submissions are checked against the live session, expiry, academic period, class/subject enrollment, and the per-session uniqueness constraint.
- The teacher monitor polls the session roster and attendance records while an active session is open. Student attendance percentages use backend records and the configured `REQUIRED_ATTENDANCE_PERCENTAGE`; QR token TTL and refresh intervals are configured by `ATTENDANCE_QR_TOKEN_TTL_SECONDS` and `ATTENDANCE_QR_REFRESH_INTERVAL_SECONDS`.
- Camera scanning uses the cross-browser ZXing QR decoder and sends decoded session tokens to the existing student attendance endpoint. Secure context and camera permission are required; token entry remains available as a fallback.
- No location data is collected. Rotating QR tokens reduce stale-code reuse but cannot prove physical presence or prevent a student from sharing a live QR code.
- Curriculum, assignments/submissions, assessment results, academic risks, activities, notifications, document upload/list/replace/delete, and the RAG assistant use the backend APIs documented in the backend README.
- The student assistant loads account-scoped chat history, supports clearing it, cites retrieved documents, and receives only the authenticated student's own database-calculated attendance, curriculum, assignment, and assessment context.
- Next-best actions are recalculated from actual academic records on each request. Teacher insights are restricted to assigned subjects/classes; admin insights aggregate current records and identify when the student sample is truncated.
- Document ingestion and assistant responses require server-side embedding, Qdrant, and OpenAI-compatible chat-completions configuration. The frontend never receives provider credentials. Upload processing is synchronous and reports `READY` after indexing succeeds.
- The frontend Docker image serves the SPA and reverse-proxies `/api/` to the Compose backend. Nginx allows 12 MB request bodies for the default 10 MB PDF upload limit and applies a longer upstream timeout for synchronous assistant requests.

## API-backed features not available yet

- The API does not expose a curriculum-topic list, so the UI can show syllabus aggregates and units and can create topics, but cannot render topic-level status or let students update topic progress.
- Assignment submissions accept written text only. There is no assignment attachment upload route.
- The backend has no global admin attendance aggregate/department analytics endpoint; the dashboard does not invent an overall attendance percentage or department chart.
- The API has no student-submitted attendance correction-request workflow or general profile update endpoint.
- Teacher roster search/complete student list and aggregate syllabus/assessment class charts require additional backend list/analytics endpoints. Assessment marks can be recorded by profile ID in the current API.
- AI assistant availability depends on backend RAG/provider and indexed-document configuration. The frontend displays backend errors and citations when returned; it does not fabricate answers.
- Document processing is synchronous; there is no background job queue or per-document progress endpoint.
- Live external-provider and physical document-ingestion tests require configured embeddings, Qdrant, an LLM endpoint, and an authorized PDF. `backend/verify_phase5.py` uses isolated SQLite data and mocked providers instead.

Backend authorization remains authoritative. Frontend route restrictions complement, but do not replace, server-side role and data-scope checks.
