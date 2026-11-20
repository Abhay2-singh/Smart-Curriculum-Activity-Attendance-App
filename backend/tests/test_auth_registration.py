from datetime import date
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password, verify_password
from app.main import app
from app.models.academic import (
    AcademicClass,
    AcademicYear,
    Batch,
    Department,
    Division,
    Semester,
)
from app.models.enums import UserRole
from app.models.profiles import Student, Teacher
from app.models.user import User


class RegistrationFlowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)

        def override_get_db():
            db = self.session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        with self.session_factory() as db:
            db.add(
                User(
                    username="test-admin",
                    email="test-admin@example.com",
                    password_hash=hash_password("AdminTestPass123"),
                    role=UserRole.ADMIN,
                    is_active=True,
                )
            )
            db.commit()
        admin_login = self.client.post(
            "/api/auth/login",
            json={"username": "test-admin", "password": "AdminTestPass123"},
        )
        self.admin_headers = {
            "Authorization": f"Bearer {admin_login.json()['access_token']}"
        }

    def tearDown(self):
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def test_student_registration_login_profile_and_role_guard(self):
        registration = {
            "full_name": "Abhay Singh",
            "email": "abhay@example.com",
            "enrollment_number": "ENR-1001",
            "password": "StudentPass123",
            "confirm_password": "StudentPass123",
        }
        registered = self.client.post("/api/auth/register/student", json=registration)
        self.assertEqual(registered.status_code, 201, registered.text)
        self.assertEqual(registered.json()["full_name"], "Abhay Singh")
        self.assertEqual(registered.json()["enrollment_number"], "ENR-1001")
        self.assertEqual(registered.json()["role"], "STUDENT")

        with self.session_factory() as db:
            user = db.query(User).filter(User.email == "abhay@example.com").one()
            self.assertNotEqual(user.password_hash, registration["password"])
            self.assertTrue(verify_password(registration["password"], user.password_hash))

        wrong_account_type = self.client.post(
            "/api/auth/login",
            json={
                "username": "abhay@example.com",
                "password": registration["password"],
                "role": "TEACHER",
            },
        )
        self.assertEqual(wrong_account_type.status_code, 401)

        login = self.client.post(
            "/api/auth/login",
            json={
                "username": "abhay@example.com",
                "password": registration["password"],
                "role": "STUDENT",
            },
        )
        self.assertEqual(login.status_code, 200, login.text)
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        profile = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(profile.status_code, 200, profile.text)
        self.assertEqual(profile.json()["full_name"], "Abhay Singh")
        self.assertEqual(profile.json()["enrollment_number"], "ENR-1001")
        self.assertEqual(self.client.get("/api/auth/test/student", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/test/teacher", headers=headers).status_code, 403)

    def test_teacher_registration_login_and_role_guard(self):
        registration = {
            "full_name": "Rahul Sharma",
            "email": "rahul@example.com",
            "password": "TeacherPass123",
            "confirm_password": "TeacherPass123",
        }
        registered = self.client.post("/api/auth/register/teacher", json=registration)
        self.assertEqual(registered.status_code, 201, registered.text)
        self.assertEqual(registered.json()["full_name"], "Rahul Sharma")
        self.assertEqual(registered.json()["role"], "TEACHER")

        login = self.client.post(
            "/api/auth/login",
            json={
                "username": registration["email"],
                "password": registration["password"],
                "role": "TEACHER",
            },
        )
        self.assertEqual(login.status_code, 200, login.text)
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        profile = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(profile.status_code, 200, profile.text)
        self.assertEqual(profile.json()["full_name"], "Rahul Sharma")
        self.assertEqual(self.client.get("/api/auth/test/teacher", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/test/student", headers=headers).status_code, 403)

    def test_duplicate_email_enrollment_and_password_confirmation_are_rejected(self):
        student = {
            "full_name": "First Student",
            "email": "same@example.com",
            "enrollment_number": "ENR-2001",
            "password": "StudentPass123",
            "confirm_password": "StudentPass123",
        }
        self.assertEqual(
            self.client.post("/api/auth/register/student", json=student).status_code,
            201,
        )

        duplicate_email = dict(student, enrollment_number="ENR-2002")
        self.assertEqual(
            self.client.post("/api/auth/register/student", json=duplicate_email).status_code,
            409,
        )

        duplicate_enrollment = dict(
            student,
            email="another@example.com",
        )
        self.assertEqual(
            self.client.post("/api/auth/register/student", json=duplicate_enrollment).status_code,
            409,
        )

        mismatch = dict(
            student,
            email="different@example.com",
            enrollment_number="ENR-2003",
            confirm_password="WrongPassword123",
        )
        self.assertEqual(
            self.client.post("/api/auth/register/student", json=mismatch).status_code,
            422,
        )

    def test_admin_can_link_registered_student_to_valid_academic_profile(self):
        registration = {
            "full_name": "Profile Link Student",
            "email": "profile-student@example.com",
            "enrollment_number": "ENR-LINK-1",
            "password": "StudentPass123",
            "confirm_password": "StudentPass123",
        }
        account = self.client.post("/api/auth/register/student", json=registration)
        self.assertEqual(account.status_code, 201, account.text)
        user_id = account.json()["id"]

        with self.session_factory() as db:
            department = Department(name="Link Test Department", code="LINK")
            year = AcademicYear(
                name="2098-2099",
                start_date=date(2098, 7, 1),
                end_date=date(2099, 6, 30),
            )
            db.add_all([department, year])
            db.flush()
            semester = Semester(
                academic_year_id=year.id,
                semester_number=1,
                name="Link Test Semester",
            )
            academic_class = AcademicClass(
                department_id=department.id,
                name="Link Test Class",
                code="LINK-1",
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
            db.add(batch)
            db.flush()
            profile_ids = {
                "department_id": department.id,
                "academic_class_id": academic_class.id,
                "division_id": division.id,
                "batch_id": batch.id,
                "academic_year_id": year.id,
                "semester_id": semester.id,
            }
            db.commit()

        linked = self.client.post(
            f"/api/users/{user_id}/student-profile",
            headers=self.admin_headers,
            json={
                "full_name": "Profile Link Student",
                "enrollment_number": "ENR-LINK-1",
                "roll_number": "LINK-001",
                **profile_ids,
            },
        )
        self.assertEqual(linked.status_code, 201, linked.text)
        self.assertEqual(linked.json()["student_profile"]["enrollment_number"], "ENR-LINK-1")

        student_login = self.client.post(
            "/api/auth/login",
            json={"username": registration["email"], "password": registration["password"]},
        )
        token = student_login.json()["access_token"]
        profile = self.client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(profile.status_code, 200, profile.text)
        self.assertIsNotNone(profile.json()["student_profile"])
        self.assertEqual(
            self.client.get(
                "/api/attendance/my-summary",
                headers={"Authorization": f"Bearer {token}"},
            ).status_code,
            200,
        )

    def test_admin_can_link_registered_teacher_to_valid_department(self):
        registration = {
            "full_name": "Profile Link Teacher",
            "email": "profile-teacher@example.com",
            "password": "TeacherPass123",
            "confirm_password": "TeacherPass123",
        }
        account = self.client.post("/api/auth/register/teacher", json=registration)
        self.assertEqual(account.status_code, 201, account.text)
        user_id = account.json()["id"]

        with self.session_factory() as db:
            department = Department(name="Teacher Link Department", code="TLINK")
            db.add(department)
            db.commit()
            department_id = department.id

        linked = self.client.post(
            f"/api/users/{user_id}/teacher-profile",
            headers=self.admin_headers,
            json={
                "full_name": "Profile Link Teacher",
                "employee_id": "EMP-LINK-1",
                "department_id": department_id,
            },
        )
        self.assertEqual(linked.status_code, 201, linked.text)
        self.assertEqual(linked.json()["teacher_profile"]["department_id"], department_id)

        teacher_login = self.client.post(
            "/api/auth/login",
            json={"username": registration["email"], "password": registration["password"]},
        )
        token = teacher_login.json()["access_token"]
        self.assertEqual(
            self.client.get(
                "/api/attendance-sessions",
                headers={"Authorization": f"Bearer {token}"},
            ).status_code,
            200,
        )


if __name__ == "__main__":
    unittest.main()
