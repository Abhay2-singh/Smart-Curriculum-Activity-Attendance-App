"""Verify dynamic QR attendance APIs against an isolated SQLite database."""

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.academic import (
    AcademicClass,
    AcademicYear,
    Batch,
    Department,
    Division,
    Semester,
)
from app.models.assignments import ClassSubjectAssignment, TeacherAssignment
from app.models.attendance import AttendanceSession
from app.models.enums import UserRole
from app.models.profiles import Student, Teacher
from app.models.subject import Subject
from app.models.user import User

engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(engine)


def test_db():
    with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = test_db
settings.EMBEDDING_API_URL = ""

with TestSession() as db:
    department = Department(name="QR Test Department", code="QRTEST")
    year = AcademicYear(
        name="QR Test Year",
        start_date=date.today() - timedelta(days=1),
        end_date=date.today() + timedelta(days=300),
    )
    db.add_all([department, year])
    db.flush()
    semester = Semester(
        academic_year_id=year.id, semester_number=1, name="QR Test Semester"
    )
    academic_class = AcademicClass(
        department_id=department.id, name="QR Test Class", code="QRT"
    )
    db.add_all([semester, academic_class])
    db.flush()
    division = Division(
        academic_class_id=academic_class.id,
        academic_year_id=year.id,
        semester_id=semester.id,
        name="A",
    )
    db.add(division)
    db.flush()
    batch = Batch(division_id=division.id, name="B1")
    other_batch = Batch(division_id=division.id, name="B2")
    subject = Subject(
        name="QR Test Subject",
        code="QR-101",
        department_id=department.id,
        semester_id=semester.id,
    )
    unassigned_subject = Subject(
        name="Unassigned QR Subject",
        code="QR-102",
        department_id=department.id,
        semester_id=semester.id,
    )
    db.add_all([batch, other_batch, subject, unassigned_subject])
    db.flush()

    password = hash_password("qr-test-password")
    teacher_user = User(
        username="qr-teacher",
        email="qr-teacher@example.test",
        password_hash=password,
        role=UserRole.TEACHER,
    )
    student_user = User(
        username="qr-student",
        email="qr-student@example.test",
        password_hash=password,
        role=UserRole.STUDENT,
    )
    other_student_user = User(
        username="qr-other-student",
        email="qr-other-student@example.test",
        password_hash=password,
        role=UserRole.STUDENT,
    )
    admin_user = User(
        username="qr-admin",
        email="qr-admin@example.test",
        password_hash=password,
        role=UserRole.ADMIN,
    )
    db.add_all([teacher_user, student_user, other_student_user, admin_user])
    db.flush()

    teacher = Teacher(
        user_id=teacher_user.id,
        employee_id="QR-EMP-1",
        full_name="QR Teacher",
        email=teacher_user.email,
        department_id=department.id,
    )
    student = Student(
        user_id=student_user.id,
        student_id="QR-STU-1",
        roll_number="1",
        enrollment_number="QR-ENR-1",
        full_name="QR Student",
        email=student_user.email,
        department_id=department.id,
        academic_class_id=academic_class.id,
        division_id=division.id,
        batch_id=batch.id,
        academic_year_id=year.id,
        semester_id=semester.id,
    )
    other_student = Student(
        user_id=other_student_user.id,
        student_id="QR-STU-2",
        roll_number="2",
        enrollment_number="QR-ENR-2",
        full_name="Other QR Student",
        email=other_student_user.email,
        department_id=department.id,
        academic_class_id=academic_class.id,
        division_id=division.id,
        batch_id=other_batch.id,
        academic_year_id=year.id,
        semester_id=semester.id,
    )
    db.add_all([teacher, student, other_student])
    db.flush()
    db.add_all(
        [
            ClassSubjectAssignment(
                academic_class_id=academic_class.id,
                division_id=division.id,
                subject_id=subject.id,
                academic_year_id=year.id,
                semester_id=semester.id,
            ),
            TeacherAssignment(
                teacher_id=teacher.id,
                subject_id=subject.id,
                academic_class_id=academic_class.id,
                division_id=division.id,
                batch_id=None,
                academic_year_id=year.id,
                semester_id=semester.id,
            ),
        ]
    )
    db.commit()
    ids = {
        "year": year.id,
        "semester": semester.id,
        "division": division.id,
        "batch": batch.id,
        "subject": subject.id,
        "unassigned_subject": unassigned_subject.id,
        "teacher": teacher.id,
        "student": student.id,
    }


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "qr-test-password"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_session(client: TestClient, headers: dict[str, str], subject_id: int) -> dict:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    response = client.post(
        "/api/attendance-sessions",
        headers=headers,
        json={
            "academic_year_id": ids["year"],
            "semester_id": ids["semester"],
            "division_id": ids["division"],
            "batch_id": ids["batch"],
            "subject_id": subject_id,
            "teacher_id": ids["teacher"],
            "session_date": date.today().isoformat(),
            "start_time": now.time().isoformat(),
            "end_time": (now + timedelta(minutes=20)).time().isoformat(),
            "expires_at": (now + timedelta(minutes=20)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def expect_status(expected: int, response) -> None:
    assert response.status_code == expected, (
        f"expected {expected}, received {response.status_code}: {response.text}"
    )


try:
    with TestClient(app) as client:
        teacher_headers = login(client, "qr-teacher")
        student_headers = login(client, "qr-student")
        other_student_headers = login(client, "qr-other-student")
        admin_headers = login(client, "qr-admin")

        session = create_session(client, teacher_headers, ids["subject"])
        token = session["session_token"]
        assert len(token) >= 40
        assert session["qr_token_expires_at"]
        assert session["qr_token_ttl_seconds"] > session["qr_refresh_interval_seconds"]

        student_sessions = client.get(
            "/api/attendance-sessions?status=ACTIVE", headers=student_headers
        )
        expect_status(200, student_sessions)
        assert student_sessions.json()[0]["session_token"] is None

        expect_status(
            403,
            client.post(
                f"/api/attendance-sessions/{session['id']}/refresh-token",
                headers=student_headers,
            ),
        )
        expect_status(
            429,
            client.post(
                f"/api/attendance-sessions/{session['id']}/refresh-token",
                headers=teacher_headers,
            ),
        )

        marked = client.post(
            "/api/attendance/mark",
            headers=student_headers,
            json={"session_token": token},
        )
        expect_status(201, marked)
        expect_status(
            409,
            client.post(
                "/api/attendance/mark",
                headers=student_headers,
                json={"session_token": token},
            ),
        )
        expect_status(
            403,
            client.post(
                "/api/attendance/mark",
                headers=other_student_headers,
                json={"session_token": token},
            ),
        )
        monitor = client.get(
            f"/api/attendance-sessions/{session['id']}/monitor",
            headers=teacher_headers,
        )
        expect_status(200, monitor)
        assert monitor.json()["present_count"] == 1
        assert monitor.json()["total_enrolled"] == 1

        with TestSession() as db:
            row = db.get(AttendanceSession, session["id"])
            row.qr_token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        rotated = client.post(
            f"/api/attendance-sessions/{session['id']}/refresh-token",
            headers=teacher_headers,
        )
        expect_status(200, rotated)
        assert rotated.json()["session_token"] != token
        expect_status(
            404,
            client.post(
                "/api/attendance/mark",
                headers=student_headers,
                json={"session_token": token},
            ),
        )

        summary = client.get("/api/attendance/my-summary", headers=student_headers)
        expect_status(200, summary)
        assert summary.json()["total_sessions"] == 1
        assert summary.json()["attended_sessions"] == 1
        assert summary.json()["overall_percentage"] == 100
        assert "required_attendance_percentage" in summary.json()

        closed = client.patch(
            f"/api/attendance-sessions/{session['id']}/close",
            headers=teacher_headers,
        )
        expect_status(200, closed)
        expect_status(
            400,
            client.post(
                "/api/attendance/mark",
                headers=student_headers,
                json={"session_token": rotated.json()["session_token"]},
            ),
        )

        expired_session = create_session(client, teacher_headers, ids["subject"])
        with TestSession() as db:
            row = db.get(AttendanceSession, expired_session["id"])
            row.qr_token_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        expired_mark = client.post(
            "/api/attendance/mark",
            headers=student_headers,
            json={"session_token": expired_session["session_token"]},
        )
        expect_status(400, expired_mark)
        assert "QR code has expired" in expired_mark.json()["detail"]
        client.patch(
            f"/api/attendance-sessions/{expired_session['id']}/close",
            headers=teacher_headers,
        )

        unassigned = create_session(
            client, admin_headers, ids["unassigned_subject"]
        )
        expect_status(
            403,
            client.post(
                "/api/attendance/mark",
                headers=student_headers,
                json={"session_token": unassigned["session_token"]},
            ),
        )
        expect_status(
            404,
            client.post(
                "/api/attendance/mark",
                headers=student_headers,
                json={"session_token": "not-a-valid-token"},
            ),
        )

    print(
        "PASS: token generation/redaction, role access, refresh cooldown and rotation, "
        "valid/duplicate/unauthorized/expired/closed/invalid marks, live roster monitor, "
        "subject enrollment, and attendance summary"
    )
finally:
    app.dependency_overrides.pop(get_db, None)
    engine.dispose()
