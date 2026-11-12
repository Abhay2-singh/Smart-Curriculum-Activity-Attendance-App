"""Verify Phase 5 APIs with isolated SQLite data and mocked providers."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy import inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.academic import AcademicClass, AcademicYear, Department, Semester
from app.models.assignments import ClassSubjectAssignment, TeacherAssignment
from app.models.enums import UserRole
from app.models.learning import (
    AcademicDocumentChunk,
    Assessment,
    AssessmentResult,
    Assignment,
    CurriculumTopic,
    CurriculumUnit,
)
from app.models.profiles import Student, Teacher
from app.models.subject import Subject
from app.models.user import User
import app.services.rag_service as rag_service

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
settings.LLM_API_URL = "https://configured-provider.invalid/v1/chat/completions"
settings.LLM_MODEL = "phase5-test-model"
settings.LLM_API_KEY = "local-test-only"
settings.RAG_MIN_SIMILARITY_SCORE = 0.25
vector_points = {}
provider_requests = []
query_score = 0.95


def fake_embedding(texts):
    return [[0.1, 0.2, 0.3] for _ in texts]


def fake_qdrant(method, path, payload=None):
    if method == "GET" and "/collections/" in path:
        return SimpleNamespace(status_code=200, json=lambda: {})
    if method == "PUT" and "/points?wait=true" in path:
        for point in payload["points"]:
            vector_points[point["id"]] = point
        return SimpleNamespace(status_code=200, json=lambda: {})
    if method == "POST" and "/points/delete" in path:
        for point_id in payload["points"]:
            vector_points.pop(point_id, None)
        return SimpleNamespace(status_code=200, json=lambda: {})
    if method == "POST" and "/points/query" in path:
        allowed = set(payload["filter"]["must"][0]["match"]["any"])
        matches = [
            {
                "id": point_id,
                "score": query_score,
                "payload": point["payload"],
            }
            for point_id, point in vector_points.items()
            if point["payload"]["document_id"] in allowed
        ]
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"result": {"points": matches[: payload["limit"]]}},
        )
    raise AssertionError(f"Unexpected vector request: {method} {path}")


def fake_llm_post(url, json, headers, timeout):
    provider_requests.append(json)
    return SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {
            "choices": [
                {"message": {"content": "The cited academic source explains this. [1]"}}
            ]
        },
    )


real_generate_embeddings = rag_service.generate_embeddings
rag_service.generate_embeddings = fake_embedding
rag_service._qdrant_request = fake_qdrant
rag_service._ensure_collection = lambda vector_size: None
rag_service.httpx.post = fake_llm_post


def pdf_with_text(text: str) -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(stream)).encode()
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for object_id, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode())
        output.extend(body + b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(output)


with TestSession() as db:
    department = Department(name="Phase 5 Department", code="P5DEPT")
    other_department = Department(name="Other Phase 5 Department", code="P5OTHER")
    year = AcademicYear(
        name="Phase 5 Year",
        start_date=date.today() - timedelta(days=100),
        end_date=date.today() + timedelta(days=200),
    )
    other_year = AcademicYear(
        name="Other Phase 5 Year",
        start_date=date.today() - timedelta(days=100),
        end_date=date.today() + timedelta(days=200),
    )
    db.add_all([department, other_department, year, other_year])
    db.flush()
    semester = Semester(academic_year_id=year.id, semester_number=1, name="P5-S1")
    other_semester = Semester(
        academic_year_id=other_year.id, semester_number=1, name="P5-Other-S1"
    )
    academic_class = AcademicClass(
        department_id=department.id, name="Phase 5 Class", code="P5"
    )
    other_class = AcademicClass(
        department_id=other_department.id, name="Other Class", code="P5O"
    )
    db.add_all([semester, other_semester, academic_class, other_class])
    db.flush()
    subject = Subject(
        name="Phase 5 Subject",
        code="P5-101",
        department_id=department.id,
        semester_id=semester.id,
    )
    other_subject = Subject(
        name="Other Subject",
        code="P5-201",
        department_id=other_department.id,
        semester_id=other_semester.id,
    )
    db.add_all([subject, other_subject])
    db.flush()
    teacher_user = User(
        username="p5-teacher",
        email="p5-teacher@example.test",
        password_hash=hash_password("phase5-test-password"),
        role=UserRole.TEACHER,
    )
    student_user = User(
        username="p5-student",
        email="p5-student@example.test",
        password_hash=hash_password("phase5-test-password"),
        role=UserRole.STUDENT,
    )
    other_student_user = User(
        username="p5-student-other",
        email="p5-student-other@example.test",
        password_hash=hash_password("phase5-test-password"),
        role=UserRole.STUDENT,
    )
    admin_user = User(
        username="p5-admin",
        email="p5-admin@example.test",
        password_hash=hash_password("phase5-test-password"),
        role=UserRole.ADMIN,
    )
    db.add_all([teacher_user, student_user, other_student_user, admin_user])
    db.flush()
    teacher = Teacher(
        user_id=teacher_user.id,
        employee_id="P5-EMP",
        full_name="Phase 5 Teacher",
        email=teacher_user.email,
        department_id=department.id,
    )
    student = Student(
        user_id=student_user.id,
        student_id="P5-STU-1",
        roll_number="1",
        enrollment_number="P5-ENR-1",
        full_name="Phase 5 Student",
        email=student_user.email,
        department_id=department.id,
        academic_class_id=academic_class.id,
        division_id=1,
        batch_id=1,
        academic_year_id=year.id,
        semester_id=semester.id,
    )
    other_student = Student(
        user_id=other_student_user.id,
        student_id="P5-STU-2",
        roll_number="2",
        enrollment_number="P5-ENR-2",
        full_name="Other Student",
        email=other_student_user.email,
        department_id=other_department.id,
        academic_class_id=other_class.id,
        division_id=2,
        batch_id=2,
        academic_year_id=other_year.id,
        semester_id=other_semester.id,
    )
    # Create valid academic groups using the existing relationships.
    from app.models.academic import Batch, Division

    division = Division(
        id=1,
        academic_class_id=academic_class.id,
        academic_year_id=year.id,
        semester_id=semester.id,
        name="A",
    )
    other_division = Division(
        id=2,
        academic_class_id=other_class.id,
        academic_year_id=other_year.id,
        semester_id=other_semester.id,
        name="A",
    )
    db.add_all([division, other_division])
    db.flush()
    batch = Batch(id=1, division_id=division.id, name="B1")
    other_batch = Batch(id=2, division_id=other_division.id, name="B1")
    db.add_all([batch, other_batch])
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
                academic_year_id=year.id,
                semester_id=semester.id,
            ),
        ]
    )
    unit = CurriculumUnit(
        subject_id=subject.id,
        title="Unit 1",
        order_index=1,
        expected_completion_date=datetime.now(timezone.utc) - timedelta(days=1),
        created_by=admin_user.id,
    )
    db.add(unit)
    db.flush()
    db.add(
        CurriculumTopic(
            unit_id=unit.id,
            title="Topic 1",
            order_index=1,
            expected_completion_date=datetime.now(timezone.utc) - timedelta(days=1),
        )
    )
    assignment = Assignment(
        subject_id=subject.id,
        teacher_id=teacher.id,
        division_id=division.id,
        title="Overdue Phase 5 Assignment",
        due_at=datetime.now(timezone.utc) - timedelta(days=1),
        max_marks=Decimal("100"),
    )
    assessment = Assessment(
        subject_id=subject.id,
        teacher_id=teacher.id,
        division_id=division.id,
        title="Phase 5 Assessment",
        assessment_type="TEST",
        scheduled_at=datetime.now(timezone.utc) - timedelta(days=2),
        max_marks=Decimal("100"),
    )
    db.add_all([assignment, assessment])
    db.flush()
    db.add(
        AssessmentResult(
            assessment_id=assessment.id,
            student_id=student.id,
            marks=Decimal("30"),
            recorded_by=teacher_user.id,
        )
    )
    db.commit()
    ids = {
        "department": department.id,
        "other_department": other_department.id,
        "class": academic_class.id,
        "year": year.id,
        "semester": semester.id,
        "subject": subject.id,
        "other_subject": other_subject.id,
        "student": student.id,
        "other_student": other_student.id,
    }


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "phase5-test-password"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def upload(client, headers, text, **metadata):
    data = {key: str(value) for key, value in metadata.items() if value is not None}
    return client.post(
        "/api/documents",
        headers=headers,
        data=data,
        files={"file": ("source.pdf", pdf_with_text(text), "application/pdf")},
    )


with TestClient(app) as client:
    admin_headers = login(client, "p5-admin")
    teacher_headers = login(client, "p5-teacher")
    student_headers = login(client, "p5-student")
    other_student_headers = login(client, "p5-student-other")

    invalid_pdf = client.post(
        "/api/documents",
        headers=admin_headers,
        data={"subject_id": ids["subject"]},
        files={"file": ("bad.pdf", b"not a pdf", "application/pdf")},
    )
    assert invalid_pdf.status_code == 415, invalid_pdf.text

    admin_upload = upload(
        client,
        admin_headers,
        "The attendance policy requires students to attend scheduled classes.",
        subject_id=ids["subject"],
    )
    assert admin_upload.status_code == 201, admin_upload.text
    admin_document = admin_upload.json()
    assert admin_document["processing_status"] == "READY"
    assert admin_document["department_id"] == ids["department"]
    assert admin_document["academic_year_id"] == ids["year"]
    assert admin_document["semester_id"] == ids["semester"]

    teacher_upload = upload(
        client,
        teacher_headers,
        "The syllabus includes network protocols and routing fundamentals.",
        subject_id=ids["subject"],
        academic_class_id=ids["class"],
    )
    assert teacher_upload.status_code == 201, teacher_upload.text
    teacher_document_id = teacher_upload.json()["id"]
    replaced_document = client.post(
        f"/api/documents/{teacher_document_id}/replace",
        headers=teacher_headers,
        files={
            "file": (
                "replacement.pdf",
                pdf_with_text("The updated course syllabus includes routing."),
                "application/pdf",
            )
        },
    )
    assert replaced_document.status_code == 200, replaced_document.text
    replaced_document_id = replaced_document.json()["id"]
    assert replaced_document_id != teacher_document_id
    assert teacher_document_id not in {
        point["payload"]["document_id"] for point in vector_points.values()
    }
    teacher_document_id = replaced_document_id

    unauthorized_upload = upload(
        client,
        teacher_headers,
        "Unauthorized content",
        subject_id=ids["other_subject"],
    )
    assert unauthorized_upload.status_code == 403, unauthorized_upload.text

    other_department_document = upload(
        client,
        admin_headers,
        "Other department regulations.",
        department_id=ids["other_department"],
    )
    assert other_department_document.status_code == 201, other_department_document.text

    student_documents = client.get(
        f"/api/documents?subject_id={ids['subject']}", headers=student_headers
    )
    assert student_documents.status_code == 200, student_documents.text
    visible_ids = {item["id"] for item in student_documents.json()}
    assert admin_document["id"] in visible_ids
    assert teacher_document_id in visible_ids
    assert other_department_document.json()["id"] not in visible_ids

    assistant_answer = client.post(
        "/api/assistant/query",
        headers=student_headers,
        json={
            "question": "What does my academic source say about attendance?",
            "subject_id": ids["subject"],
        },
    )
    assert assistant_answer.status_code == 200, assistant_answer.text
    answer_data = assistant_answer.json()
    assert answer_data["citations"]
    assert "attendance_percentage" in answer_data["academic_context"]
    assert provider_requests
    prompt = provider_requests[-1]["messages"][1]["content"]
    assert "attendance_percentage" in prompt
    assert "next_best_actions" in prompt
    assert "attendance policy requires" in prompt

    original_llm_url = settings.LLM_API_URL
    settings.LLM_API_URL = ""
    unavailable_llm = client.post(
        "/api/assistant/query",
        headers=student_headers,
        json={"question": "Explain the source document.", "subject_id": ids["subject"]},
    )
    assert unavailable_llm.status_code == 503, unavailable_llm.text
    settings.LLM_API_URL = original_llm_url

    rag_service.httpx.post = lambda *args, **kwargs: (_ for _ in ()).throw(
        rag_service.httpx.TimeoutException("test timeout")
    )
    failed_llm = client.post(
        "/api/assistant/query",
        headers=student_headers,
        json={"question": "Explain the source document.", "subject_id": ids["subject"]},
    )
    assert failed_llm.status_code == 502, failed_llm.text
    rag_service.httpx.post = fake_llm_post

    forbidden_subject_query = client.post(
        "/api/assistant/query",
        headers=student_headers,
        json={"question": "What is in this subject?", "subject_id": ids["other_subject"]},
    )
    assert forbidden_subject_query.status_code == 403, forbidden_subject_query.text

    no_evidence_before = len(provider_requests)
    query_score = 0.1
    unsupported_answer = client.post(
        "/api/assistant/query",
        headers=admin_headers,
        json={
            "question": "Explain the unsupported academic policy.",
            "subject_id": ids["other_subject"],
        },
    )
    assert unsupported_answer.status_code == 200, unsupported_answer.text
    assert "do not contain sufficient information" in unsupported_answer.json()["answer"]
    assert not unsupported_answer.json()["citations"]
    assert len(provider_requests) == no_evidence_before
    query_score = 0.95

    own_history = client.get("/api/assistant/history", headers=student_headers)
    other_history = client.get("/api/assistant/history", headers=other_student_headers)
    assert [message["role"] for message in own_history.json()] == ["user", "assistant"]
    assert other_history.json() == []
    assert client.get("/api/assistant/history?limit=201", headers=student_headers).status_code == 422

    recommendations = client.get(
        f"/api/recommendations/next-best-action?student_id={ids['other_student']}",
        headers=student_headers,
    )
    assert recommendations.status_code == 200, recommendations.text
    actions = recommendations.json()
    assert {item["indicator"] for item in actions} >= {
        "curriculum_gap_percentage_points",
        "pending_assignments",
        "assessment_average_percentage",
    }
    assert not any(item["indicator"] == "attendance_gap_percentage_points" for item in actions)

    teacher_insights = client.get(
        f"/api/analytics/insights?subject_id={ids['subject']}",
        headers=teacher_headers,
    )
    assert teacher_insights.status_code == 200, teacher_insights.text
    assert teacher_insights.json()["students_analyzed"] == 1
    assert client.get("/api/analytics/insights", headers=student_headers).status_code == 403
    assert client.get(
        f"/api/recommendations/next-best-action?student_id={ids['student']}",
        headers=teacher_headers,
    ).status_code == 200
    assert client.get(
        f"/api/recommendations/next-best-action?student_id={ids['other_student']}",
        headers=teacher_headers,
    ).status_code == 403

    assert client.delete(
        f"/api/documents/{admin_document['id']}", headers=student_headers
    ).status_code == 403
    teacher_delete = client.delete(
        f"/api/documents/{teacher_document_id}", headers=teacher_headers
    )
    assert teacher_delete.status_code == 204, teacher_delete.text
    assert not any(
        point["payload"]["document_id"] == teacher_document_id
        for point in vector_points.values()
    )

    clear_history = client.delete("/api/assistant/history", headers=student_headers)
    assert clear_history.status_code == 204, clear_history.text
    assert client.get("/api/assistant/history", headers=student_headers).json() == []
    assert client.get("/api/assistant/history", headers=other_student_headers).json() == []
    assert len(own_history.json()) == 2

app.dependency_overrides.pop(get_db, None)
Base.metadata.drop_all(engine)
engine.dispose()

original_embedding_url = settings.EMBEDDING_API_URL
settings.EMBEDDING_API_URL = ""
try:
    real_generate_embeddings(["provider configuration check"])
except HTTPException as error:
    assert error.status_code == 503
else:
    raise AssertionError("Missing embedding configuration did not fail explicitly")
settings.EMBEDDING_API_URL = original_embedding_url

migration_engine = create_engine("sqlite+pysqlite://")
excluded_tables = {
    "academic_documents",
    "academic_document_chunks",
    "academic_assistant_messages",
}
Base.metadata.create_all(
    migration_engine,
    tables=[
        table
        for table in Base.metadata.sorted_tables
        if table.name not in excluded_tables
    ],
)
with migration_engine.begin() as connection:
    connection.execute(
        text(
            "CREATE TABLE academic_documents ("
            "id INTEGER PRIMARY KEY, subject_id INTEGER, uploaded_by INTEGER NOT NULL, "
            "filename VARCHAR(255) NOT NULL, content_type VARCHAR(100) NOT NULL, "
            "sha256 VARCHAR(64) NOT NULL UNIQUE, is_active BOOLEAN NOT NULL DEFAULT 1, "
            "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
        )
    )
    department = Department(name="Migration Department", code="MIGRATE")
    migration_session = TestSession(bind=connection)
    migration_session.add(department)
    migration_session.flush()
    migration_year = AcademicYear(
        name="Migration Year",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=365),
    )
    migration_session.add(migration_year)
    migration_session.flush()
    migration_semester = Semester(
        academic_year_id=migration_year.id,
        semester_number=1,
        name="Migration Semester",
    )
    migration_subject = Subject(
        name="Migration Subject",
        code="MIG-101",
        department_id=department.id,
        semester=migration_semester,
    )
    migration_user = User(
        username="migration-admin",
        email="migration-admin@example.test",
        password_hash="not-a-real-password-hash",
        role=UserRole.ADMIN,
    )
    migration_session.add_all([migration_semester, migration_subject, migration_user])
    migration_session.flush()
    migration_ids = {
        "department": department.id,
        "year": migration_year.id,
        "semester": migration_semester.id,
    }
    connection.execute(
        text(
            "INSERT INTO academic_documents "
            "(id, subject_id, uploaded_by, filename, content_type, sha256, is_active, "
            "created_at, updated_at) VALUES "
            "(:id, :subject_id, :uploaded_by, :filename, :content_type, :sha256, "
            "1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {
            "id": 1,
            "subject_id": migration_subject.id,
            "uploaded_by": migration_user.id,
            "filename": "legacy.pdf",
            "content_type": "application/pdf",
            "sha256": "a" * 64,
        },
    )
    migration_session.flush()
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from migrations.versions.phase5_academic_assistant import upgrade

    with Operations.context(MigrationContext.configure(connection)):
        upgrade()
    migration_session.commit()
    migration_session.close()
columns = {column["name"] for column in inspect(migration_engine).get_columns("academic_documents")}
with migration_engine.connect() as connection:
    migrated_document = connection.execute(
        text(
            "SELECT department_id, academic_year_id, semester_id "
            "FROM academic_documents WHERE id = 1"
        )
    ).one()
assert {"department_id", "academic_class_id", "academic_year_id", "semester_id"} <= columns
assert migrated_document.department_id == migration_ids["department"]
assert migrated_document.academic_year_id == migration_ids["year"]
assert migrated_document.semester_id == migration_ids["semester"]
assert "academic_assistant_messages" in inspect(migration_engine).get_table_names()
migration_engine.dispose()
print("Phase 5 document, RAG, access-control, history, insight, and recommendation checks passed.")
