# 🎓 ATTENDANCE MANAGEMENT SYSTEM — FINAL ACADEMIC PROJECT SUBMISSION GUIDE

**Institution:** Shri Vaishnav Vidyapeeth Vishwavidyalaya
**Project Title:** Full-Stack QR-Based Attendance Management System with Role-Based Access Control & Defaulter Analytics  
**Tech Stack:** FastAPI (Python 3.13), MySQL 8.0, React 19 (Vite), Glassmorphism Design System  

---

## 🔑 1. Demo Accounts

| Role | Username | Password | Access Rights |
| :--- | :--- | :--- | :--- |
| **ADMIN / HOD** | Configure during setup | Set in your local environment | Full access to users, academic structure, timetable, audit logs & reports. |
| **TEACHER** | Create through Admin | Set during account creation | Class timetable, attendance sessions, live monitor, manual marking & audit corrections. |
| **STUDENT** | Create through Admin | Set during account creation | Scan QR / enter session token, then view personal attendance and academic progress. |

No shared demo passwords are published. Create or configure a local admin account using `INIT_ADMIN_PASSWORD`; create teacher/student accounts from the Admin portal.

---

## 🚀 2. How to Launch & Run for Live Presentation

### Step A: Start Backend API (FastAPI)
Open PowerShell Terminal 1:
```powershell
cd backend
.\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
```
- **Backend API**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Step B: Start Frontend App (React Vite)
Open PowerShell Terminal 2:
```powershell
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```
- **Web App Interface**: [http://127.0.0.1:5173](http://127.0.0.1:5173)

---

## 🎬 3. Live 5-Minute Presentation Script (Viva Demonstration)

Create a teacher and student account through User Management, assign the teacher to a class/subject, then follow this sequence:

### Step 1: Demonstrate Admin Portal (`admin` / password configured in `backend/.env`)
1. Log in as **Admin**.
2. Show **Dashboard Overview** metrics (Active Sessions, Total Students, Defaulter Alerts).
3. In **Academic Structure → Add your academic data**, add an academic year, semester, department, class, division, batch, and subject.
4. In **User Management**, create teacher and student accounts. Add a class-subject mapping and either a teacher assignment or timetable entry before starting attendance.
5. Open **Academic Structure** to review departments, classes, subjects, faculty, and student profiles.

### Step 2: Demonstrate Teacher QR Session Creation
1. Log out of Admin and sign in with the teacher account created by the administrator.
2. Go to **My Timetable** or **My Assigned Classes** and click **"Start Attendance Session"**.
3. Point out the **1-Click Quick Fill from Timetable** chips and **Batch selector**.
4. Click **"Launch Session & Display QR"**.
5. Show the live **QR Code**, rotating session token, and countdown expiration timer.

### Step 3: Demonstrate Student Self-Marking & Duplicate Rule
1. Open a new Incognito browser window or sign in with the student account created by the administrator.
2. Go to **Mark Attendance**.
3. Use **"Scan QR with camera"** to scan the teacher's active QR (HTTPS or localhost and camera permission are required), or enter the token manually.
4. Show the instant success message: **`Status: PRESENT`**.
5. **Duplicate Anti-Cheat Rule Test:** Click **"Mark Attendance Now"** again with the same token to demonstrate the system blocking duplicate submissions (`HTTP 409 Conflict`).

### Step 4: Demonstrate Teacher Live Monitor & Manual Audit Correction
1. Switch back to the **Teacher** browser window.
2. Open **Live Session Monitor / Records**.
3. Show the live student attendance entry.
4. Click **"Audit Override / Correct Record"**, change a status (e.g. `ABSENT` -> `EXCUSED`), and type a reason (*"Medical certificate submitted"*).
5. Open **Corrections & Audit** to show the permanent, tamper-proof audit log.

### Step 5: Demonstrate Subject Breakdown & Defaulter Analytics
1. Switch to **Student Portal**: Open **Subject Attendance** to show percentage progress bars and required class counters (*"Attend next N classes for 75%"*).
2. Switch to **Teacher/Admin Portal**: Open **Class Defaulter Reports** and set threshold slider to `75%` to view automatic defaulter lists.

---

## 🧪 4. Automated Verification Suite (Proof of Correctness)

Run the isolated, SQLite-backed verification suites from the repository root:

```powershell
python backend\verify_all_modules.py
```
This suite runs core academic/access-control, dynamic QR attendance, and Phase 5 RAG/recommendation checks without using the configured MySQL database or live AI providers. The legacy `verify_module_1*.py` scripts target a live database and some create and clean up records matching test prefixes; do not run them against data you need to preserve.

---

## 🏛️ 5. Key System Architecture & Database

1. `users` — Role-based accounts (`ADMIN`, `TEACHER`, `STUDENT`) with Bcrypt password hashes.
2. `departments` — Department definitions (COMP, IT, AIDS, ENTC, MECH, CIVIL).
3. `academic_years` & `semesters` — Term duration mappings.
4. `academic_classes`, `divisions`, `batches` — Hierarchy structure (FE, SE, TE, BE).
5. `teachers` & `students` — Profiles linked to users.
6. `subjects`, `class_subject_assignments`, `teacher_assignments` — Curriculum mapping.
7. `timetable` — Weekly schedule slots.
8. `attendance_sessions` — Dynamic QR token sessions with expiration timestamps.
9. `attendance_records` — Present/Absent entries with duplicate prevention index.
10. `attendance_corrections` — Status override audit trail.
11. Academic progress, assignments/submissions, assessments/results, activities, gap snapshots, risk records, recommendations, alerts, notifications, documents/chunks, and user-scoped assistant history.

The base application schema contains 16 tables; additive academic and assistant migrations add their tables and QR token expiry field. See [`backend/README.md`](./backend/README.md) for migration and backup instructions.

---

**Prepared for Academic Evaluation at Shri Vaishnav Vidyapeeth Vishwavidyalaya.**

---

## 🌱 6. Environment Setup & Initialization

To set up your local development environment, follow these initialization steps:

### Step 1: Clone the Repository
```bash
git clone https://github.com/yourusername/attendance-management-system.git
cd attendance-management-system
```

### Step 2: Configure Backend API
1. Navigate to the `backend` directory from the project root.
2. Copy the example environment file:
   ```bash
   Copy-Item .env.example .env
   ```
3. Update `.env` with your MySQL credentials, unique `JWT_SECRET_KEY`, and `INIT_ADMIN_PASSWORD`.
4. Create the `attendance_management` database in MySQL if it does not exist.

### Step 3: Install Python Dependencies
```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### Step 4: Initialize the Database
```bash
.\.venv\Scripts\python.exe -m app.init_db
.\.venv\Scripts\python.exe -m alembic upgrade head
```
For an existing database, take a backup and run `alembic upgrade head`; don't use `app.init_db` as a migration substitute. Do not run `seed_indian_college_data.py` when preparing a clean database; it inserts fictional demo records.

### Step 5: Run the Application
- Follow the instructions in **🚀 2. How to Launch & Run for Live Presentation** to start the backend API and frontend app.

---

## 🔄 7. Common Troubleshooting Tips

- **Backend API not starting?**
  - Ensure your virtual environment is activated.
  - Check for port conflicts on `127.0.0.1:8000`.

- **Frontend not loading?**
  - Ensure the backend API is running.
  - Check browser console for CORS or network errors.

- **Database connection issues?**
  - Double-check your MySQL credentials in the `.env` file.
  - Ensure the MySQL service is running.
- **AI academic assistant says it is not configured?**
  - The optional assistant needs a compatible LLM endpoint, API key, and model in `.env`; attendance does not depend on these settings.
- **Student camera scanner cannot open?**
  - Allow camera permission and use HTTPS or localhost. A student can still enter the current session token manually.
- **Docker says `DB_PASSWORD` or `JWT_SECRET_KEY` is missing?**
  - Copy the root `.env.example` to `.env`, replace both values with unique secrets, then restart Compose. Keep the existing DB password when reusing an existing volume; never run `docker compose down -v` to troubleshoot.

---

## 📚 8. References & Acknowledgements

- **FastAPI Documentation**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **React Documentation**: [reactjs.org](https://reactjs.org)
- **MySQL Documentation**: [dev.mysql.com/doc](https://dev.mysql.com/doc)
- **Glassmorphism CSS CodePen**: [codepen.io](https://codepen.io/tag/glassmorphism)

---

**This project is developed for Shri Vaishnav Vidyapeeth Vishwavidyalaya.**
