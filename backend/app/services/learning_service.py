from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.academic import Division
from app.models.assignments import ClassSubjectAssignment, TeacherAssignment
from app.models.learning import (
    ActivityParticipation,
    Assessment,
    AssessmentResult,
    Assignment,
    AssignmentSubmission,
    CurriculumTopic,
    CurriculumUnit,
    Notification,
    StudentActivity,
    StudentTopicProgress,
)
from app.models.profiles import Student, Teacher
from app.models.subject import Subject
from app.models.timetable import Timetable
from app.models.user import User
from app.models.enums import UserRole
from app.schemas.learning import (
    ActivityParticipationCreate,
    AssessmentCreate,
    AssessmentMarksUpdate,
    AssessmentResultCreate,
    AssignmentCreate,
    AssignmentUpdate,
    CurriculumProgressUpdate,
    CurriculumTopicCreate,
    CurriculumUnitCreate,
    StudentActivityCreate,
)


def _http_error(code: int, message: str) -> HTTPException:
    return HTTPException(status_code=code, detail=message)


def _get_or_404(db: Session, model, item_id: int, label: str):
    item = db.get(model, item_id)
    if item is None:
        raise _http_error(status.HTTP_404_NOT_FOUND, f"{label} not found")
    return item


def _student_profile(user: User) -> Student:
    if not user.student_profile:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Student profile is required")
    return user.student_profile


def _teacher_profile(user: User) -> Teacher:
    if not user.teacher_profile:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Teacher profile is required")
    return user.teacher_profile


def _require_teaching_scope(
    db: Session, user: User, subject_id: int, division_id: Optional[int] = None
) -> Teacher:
    teacher = _teacher_profile(user)
    if division_id is not None:
        if not _teacher_can_access_division(db, user, subject_id, division_id):
            raise _http_error(
                status.HTTP_403_FORBIDDEN,
                "Teacher is not assigned to this subject and division",
            )
        return teacher
    query = select(TeacherAssignment).where(
        TeacherAssignment.teacher_id == teacher.id,
        TeacherAssignment.subject_id == subject_id,
        TeacherAssignment.is_active.is_(True),
    )
    if not db.execute(query.limit(1)).first():
        raise _http_error(
            status.HTTP_403_FORBIDDEN,
            "Teacher is not assigned to this subject and division",
        )
    return teacher


def _can_access_subject(db: Session, user: User, subject_id: int) -> None:
    if user.role == UserRole.STUDENT:
        student = _student_profile(user)
        assigned = db.execute(
            select(ClassSubjectAssignment.id).where(
                ClassSubjectAssignment.subject_id == subject_id,
                ClassSubjectAssignment.academic_class_id == student.academic_class_id,
                ClassSubjectAssignment.academic_year_id == student.academic_year_id,
                ClassSubjectAssignment.semester_id == student.semester_id,
                or_(
                    ClassSubjectAssignment.division_id.is_(None),
                    ClassSubjectAssignment.division_id == student.division_id,
                ),
                (
                    ClassSubjectAssignment.division_id.is_(None)
                    | (ClassSubjectAssignment.division_id == student.division_id)
                ),
                ClassSubjectAssignment.is_active.is_(True),
            ).limit(1)
        ).first()
        if not assigned:
            assigned = db.execute(
                select(TeacherAssignment.id).where(
                    TeacherAssignment.subject_id == subject_id,
                    TeacherAssignment.academic_class_id == student.academic_class_id,
                    TeacherAssignment.academic_year_id == student.academic_year_id,
                    TeacherAssignment.semester_id == student.semester_id,
                    TeacherAssignment.is_active.is_(True),
                    or_(
                        TeacherAssignment.division_id.is_(None),
                        TeacherAssignment.division_id == student.division_id,
                    ),
                    or_(
                        TeacherAssignment.batch_id.is_(None),
                        TeacherAssignment.batch_id == student.batch_id,
                    ),
                ).limit(1)
            ).first()
        if not assigned:
            assigned = db.execute(
                select(Timetable.id).where(
                    Timetable.subject_id == subject_id,
                    Timetable.academic_year_id == student.academic_year_id,
                    Timetable.semester_id == student.semester_id,
                    Timetable.division_id == student.division_id,
                    Timetable.is_active.is_(True),
                    or_(
                        Timetable.batch_id.is_(None),
                        Timetable.batch_id == student.batch_id,
                    ),
                ).limit(1)
            ).first()
        if not assigned:
            raise _http_error(status.HTTP_403_FORBIDDEN, "Subject is not available to this student")
    elif user.role == UserRole.TEACHER:
        _require_teaching_scope(db, user, subject_id)


def _validate_subject_division(
    db: Session, subject_id: int, division_id: Optional[int]
) -> None:
    if division_id is None:
        return
    division = _get_or_404(db, Division, division_id, "Division")
    linked = db.execute(
        select(ClassSubjectAssignment.id).where(
            ClassSubjectAssignment.subject_id == subject_id,
            ClassSubjectAssignment.academic_class_id == division.academic_class_id,
            ClassSubjectAssignment.academic_year_id == division.academic_year_id,
            ClassSubjectAssignment.semester_id == division.semester_id,
            or_(
                ClassSubjectAssignment.division_id.is_(None),
                ClassSubjectAssignment.division_id == division.id,
            ),
            ClassSubjectAssignment.is_active.is_(True),
        ).limit(1)
    ).first()
    if not linked:
        raise _http_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Subject is not assigned to the selected division",
        )


def create_curriculum_unit(
    db: Session, user: User, data: CurriculumUnitCreate
) -> CurriculumUnit:
    if not db.get(Subject, data.subject_id):
        raise _http_error(status.HTTP_404_NOT_FOUND, "Subject not found")
    if user.role == UserRole.TEACHER:
        _require_teaching_scope(db, user, data.subject_id)
    unit = CurriculumUnit(**data.model_dump(), created_by=user.id)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


def list_curriculum_units(db: Session, user: User, subject_id: int) -> list[CurriculumUnit]:
    _can_access_subject(db, user, subject_id)
    return list(
        db.execute(
            select(CurriculumUnit)
            .options(joinedload(CurriculumUnit.topics))
            .where(CurriculumUnit.subject_id == subject_id)
            .order_by(CurriculumUnit.order_index)
        ).unique().scalars()
    )


def create_curriculum_topic(
    db: Session, user: User, unit_id: int, data: CurriculumTopicCreate
) -> CurriculumTopic:
    unit = _get_or_404(db, CurriculumUnit, unit_id, "Curriculum unit")
    if user.role == UserRole.TEACHER:
        _require_teaching_scope(db, user, unit.subject_id)
    topic = CurriculumTopic(unit_id=unit_id, **data.model_dump())
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return topic


def update_topic_progress(
    db: Session,
    user: User,
    topic_id: int,
    data: CurriculumProgressUpdate,
    student_id: Optional[int] = None,
) -> StudentTopicProgress:
    topic = _get_or_404(db, CurriculumTopic, topic_id, "Curriculum topic")
    unit = _get_or_404(db, CurriculumUnit, topic.unit_id, "Curriculum unit")
    if user.role == UserRole.STUDENT:
        student = _student_profile(user)
        _can_access_subject(db, user, unit.subject_id)
    else:
        if user.role == UserRole.TEACHER:
            _require_teaching_scope(db, user, unit.subject_id)
        if student_id is None:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "student_id is required")
        student = _get_or_404(db, Student, student_id, "Student")
        if user.role == UserRole.TEACHER and not _teacher_can_access_division(
            db, user, unit.subject_id, student.division_id, student.batch_id
        ):
            raise _http_error(status.HTTP_403_FORBIDDEN, "Student is outside teacher assignment")

    progress = db.execute(
        select(StudentTopicProgress).where(
            StudentTopicProgress.student_id == student.id,
            StudentTopicProgress.topic_id == topic.id,
        )
    ).scalar_one_or_none()
    if progress is None:
        progress = StudentTopicProgress(
            student_id=student.id,
            topic_id=topic.id,
            updated_by=user.id,
            status=data.status,
        )
        db.add(progress)
    else:
        progress.status = data.status
        progress.updated_by = user.id
    progress.completed_at = (
        datetime.now(timezone.utc) if data.status == "COMPLETED" else None
    )
    db.commit()
    db.refresh(progress)
    return progress


def _teacher_can_access_division(
    db: Session,
    user: User,
    subject_id: int,
    division_id: int,
    batch_id: Optional[int] = None,
) -> bool:
    teacher = _teacher_profile(user)
    division = db.get(Division, division_id)
    if division is None:
        return False
    batch_scope = (
        or_(
            TeacherAssignment.batch_id.is_(None),
            TeacherAssignment.batch_id == batch_id,
        )
        if batch_id is not None
        else TeacherAssignment.batch_id.is_(None)
    )
    return db.execute(
        select(TeacherAssignment.id).where(
            TeacherAssignment.teacher_id == teacher.id,
            TeacherAssignment.subject_id == subject_id,
            TeacherAssignment.is_active.is_(True),
            TeacherAssignment.academic_class_id == division.academic_class_id,
            TeacherAssignment.academic_year_id == division.academic_year_id,
            TeacherAssignment.semester_id == division.semester_id,
            (TeacherAssignment.division_id.is_(None))
            | (TeacherAssignment.division_id == division_id),
            batch_scope,
        ).limit(1)
    ).first() is not None


def _teacher_student_assignment_scope(
    teacher_id: int,
    student: Student | type[Student],
    subject_id: Optional[int] = None,
):
    conditions = [
        TeacherAssignment.teacher_id == teacher_id,
        TeacherAssignment.is_active.is_(True),
        TeacherAssignment.academic_class_id == student.academic_class_id,
        TeacherAssignment.academic_year_id == student.academic_year_id,
        TeacherAssignment.semester_id == student.semester_id,
        or_(
            TeacherAssignment.division_id.is_(None),
            TeacherAssignment.division_id == student.division_id,
        ),
        or_(
            TeacherAssignment.batch_id.is_(None),
            TeacherAssignment.batch_id == student.batch_id,
        ),
    ]
    if subject_id is not None:
        conditions.append(TeacherAssignment.subject_id == subject_id)
    return and_(*conditions)


def get_syllabus_progress(db: Session, user: User, subject_id: int, student_id: Optional[int] = None) -> dict:
    _can_access_subject(db, user, subject_id)
    if user.role == UserRole.STUDENT:
        student = _student_profile(user)
    else:
        if user.role == UserRole.TEACHER:
            _require_teaching_scope(db, user, subject_id)
        if student_id is None:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "student_id is required")
        student = _get_or_404(db, Student, student_id, "Student")
        if user.role == UserRole.TEACHER and not _teacher_can_access_division(
            db, user, subject_id, student.division_id, student.batch_id
        ):
            raise _http_error(status.HTTP_403_FORBIDDEN, "Student is outside teacher assignment")

    subject = _get_or_404(db, Subject, subject_id, "Subject")
    topic_rows = db.execute(
        select(CurriculumTopic, CurriculumUnit.expected_completion_date)
        .join(CurriculumUnit)
        .where(CurriculumUnit.subject_id == subject_id)
    ).all()
    topics = [row[0] for row in topic_rows]
    now = datetime.now(timezone.utc)
    expected_count = sum(
        1
        for topic, unit_due_at in topic_rows
        if (topic.expected_completion_date or unit_due_at) is not None
        and _as_utc(topic.expected_completion_date or unit_due_at) <= now
    )
    completed_ids = set(
        db.execute(
            select(StudentTopicProgress.topic_id).where(
                StudentTopicProgress.student_id == student.id,
                StudentTopicProgress.status == "COMPLETED",
                StudentTopicProgress.topic_id.in_([topic.id for topic in topics] or [-1]),
            )
        ).scalars()
    )
    total = len(topics)
    actual = round(len(completed_ids) * 100 / total, 2) if total else 0.0
    expected = round(expected_count * 100 / total, 2) if total else 0.0
    return {
        "subject_id": subject_id,
        "subject_name": subject.name,
        "total_topics": total,
        "completed_topics": len(completed_ids),
        "expected_progress_percentage": expected,
        "actual_progress_percentage": actual,
        "curriculum_gap_percentage": round(max(0.0, expected - actual), 2),
    }


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def create_assignment(db: Session, user: User, data: AssignmentCreate) -> Assignment:
    teacher = _teacher_profile(user) if user.role == UserRole.TEACHER else None
    teacher_id = teacher.id if teacher else data.teacher_id
    if teacher_id is None:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "teacher_id is required")
    if not db.get(Subject, data.subject_id):
        raise _http_error(status.HTTP_404_NOT_FOUND, "Subject not found")
    if not db.get(Teacher, teacher_id):
        raise _http_error(status.HTTP_404_NOT_FOUND, "Teacher not found")
    if data.division_id is not None and not db.get(Division, data.division_id):
        raise _http_error(status.HTTP_404_NOT_FOUND, "Division not found")
    _validate_subject_division(db, data.subject_id, data.division_id)
    _require_teaching_scope_for_id(db, user, teacher_id, data.subject_id, data.division_id)
    assignment = Assignment(**data.model_dump(exclude={"teacher_id"}), teacher_id=teacher_id)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def _require_teaching_scope_for_id(
    db: Session,
    user: User,
    teacher_id: int,
    subject_id: int,
    division_id: Optional[int],
) -> None:
    if user.role == UserRole.ADMIN:
        return
    teacher = _teacher_profile(user)
    if division_id is None:
        allowed = db.execute(
            select(TeacherAssignment.id).where(
                TeacherAssignment.teacher_id == teacher.id,
                TeacherAssignment.subject_id == subject_id,
                TeacherAssignment.is_active.is_(True),
                TeacherAssignment.division_id.is_(None),
                TeacherAssignment.batch_id.is_(None),
            ).limit(1)
        ).first() is not None
    else:
        allowed = _teacher_can_access_division(db, user, subject_id, division_id)
    if teacher.id != teacher_id or not allowed:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Teacher is not assigned to this subject")


def list_assignments(
    db: Session, user: User, state: Optional[str] = None, subject_id: Optional[int] = None
) -> list[Assignment]:
    query = select(Assignment).where(Assignment.is_active.is_(True))
    if subject_id is not None:
        query = query.where(Assignment.subject_id == subject_id)
    if user.role == UserRole.STUDENT:
        student = _student_profile(user)
        query = query.where(
            Assignment.subject_id.in_(
                select(ClassSubjectAssignment.subject_id).where(
                    ClassSubjectAssignment.academic_class_id == student.academic_class_id,
                    ClassSubjectAssignment.academic_year_id == student.academic_year_id,
                    ClassSubjectAssignment.semester_id == student.semester_id,
                    or_(
                        ClassSubjectAssignment.division_id.is_(None),
                        ClassSubjectAssignment.division_id == student.division_id,
                    ),
                    ClassSubjectAssignment.is_active.is_(True),
                )
            ),
            or_(Assignment.division_id.is_(None), Assignment.division_id == student.division_id),
        )
        if state in ("pending", "overdue"):
            query = query.where(
                ~select(AssignmentSubmission.id)
                .where(
                    AssignmentSubmission.assignment_id == Assignment.id,
                    AssignmentSubmission.student_id == student.id,
                )
                .exists()
            )
            if state == "overdue":
                query = query.where(Assignment.due_at < datetime.now(timezone.utc))
        elif state not in (None, "all"):
            raise _http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unsupported assignment state")
    elif user.role == UserRole.TEACHER:
        teacher = _teacher_profile(user)
        query = query.where(Assignment.teacher_id == teacher.id)
    return list(db.execute(query.order_by(Assignment.due_at)).scalars())


def update_assignment(
    db: Session, user: User, assignment_id: int, data: AssignmentUpdate
) -> Assignment:
    assignment = _get_or_404(db, Assignment, assignment_id, "Assignment")
    if user.role == UserRole.TEACHER and assignment.teacher_id != _teacher_profile(user).id:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Cannot update another teacher's assignment")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(assignment, key, value)
    db.commit()
    db.refresh(assignment)
    return assignment


def deactivate_assignment(db: Session, user: User, assignment_id: int) -> None:
    assignment = _get_or_404(db, Assignment, assignment_id, "Assignment")
    if user.role == UserRole.TEACHER and assignment.teacher_id != _teacher_profile(user).id:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Cannot delete another teacher's assignment")
    assignment.is_active = False
    db.commit()


def submit_assignment(
    db: Session, user: User, assignment_id: int, content: str
) -> AssignmentSubmission:
    student = _student_profile(user)
    assignment = _get_or_404(db, Assignment, assignment_id, "Assignment")
    if not assignment.is_active:
        raise _http_error(status.HTTP_409_CONFLICT, "Assignment is no longer active")
    _can_access_subject(db, user, assignment.subject_id)
    if assignment.division_id is not None and assignment.division_id != student.division_id:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Assignment is not available to this student")
    existing = db.execute(
        select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment_id,
            AssignmentSubmission.student_id == student.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.content = content
        existing.submitted_at = datetime.now(timezone.utc)
        existing.score = None
        existing.feedback = None
        existing.evaluated_by = None
        existing.evaluated_at = None
        submission = existing
    else:
        submission = AssignmentSubmission(
            assignment_id=assignment_id, student_id=student.id, content=content
        )
        db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def list_submissions(db: Session, user: User, assignment_id: int) -> list[AssignmentSubmission]:
    assignment = _get_or_404(db, Assignment, assignment_id, "Assignment")
    if user.role == UserRole.TEACHER and assignment.teacher_id != _teacher_profile(user).id:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Cannot view another teacher's submissions")
    query = select(AssignmentSubmission).where(
        AssignmentSubmission.assignment_id == assignment_id
    )
    if user.role == UserRole.STUDENT:
        query = query.where(AssignmentSubmission.student_id == _student_profile(user).id)
    return list(db.execute(query.order_by(AssignmentSubmission.submitted_at)).scalars())


def evaluate_submission(
    db: Session, user: User, submission_id: int, score: Decimal, feedback: Optional[str]
) -> AssignmentSubmission:
    submission = _get_or_404(db, AssignmentSubmission, submission_id, "Submission")
    assignment = submission.assignment
    if user.role == UserRole.TEACHER and assignment.teacher_id != _teacher_profile(user).id:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Cannot evaluate another teacher's submission")
    if score > assignment.max_marks:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Score exceeds assignment maximum")
    submission.score = score
    submission.feedback = feedback
    submission.evaluated_by = user.id
    submission.evaluated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(submission)
    return submission


def create_assessment(db: Session, user: User, data: AssessmentCreate) -> Assessment:
    teacher = _teacher_profile(user) if user.role == UserRole.TEACHER else None
    teacher_id = teacher.id if teacher else data.teacher_id
    if teacher_id is None:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "teacher_id is required")
    if not db.get(Subject, data.subject_id) or not db.get(Teacher, teacher_id):
        raise _http_error(status.HTTP_404_NOT_FOUND, "Subject or teacher not found")
    if data.division_id is not None and not db.get(Division, data.division_id):
        raise _http_error(status.HTTP_404_NOT_FOUND, "Division not found")
    _validate_subject_division(db, data.subject_id, data.division_id)
    _require_teaching_scope_for_id(db, user, teacher_id, data.subject_id, data.division_id)
    assessment = Assessment(**data.model_dump(exclude={"teacher_id"}), teacher_id=teacher_id)
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


def list_assessments(
    db: Session, user: User, subject_id: Optional[int] = None
) -> list[Assessment]:
    query = select(Assessment).where(Assessment.is_active.is_(True))
    if subject_id is not None:
        query = query.where(Assessment.subject_id == subject_id)
    if user.role == UserRole.STUDENT:
        student = _student_profile(user)
        query = query.where(
            Assessment.subject_id.in_(
                select(ClassSubjectAssignment.subject_id).where(
                    ClassSubjectAssignment.academic_class_id == student.academic_class_id,
                    ClassSubjectAssignment.academic_year_id == student.academic_year_id,
                    ClassSubjectAssignment.semester_id == student.semester_id,
                    or_(
                        ClassSubjectAssignment.division_id.is_(None),
                        ClassSubjectAssignment.division_id == student.division_id,
                    ),
                    ClassSubjectAssignment.is_active.is_(True),
                )
            ),
            or_(Assessment.division_id.is_(None), Assessment.division_id == student.division_id),
        )
    elif user.role == UserRole.TEACHER:
        query = query.where(Assessment.teacher_id == _teacher_profile(user).id)
    return list(db.execute(query.order_by(Assessment.scheduled_at)).scalars())


def record_assessment_result(
    db: Session, user: User, assessment_id: int, data: AssessmentResultCreate
) -> AssessmentResult:
    assessment = _get_or_404(db, Assessment, assessment_id, "Assessment")
    if user.role == UserRole.TEACHER and assessment.teacher_id != _teacher_profile(user).id:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Cannot grade another teacher's assessment")
    student = _get_or_404(db, Student, data.student_id, "Student")
    if assessment.division_id is not None and assessment.division_id != student.division_id:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Student is outside this assessment division")
    enrolled = db.execute(
        select(ClassSubjectAssignment.id).where(
            ClassSubjectAssignment.subject_id == assessment.subject_id,
            ClassSubjectAssignment.academic_class_id == student.academic_class_id,
            ClassSubjectAssignment.academic_year_id == student.academic_year_id,
            ClassSubjectAssignment.semester_id == student.semester_id,
            or_(
                ClassSubjectAssignment.division_id.is_(None),
                ClassSubjectAssignment.division_id == student.division_id,
            ),
            ClassSubjectAssignment.is_active.is_(True),
        ).limit(1)
    ).first()
    if not enrolled:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Student is not enrolled in this subject")
    if user.role == UserRole.TEACHER and not _teacher_can_access_division(
        db, user, assessment.subject_id, student.division_id, student.batch_id
    ):
        raise _http_error(
            status.HTTP_403_FORBIDDEN,
            "Student is outside teacher assignment",
        )
    if data.marks > assessment.max_marks:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Marks exceed assessment maximum")
    result = db.execute(
        select(AssessmentResult).where(
            AssessmentResult.assessment_id == assessment_id,
            AssessmentResult.student_id == student.id,
        )
    ).scalar_one_or_none()
    if result is None:
        result = AssessmentResult(
            assessment_id=assessment_id, student_id=student.id, recorded_by=user.id,
            marks=data.marks, feedback=data.feedback,
        )
        db.add(result)
    else:
        result.marks = data.marks
        result.feedback = data.feedback
        result.recorded_by = user.id
    db.commit()
    db.refresh(result)
    return result


def update_assessment_result(
    db: Session,
    user: User,
    assessment_id: int,
    student_id: int,
    data: AssessmentMarksUpdate,
) -> AssessmentResult:
    return record_assessment_result(
        db,
        user,
        assessment_id,
        AssessmentResultCreate(
            student_id=student_id, marks=data.marks, feedback=data.feedback
        ),
    )


def list_assessment_results(
    db: Session, user: User, assessment_id: int
) -> list[AssessmentResult]:
    assessment = _get_or_404(db, Assessment, assessment_id, "Assessment")
    query = select(AssessmentResult).where(
        AssessmentResult.assessment_id == assessment.id
    )
    if user.role == UserRole.STUDENT:
        query = query.where(AssessmentResult.student_id == _student_profile(user).id)
    elif user.role == UserRole.TEACHER and assessment.teacher_id != _teacher_profile(user).id:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Cannot view another teacher's results")
    return list(db.execute(query.order_by(AssessmentResult.student_id)).scalars())


def get_performance_report(
    db: Session, user: User, student_id: Optional[int] = None, subject_id: Optional[int] = None
) -> dict:
    if user.role == UserRole.STUDENT:
        student = _student_profile(user)
    else:
        if student_id is None:
            raise _http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "student_id is required")
        student = _get_or_404(db, Student, student_id, "Student")
    if user.role == UserRole.TEACHER:
        teacher = _teacher_profile(user)
        scope_query = select(TeacherAssignment.id).where(
            _teacher_student_assignment_scope(teacher.id, student, subject_id)
        )
        if not db.execute(scope_query.limit(1)).first():
            raise _http_error(status.HTTP_403_FORBIDDEN, "Student is outside teacher assignment")
        query_subjects = select(TeacherAssignment.subject_id).where(
            _teacher_student_assignment_scope(teacher.id, student)
        )
    else:
        query_subjects = None
    if user.role == UserRole.STUDENT and subject_id is not None:
        _can_access_subject(db, user, subject_id)
    query = (
        select(
            Assessment.subject_id,
            Subject.name,
            func.count(AssessmentResult.id),
            func.avg(AssessmentResult.marks / Assessment.max_marks * 100),
        )
        .join(AssessmentResult, AssessmentResult.assessment_id == Assessment.id)
        .join(Subject, Subject.id == Assessment.subject_id)
        .where(AssessmentResult.student_id == student.id)
        .group_by(Assessment.subject_id, Subject.name)
    )
    if subject_id is not None:
        query = query.where(Assessment.subject_id == subject_id)
    if query_subjects is not None:
        query = query.where(Assessment.subject_id.in_(query_subjects))
    rows = db.execute(query).all()
    return {
        "student_id": student.id,
        "subject_performance": [
            {
                "subject_id": subject,
                "subject_name": name,
                "assessments_count": count,
                "average_percentage": round(float(average or 0), 2),
            }
            for subject, name, count, average in rows
        ],
    }


def get_subject_averages(
    db: Session,
    user: User,
    subject_id: Optional[int] = None,
    division_id: Optional[int] = None,
) -> dict:
    if user.role == UserRole.STUDENT:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Only staff can view class averages")
    query = (
        select(
            Assessment.subject_id,
            Subject.name,
            func.count(AssessmentResult.id),
            func.avg(AssessmentResult.marks / Assessment.max_marks * 100),
        )
        .join(AssessmentResult, AssessmentResult.assessment_id == Assessment.id)
        .join(Subject, Subject.id == Assessment.subject_id)
        .join(Student, Student.id == AssessmentResult.student_id)
        .where(Assessment.is_active.is_(True))
        .group_by(Assessment.subject_id, Subject.name)
    )
    if subject_id is not None:
        query = query.where(Assessment.subject_id == subject_id)
    if division_id is not None:
        query = query.where(Student.division_id == division_id)
    if user.role == UserRole.TEACHER:
        teacher_id = _teacher_profile(user).id
        query = query.where(
            exists(
                select(TeacherAssignment.id).where(
                    _teacher_student_assignment_scope(
                        teacher_id, Student, Assessment.subject_id
                    ),
                )
            )
        )
    rows = db.execute(query).all()
    return {
        "subject_averages": [
            {
                "subject_id": current_subject_id,
                "subject_name": name,
                "results_count": count,
                "average_percentage": round(float(average or 0), 2),
            }
            for current_subject_id, name, count, average in rows
        ]
    }


def create_activity(db: Session, user: User, data: StudentActivityCreate) -> StudentActivity:
    if data.subject_id is not None and not db.get(Subject, data.subject_id):
        raise _http_error(status.HTTP_404_NOT_FOUND, "Subject not found")
    if user.role == UserRole.TEACHER and data.subject_id is not None:
        _require_teaching_scope(db, user, data.subject_id)
    activity = StudentActivity(**data.model_dump(), created_by=user.id)
    db.add(activity)
    db.commit()
    db.refresh(activity)
    return activity


def list_activities(db: Session, user: User) -> list[StudentActivity]:
    query = select(StudentActivity).where(StudentActivity.is_active.is_(True))
    if user.role == UserRole.STUDENT:
        student = _student_profile(user)
        query = query.join(ActivityParticipation).where(
            ActivityParticipation.student_id == student.id
        )
    elif user.role == UserRole.TEACHER:
        query = query.where(StudentActivity.created_by == user.id)
    return list(db.execute(query.order_by(StudentActivity.activity_date.desc())).unique().scalars())


def record_participation(
    db: Session, user: User, activity_id: int, data: ActivityParticipationCreate
) -> ActivityParticipation:
    activity = _get_or_404(db, StudentActivity, activity_id, "Activity")
    if user.role == UserRole.STUDENT:
        student = _student_profile(user)
        if data.student_id != student.id:
            raise _http_error(status.HTTP_403_FORBIDDEN, "Students can only record their own participation")
    else:
        student = _get_or_404(db, Student, data.student_id, "Student")
        if user.role == UserRole.TEACHER:
            if activity.created_by != user.id:
                raise _http_error(status.HTTP_403_FORBIDDEN, "Cannot manage another user's activity")
            if not db.execute(
                select(TeacherAssignment.id).where(
                    _teacher_student_assignment_scope(
                        _teacher_profile(user).id, student, activity.subject_id
                    )
                ).limit(1)
            ).first():
                raise _http_error(
                    status.HTTP_403_FORBIDDEN,
                    "Student is outside teacher assignment",
                )
    participation = db.execute(
        select(ActivityParticipation).where(
            ActivityParticipation.activity_id == activity.id,
            ActivityParticipation.student_id == student.id,
        )
    ).scalar_one_or_none()
    if participation is None:
        participation = ActivityParticipation(activity_id=activity.id, **data.model_dump())
        db.add(participation)
    else:
        for key, value in data.model_dump(exclude={"student_id"}).items():
            setattr(participation, key, value)
    db.commit()
    db.refresh(participation)
    return participation


def activity_statistics(db: Session, user: User, student_id: Optional[int] = None) -> dict:
    if user.role == UserRole.STUDENT:
        student_id = _student_profile(user).id
    elif student_id is None:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "student_id is required")
    student = _get_or_404(db, Student, student_id, "Student")
    if user.role == UserRole.TEACHER and not db.execute(
        select(TeacherAssignment.id).where(
            _teacher_student_assignment_scope(
                _teacher_profile(user).id, student
            ),
        ).limit(1)
    ).first():
        raise _http_error(status.HTTP_403_FORBIDDEN, "Student is outside teacher assignment")
    query = (
        select(StudentActivity.activity_type, func.count(ActivityParticipation.id), func.sum(ActivityParticipation.points))
        .join(ActivityParticipation, ActivityParticipation.activity_id == StudentActivity.id)
        .where(
            ActivityParticipation.student_id == student_id,
            ActivityParticipation.participated.is_(True),
        )
        .group_by(StudentActivity.activity_type)
    )
    return {
        "student_id": student_id,
        "statistics": [
            {"activity_type": kind, "participation_count": count, "points": points or 0}
            for kind, count, points in db.execute(query).all()
        ],
    }


def activity_history(db: Session, user: User, student_id: Optional[int] = None) -> list[ActivityParticipation]:
    if user.role == UserRole.STUDENT:
        student_id = _student_profile(user).id
    elif student_id is None:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "student_id is required")
    student = _get_or_404(db, Student, student_id, "Student")
    if user.role == UserRole.TEACHER and not db.execute(
        select(TeacherAssignment.id).where(
            _teacher_student_assignment_scope(
                _teacher_profile(user).id, student
            ),
        ).limit(1)
    ).first():
        raise _http_error(status.HTTP_403_FORBIDDEN, "Student is outside teacher assignment")
    return list(
        db.execute(
            select(ActivityParticipation)
            .options(joinedload(ActivityParticipation.activity))
            .where(ActivityParticipation.student_id == student.id)
            .order_by(ActivityParticipation.created_at.desc())
        ).scalars()
    )


def list_recommendations(db: Session, user: User, student_id: Optional[int] = None) -> list:
    from app.models.learning import AIRecommendation

    if user.role == UserRole.STUDENT:
        student_id = _student_profile(user).id
    elif student_id is None:
        raise _http_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "student_id is required")
    student = _get_or_404(db, Student, student_id, "Student")
    query = select(AIRecommendation).where(AIRecommendation.student_id == student.id)
    if user.role == UserRole.TEACHER:
        teacher_id = _teacher_profile(user).id
        scope = select(TeacherAssignment.id).where(
            _teacher_student_assignment_scope(teacher_id, student),
            or_(
                AIRecommendation.subject_id.is_(None),
                TeacherAssignment.subject_id == AIRecommendation.subject_id,
            ),
        )
        query = query.where(exists(scope))
    return list(db.execute(query.order_by(AIRecommendation.created_at.desc())).scalars())


def list_notifications(db: Session, user: User) -> list[Notification]:
    return list(
        db.execute(
            select(Notification)
            .where(Notification.recipient_user_id == user.id)
            .order_by(Notification.created_at.desc())
        ).scalars()
    )


def mark_notification_read(db: Session, user: User, notification_id: int) -> Notification:
    notification = _get_or_404(db, Notification, notification_id, "Notification")
    if notification.recipient_user_id != user.id:
        raise _http_error(status.HTTP_403_FORBIDDEN, "Cannot access another user's notification")
    notification.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notification)
    return notification
