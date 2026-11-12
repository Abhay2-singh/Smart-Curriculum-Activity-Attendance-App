from datetime import date, datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.config import settings
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
from app.models.enums import UserRole
from app.models.profiles import Student, Teacher
from app.models.subject import Subject
from app.models.user import User
from app.services.academic_gap_service import classify_risk


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


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
    dept = Department(name="Phase 2 Test", code="P2TEST")
    year = AcademicYear(
        name="2099-2100",
        start_date=date(2099, 7, 1),
        end_date=date(2100, 6, 30),
    )
    db.add_all([dept, year])
    db.flush()
    semester = Semester(
        academic_year_id=year.id, semester_number=1, name="Test Semester"
    )
    academic_class = AcademicClass(
        department_id=dept.id, name="Test Year", code="P2"
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
    subject = Subject(
        name="Phase 2 Subject",
        code="P2-101",
        department_id=dept.id,
        semester_id=semester.id,
    )
    db.add_all([batch, subject])
    db.flush()

    admin = User(
        username="phase2-admin",
        email="phase2-admin@example.test",
        password_hash=hash_password("phase2-test-password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    teacher_user = User(
        username="phase2-teacher",
        email="phase2-teacher@example.test",
        password_hash=hash_password("phase2-test-password"),
        role=UserRole.TEACHER,
        is_active=True,
    )
    student_user = User(
        username="phase2-student",
        email="phase2-student@example.test",
        password_hash=hash_password("phase2-test-password"),
        role=UserRole.STUDENT,
        is_active=True,
    )
    bypass_admin_user = User(
        username="admin",
        email="legacy-admin@example.test",
        password_hash=hash_password("phase2-test-password"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    bypass_teacher_user = User(
        username="teacher1",
        email="legacy-teacher@example.test",
        password_hash=hash_password("phase2-test-password"),
        role=UserRole.TEACHER,
        is_active=True,
    )
    bypass_student_user = User(
        username="student1",
        email="legacy-student@example.test",
        password_hash=hash_password("phase2-test-password"),
        role=UserRole.STUDENT,
        is_active=True,
    )
    db.add_all([
        admin,
        teacher_user,
        student_user,
        bypass_admin_user,
        bypass_teacher_user,
        bypass_student_user,
    ])
    db.flush()
    teacher = Teacher(
        user_id=teacher_user.id,
        employee_id="P2-EMP-1",
        full_name="Phase 2 Teacher",
        email=teacher_user.email,
        department_id=dept.id,
    )
    student = Student(
        user_id=student_user.id,
        student_id="P2-STU-1",
        roll_number="1",
        enrollment_number="P2-ENR-1",
        full_name="Phase 2 Student",
        email=student_user.email,
        department_id=dept.id,
        academic_class_id=academic_class.id,
        division_id=division.id,
        batch_id=batch.id,
        academic_year_id=year.id,
        semester_id=semester.id,
    )
    db.add_all([teacher, student])
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
        "department": dept.id,
        "year": year.id,
        "semester": semester.id,
        "class": academic_class.id,
        "division": division.id,
        "batch": batch.id,
        "subject": subject.id,
        "teacher": teacher.id,
        "student": student.id,
    }


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "phase2-test-password"},
    )
    require(response.status_code == 200, f"Login failed for {username}: {response.text}")
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


try:
    with TestClient(app) as client:
        admin_headers = login(client, "phase2-admin")
        teacher_headers = login(client, "phase2-teacher")
        student_headers = login(client, "phase2-student")
        for username, password in (
            ("admin", "AdminPass@123"),
            ("teacher1", "JSPM#Faculty2026!"),
            ("teacher1", "TeacherPass123!"),
            ("student1", "StudentPass123!"),
        ):
            require(
                client.post(
                    "/api/auth/login",
                    json={"username": username, "password": password},
                ).status_code
                == 401,
                f"Legacy hardcoded credential unexpectedly authenticated: {username}",
            )

        require(
            client.get(
                f"/api/curriculum/subjects/{ids['subject']}",
            ).status_code
            == 401,
            "Curriculum reads must require authentication",
        )
        require(
            client.post(
                "/api/curriculum/units",
                json={"subject_id": ids["subject"], "title": "Unauthenticated", "order_index": 1},
            ).status_code
            == 401,
            "Curriculum write must require authentication",
        )
        require(
            client.post(
                "/api/curriculum/units",
                headers=student_headers,
                json={"subject_id": ids["subject"], "title": "Student unit", "order_index": 1},
            ).status_code
            == 403,
            "Students must not create curriculum units",
        )

        subject_response = client.post(
            "/api/subjects",
            headers=admin_headers,
            json={
                "name": "Phase 2 API Subject",
                "code": "P2-API",
                "department_id": ids["department"],
                "semester_id": ids["semester"],
            },
        )
        require(subject_response.status_code == 201, f"Subject API failed: {subject_response.text}")
        require(
            client.get(
                f"/api/curriculum/subjects/{subject_response.json()['id']}/progress",
                headers=student_headers,
            ).status_code
            == 403,
            "Student must not access a subject outside their class curriculum",
        )

        unit_response = client.post(
            "/api/curriculum/units",
            headers=teacher_headers,
            json={
                "subject_id": ids["subject"],
                "title": "Unit 1",
                "order_index": 1,
                "expected_completion_date": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            },
        )
        require(unit_response.status_code == 201, f"Unit creation failed: {unit_response.text}")
        unit_id = unit_response.json()["id"]
        topic_response = client.post(
            f"/api/curriculum/units/{unit_id}/topics",
            headers=teacher_headers,
            json={
                "title": "Topic 1",
                "order_index": 1,
                "expected_completion_date": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            },
        )
        require(topic_response.status_code == 201, f"Topic creation failed: {topic_response.text}")
        topic_id = topic_response.json()["id"]
        progress_response = client.put(
            f"/api/curriculum/topics/{topic_id}/progress",
            headers=student_headers,
            json={"status": "COMPLETED"},
        )
        require(progress_response.status_code == 200, f"Progress update failed: {progress_response.text}")
        syllabus = client.get(
            f"/api/curriculum/subjects/{ids['subject']}/progress",
            headers=student_headers,
        )
        require(
            syllabus.status_code == 200
            and syllabus.json()["actual_progress_percentage"] == 100.0,
            f"Syllabus progress mismatch: {syllabus.text}",
        )

        assignment_response = client.post(
            "/api/assignments",
            headers=teacher_headers,
            json={
                "subject_id": ids["subject"],
                "division_id": ids["division"],
                "title": "Overdue assignment",
                "due_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                "max_marks": "20",
            },
        )
        require(assignment_response.status_code == 201, f"Assignment creation failed: {assignment_response.text}")
        assignment_id = assignment_response.json()["id"]
        overdue = client.get(
            "/api/assignments?state=overdue", headers=student_headers
        )
        require(
            overdue.status_code == 200 and len(overdue.json()) == 1,
            f"Overdue assignment tracking failed: {overdue.text}",
        )
        submission_response = client.post(
            f"/api/assignments/{assignment_id}/submissions",
            headers=student_headers,
            json={"content": "My submission"},
        )
        require(submission_response.status_code == 201, f"Submission failed: {submission_response.text}")
        require(
            len(client.get("/api/assignments?state=pending", headers=student_headers).json()) == 0,
            "Submitted assignment was still reported as pending",
        )
        submission_id = submission_response.json()["id"]
        require(
            client.patch(
                f"/api/submissions/{submission_id}/evaluate",
                headers=teacher_headers,
                json={"score": "21", "feedback": "Too high"},
            ).status_code
            == 422,
            "Submission evaluation must enforce the assignment maximum",
        )
        evaluated = client.patch(
            f"/api/submissions/{submission_id}/evaluate",
            headers=teacher_headers,
            json={"score": "18", "feedback": "Good work"},
        )
        require(evaluated.status_code == 200, f"Submission evaluation failed: {evaluated.text}")
        require(
            client.delete(
                f"/api/assignments/{assignment_id}", headers=student_headers
            ).status_code
            == 403,
            "Student must not delete an assignment",
        )
        assignment_update = client.put(
            f"/api/assignments/{assignment_id}",
            headers=teacher_headers,
            json={"title": "Updated overdue assignment"},
        )
        require(
            assignment_update.status_code == 200
            and assignment_update.json()["title"] == "Updated overdue assignment",
            f"Assignment update failed: {assignment_update.text}",
        )

        assessment_response = client.post(
            "/api/assessments",
            headers=teacher_headers,
            json={
                "subject_id": ids["subject"],
                "division_id": ids["division"],
                "title": "Unit test",
                "assessment_type": "TEST",
                "scheduled_at": datetime.now(timezone.utc).isoformat(),
                "max_marks": "100",
            },
        )
        require(assessment_response.status_code == 201, f"Assessment creation failed: {assessment_response.text}")
        assessment_id = assessment_response.json()["id"]
        result_response = client.post(
            f"/api/assessments/{assessment_id}/results",
            headers=teacher_headers,
            json={"student_id": ids["student"], "marks": "80"},
        )
        require(result_response.status_code == 200, f"Result recording failed: {result_response.text}")
        updated_result = client.put(
            f"/api/assessments/{assessment_id}/results/{ids['student']}",
            headers=teacher_headers,
            json={"marks": "90", "feedback": "Updated"},
        )
        require(updated_result.status_code == 200 and updated_result.json()["marks"] == "90.00",
                f"Assessment result update failed: {updated_result.text}")
        performance = client.get(
            "/api/assessments/performance", headers=student_headers
        )
        require(
            performance.status_code == 200
            and performance.json()["subject_performance"][0]["average_percentage"] == 90.0,
            f"Student performance calculation failed: {performance.text}",
        )
        averages = client.get(
            "/api/assessments/subject-averages", headers=teacher_headers
        )
        require(
            averages.status_code == 200
            and averages.json()["subject_averages"][0]["average_percentage"] == 90.0,
            f"Class averages failed: {averages.text}",
        )

        activity_response = client.post(
            "/api/activities",
            headers=teacher_headers,
            json={
                "title": "Academic workshop",
                "activity_type": "ACADEMIC",
                "activity_date": datetime.now(timezone.utc).isoformat(),
                "subject_id": ids["subject"],
            },
        )
        require(activity_response.status_code == 201, f"Activity creation failed: {activity_response.text}")
        activity_id = activity_response.json()["id"]
        participation = client.post(
            f"/api/activities/{activity_id}/participation",
            headers=teacher_headers,
            json={"student_id": ids["student"], "participated": True, "points": 5},
        )
        require(participation.status_code == 200, f"Activity participation failed: {participation.text}")
        require(
            client.get("/api/activities/history", headers=student_headers).status_code == 200,
            "Student activity history endpoint failed",
        )
        activity_stats = client.get(
            "/api/activities/statistics", headers=student_headers
        )
        require(
            activity_stats.status_code == 200
            and activity_stats.json()["statistics"][0]["participation_count"] == 1,
            f"Activity statistics failed: {activity_stats.text}",
        )
        require(
            client.post(
                f"/api/activities/{activity_id}/participation",
                headers=student_headers,
                json={"student_id": ids["student"], "participated": True},
            ).status_code
            == 403,
            "Student must not self-certify activity participation",
        )

        now = datetime.now(timezone.utc)
        session_payload = {
            "academic_year_id": ids["year"],
            "semester_id": ids["semester"],
            "division_id": ids["division"],
            "batch_id": ids["batch"],
            "subject_id": ids["subject"],
            "teacher_id": ids["teacher"],
            "session_date": date.today().isoformat(),
            "start_time": "09:00:00",
            "end_time": "10:00:00",
            "expires_at": (now + timedelta(minutes=10)).isoformat(),
        }
        session_response = client.post(
            "/api/attendance-sessions", headers=teacher_headers, json=session_payload
        )
        require(session_response.status_code == 201, f"QR session creation failed: {session_response.text}")
        session_data = session_response.json()
        require(session_data["session_token"], "Session token was empty")
        unassigned_subject_session = client.post(
            "/api/attendance-sessions",
            headers=teacher_headers,
            json={**session_payload, "subject_id": subject_response.json()["id"]},
        )
        require(
            unassigned_subject_session.status_code == 403,
            "Teacher created a session for an unassigned subject",
        )
        require(
            client.get(
                f"/api/attendance-sessions/{session_data['id']}",
                headers=student_headers,
            ).status_code
            == 200,
            "Student could not access a session in their division",
        )
        require(
            client.get(
                "/api/attendance-sessions?division_id=999999",
                headers=student_headers,
            ).status_code
            == 403,
            "Student accessed attendance sessions outside their division",
        )
        mark = client.post(
            "/api/attendance/mark",
            headers=student_headers,
            json={"session_token": session_data["session_token"]},
        )
        require(mark.status_code == 201, f"QR attendance mark failed: {mark.text}")
        require(mark.json()["marked_at"], "Attendance timestamp missing")
        duplicate = client.post(
            "/api/attendance/mark",
            headers=student_headers,
            json={"session_token": session_data["session_token"]},
        )
        require(duplicate.status_code == 409, "Duplicate QR attendance was not rejected")
        close = client.patch(
            f"/api/attendance-sessions/{session_data['id']}/close",
            headers=teacher_headers,
        )
        require(close.status_code == 200, f"Session close failed: {close.text}")
        attendance_summary = client.get(
            f"/api/attendance/students/{ids['student']}/summary",
            headers=teacher_headers,
        )
        require(
            attendance_summary.status_code == 200
            and attendance_summary.json()["attended_sessions"] == 1,
            f"Teacher attendance summary failed: {attendance_summary.text}",
        )
        defaulters = client.get(
            f"/api/reports/defaulters?division_id={ids['division']}",
            headers=teacher_headers,
        )
        require(defaulters.status_code == 200, f"Scoped defaulter report failed: {defaulters.text}")

        expired_session = client.post(
            "/api/attendance-sessions", headers=teacher_headers, json=session_payload
        )
        require(expired_session.status_code == 201, f"Second QR session failed: {expired_session.text}")
        with TestSession() as db:
            from app.models.attendance import AttendanceSession

            row = db.get(AttendanceSession, expired_session.json()["id"])
            row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            db.commit()
        expired_mark = client.post(
            "/api/attendance/mark",
            headers=student_headers,
            json={"session_token": expired_session.json()["session_token"]},
        )
        require(expired_mark.status_code == 400, "Expired QR attendance was not rejected")

        gaps = client.get(
            f"/api/analytics/gaps?student_id={ids['student']}&subject_id={ids['subject']}",
            headers=teacher_headers,
        )
        require(gaps.status_code == 200 and gaps.json()["attendance_gap"] > 0,
                f"Academic gap calculation failed: {gaps.text}")
        low_risk, _ = classify_risk({
            "attendance_gap": 0.0,
            "curriculum_gap": 0.0,
            "pending_assignments": 0,
            "performance_percentage": 90.0,
        })
        medium_risk, _ = classify_risk({
            "attendance_gap": 7.0,
            "curriculum_gap": 0.0,
            "pending_assignments": 0,
            "performance_percentage": 90.0,
        })
        require(
            low_risk == "LOW" and medium_risk == "MEDIUM",
            "Low/medium risk thresholds were classified incorrectly",
        )
        risk = client.post(
            f"/api/analytics/analyze?student_id={ids['student']}&subject_id={ids['subject']}",
            headers=teacher_headers,
        )
        require(
            risk.status_code == 200 and risk.json()["risk_level"] == "HIGH",
            f"Risk classification failed: {risk.text}",
        )
        require(
            len(client.get("/api/analytics/risks", headers=student_headers).json()) >= 1,
            "Student risk report was not persisted",
        )
        for path, label in (
            (f"/api/analytics/risks?student_id={ids['student']}", "risk report"),
            (f"/api/analytics/gap-history?student_id={ids['student']}", "gap history"),
            (f"/api/alerts?student_id={ids['student']}", "academic alerts"),
            (f"/api/recommendations?student_id={ids['student']}", "recommendations"),
        ):
            response = client.get(path, headers=teacher_headers)
            require(response.status_code == 200, f"Teacher {label} scope failed: {response.text}")
        require(
            len(client.get("/api/alerts", headers=student_headers).json()) >= 1,
            "Academic alert was not persisted",
        )
        require(
            len(client.get("/api/recommendations", headers=student_headers).json()) >= 1,
            "Risk recommendation was not created",
        )
        require(
            len(client.get("/api/notifications", headers=student_headers).json()) >= 1,
            "Academic risk notification was not created",
        )
        manual_session = client.post(
            "/api/attendance-sessions",
            headers=teacher_headers,
            json={
                **session_payload,
                "session_date": (date.today() + timedelta(days=1)).isoformat(),
            },
        )
        require(manual_session.status_code == 201, f"Manual session setup failed: {manual_session.text}")
        manual_url = f"/api/attendance/sessions/{manual_session.json()['id']}/manual-mark"
        duplicate_manual = client.post(
            manual_url,
            headers=teacher_headers,
            json={
                "records": [
                    {"student_id": ids["student"], "status": "PRESENT"},
                    {"student_id": ids["student"], "status": "ABSENT"},
                ]
            },
        )
        require(duplicate_manual.status_code == 422, "Duplicate students in a batch were accepted")
        manual_mark = client.post(
            manual_url,
            headers=teacher_headers,
            json={
                "records": [{"student_id": ids["student"], "status": "PRESENT"}]
            },
        )
        require(manual_mark.status_code == 200, f"Manual attendance failed: {manual_mark.text}")

        bad_pdf = client.post(
            "/api/documents",
            headers=teacher_headers,
            files={"file": ("notes.pdf", b"not a pdf", "application/pdf")},
            data={"subject_id": str(ids["subject"])},
        )
        require(bad_pdf.status_code == 415, "Non-PDF content was accepted")
        assistant = client.post(
            "/api/assistant/query",
            headers=student_headers,
            json={"question": "Explain the subject syllabus", "subject_id": ids["subject"]},
        )
        require(
            assistant.status_code == 503,
            "RAG should explicitly report an unconfigured embedding provider",
        )

        print("Phase 2 API verification passed: models, auth, curriculum, assignments,")
        print("assessments, activities, QR attendance, gaps, risk, alerts and RAG guards.")
finally:
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
