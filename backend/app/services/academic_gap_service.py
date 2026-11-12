from datetime import date, datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.academic_gap import AcademicGapSnapshot
from app.models.assignments import TeacherAssignment
from app.models.attendance import AttendanceRecord, AttendanceSession
from app.models.enums import AttendanceStatus, SessionStatus, UserRole
from app.models.learning import (
    AcademicAlert,
    AcademicRiskRecord,
    AIRecommendation,
    Notification,
    Assessment,
    AssessmentResult,
    Assignment,
    AssignmentSubmission,
    CurriculumTopic,
    CurriculumUnit,
)
from app.models.profiles import Student
from app.models.subject import Subject
from app.models.user import User
from app.services.learning_service import (
    _get_or_404,
    _can_access_subject,
    _student_profile,
    _teacher_can_access_division,
    _teacher_student_assignment_scope,
    get_syllabus_progress,
)


def _check_student_scope(
    db: Session, user: User, student: Student, subject_id: Optional[int]
) -> None:
    if user.role == UserRole.STUDENT:
        if _student_profile(user).id != student.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only view their own academic data",
            )
        if subject_id is not None:
            _can_access_subject(db, user, subject_id)
    elif user.role == UserRole.TEACHER:
        if subject_id is not None:
            allowed = _teacher_can_access_division(
                db, user, subject_id, student.division_id, student.batch_id
            )
        else:
            allowed = db.execute(
                select(TeacherAssignment.id).where(
                    _teacher_student_assignment_scope(
                        user.teacher_profile.id, student
                    ),
                ).limit(1)
            ).first() is not None if user.teacher_profile else False
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student is outside teacher assignment",
            )


def calculate_academic_gaps(
    db: Session, student_id: int, subject_id: Optional[int] = None
) -> dict:
    student = _get_or_404(db, Student, student_id, "Student")
    if subject_id is not None:
        _get_or_404(db, Subject, subject_id, "Subject")
    session_query = select(AttendanceSession.id).where(
        AttendanceSession.division_id == student.division_id,
        AttendanceSession.session_date <= date.today(),
        AttendanceSession.status != SessionStatus.CANCELLED,
        or_(
            AttendanceSession.batch_id.is_(None),
            AttendanceSession.batch_id == student.batch_id,
        ),
    )
    if subject_id is not None:
        session_query = session_query.where(AttendanceSession.subject_id == subject_id)
    session_ids = list(db.execute(session_query).scalars())
    attendance: Optional[float] = None
    if session_ids:
        attended_count = db.execute(
            select(func.count(func.distinct(AttendanceRecord.attendance_session_id))).where(
                AttendanceRecord.student_id == student.id,
                AttendanceRecord.attendance_session_id.in_(session_ids),
                AttendanceRecord.status == AttendanceStatus.PRESENT,
            )
        ).scalar_one()
        attendance = round(attended_count * 100 / len(session_ids), 2)

    syllabus = None
    if subject_id is not None:
        syllabus = get_syllabus_progress(db, _admin_user_for_calculation(), subject_id, student.id)
    else:
        subject_ids = list(
            db.execute(
                select(CurriculumUnit.subject_id)
                .join(CurriculumTopic)
                .distinct()
                .where(CurriculumUnit.subject_id.in_(
                    select(AttendanceSession.subject_id).where(
                        AttendanceSession.division_id == student.division_id
                    )
                ))
            ).scalars()
        )
        progress_items = []
        for current_subject_id in subject_ids:
            progress_items.append(
                get_syllabus_progress(
                    db, _admin_user_for_calculation(), current_subject_id, student.id
                )
            )
        if progress_items:
            syllabus = {
                "expected_progress_percentage": round(
                    sum(item["expected_progress_percentage"] for item in progress_items)
                    / len(progress_items),
                    2,
                ),
                "actual_progress_percentage": round(
                    sum(item["actual_progress_percentage"] for item in progress_items)
                    / len(progress_items),
                    2,
                ),
            }

    expected_syllabus = (
        syllabus["expected_progress_percentage"] if syllabus else 0.0
    )
    actual_syllabus = syllabus["actual_progress_percentage"] if syllabus else 0.0
    curriculum_gap = round(max(0.0, expected_syllabus - actual_syllabus), 2)

    assignment_query = select(Assignment.id).where(
        Assignment.is_active.is_(True),
        Assignment.due_at < datetime.now(timezone.utc),
        (Assignment.division_id.is_(None)) | (Assignment.division_id == student.division_id),
        ~select(AssignmentSubmission.id).where(
            AssignmentSubmission.assignment_id == Assignment.id,
            AssignmentSubmission.student_id == student.id,
        ).exists(),
    )
    if subject_id is not None:
        assignment_query = assignment_query.where(Assignment.subject_id == subject_id)
    pending_assignments = len(list(db.execute(assignment_query).scalars()))

    performance_query = (
        select(func.avg(AssessmentResult.marks / Assessment.max_marks * 100))
        .join(Assessment, Assessment.id == AssessmentResult.assessment_id)
        .where(
            AssessmentResult.student_id == student.id,
            Assessment.is_active.is_(True),
        )
    )
    if subject_id is not None:
        performance_query = performance_query.where(Assessment.subject_id == subject_id)
    performance_value = db.execute(performance_query).scalar_one()
    performance = round(float(performance_value), 2) if performance_value is not None else None

    required_attendance = settings.REQUIRED_ATTENDANCE_PERCENTAGE
    attendance_gap = (
        round(max(0.0, required_attendance - attendance), 2)
        if attendance is not None
        else 0.0
    )
    performance_gap = (
        round(max(0.0, settings.PERFORMANCE_TARGET_PERCENTAGE - performance), 2)
        if performance is not None
        else 0.0
    )
    return {
        "student_id": student.id,
        "subject_id": subject_id,
        "attendance_percentage": attendance,
        "attendance_sessions_count": len(session_ids),
        "required_attendance_percentage": required_attendance,
        "attendance_gap": attendance_gap,
        "expected_syllabus_progress_percentage": expected_syllabus,
        "actual_syllabus_progress_percentage": actual_syllabus,
        "curriculum_gap": curriculum_gap,
        "pending_assignments": pending_assignments,
        "performance_percentage": performance,
        "performance_gap": performance_gap,
    }


def _admin_user_for_calculation() -> User:
    # Internal calculation uses the subject access helper only for a trusted staff call.
    return User(id=0, username="internal", email="internal@invalid", password_hash="", role=UserRole.ADMIN)


def classify_risk(indicators: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    high_signals = 0
    medium_signals = 0

    attendance_gap = indicators["attendance_gap"]
    if attendance_gap >= settings.ATTENDANCE_GAP_HIGH:
        high_signals += 1
        reasons.append(f"Attendance is {attendance_gap:.1f} percentage points below target")
    elif attendance_gap >= settings.ATTENDANCE_GAP_MEDIUM:
        medium_signals += 1
        reasons.append(f"Attendance is {attendance_gap:.1f} percentage points below target")

    curriculum_gap = indicators["curriculum_gap"]
    if curriculum_gap >= settings.CURRICULUM_GAP_HIGH:
        high_signals += 1
        reasons.append(f"Syllabus progress is {curriculum_gap:.1f} points behind expected")
    elif curriculum_gap >= settings.CURRICULUM_GAP_MEDIUM:
        medium_signals += 1
        reasons.append(f"Syllabus progress is {curriculum_gap:.1f} points behind expected")

    pending = indicators["pending_assignments"]
    if pending >= settings.PENDING_ASSIGNMENTS_HIGH:
        high_signals += 1
        reasons.append(f"{pending} overdue assignments are not submitted")
    elif pending >= settings.PENDING_ASSIGNMENTS_MEDIUM:
        medium_signals += 1
        reasons.append(f"{pending} overdue assignments are not submitted")

    performance = indicators["performance_percentage"]
    if performance is not None:
        if performance < settings.PERFORMANCE_HIGH_RISK_PERCENTAGE:
            high_signals += 1
            reasons.append(f"Assessment average is low at {performance:.1f}%")
        elif performance < settings.PERFORMANCE_TARGET_PERCENTAGE:
            medium_signals += 1
            reasons.append(f"Assessment average is below target at {performance:.1f}%")

    if high_signals or medium_signals >= 2:
        level = "HIGH"
    elif medium_signals:
        level = "MEDIUM"
    else:
        level = "LOW"
    if not reasons:
        reasons.append("No configured academic risk thresholds are currently breached")
    return level, reasons


def analyze_student(
    db: Session,
    user: User,
    student_id: Optional[int],
    subject_id: Optional[int],
    refresh_existing_alerts: bool = False,
) -> tuple[AcademicGapSnapshot, AcademicRiskRecord]:
    if user.role == UserRole.STUDENT:
        student = _student_profile(user)
        student_id = student.id
    elif student_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="student_id is required",
        )
    else:
        student = _get_or_404(db, Student, student_id, "Student")
    _check_student_scope(db, user, student, subject_id)

    indicators = calculate_academic_gaps(db, student.id, subject_id)
    risk_level, reasons = classify_risk(indicators)
    gap = AcademicGapSnapshot(
        student_id=student.id,
        subject_id=subject_id,
        attendance_gap=indicators["attendance_gap"],
        curriculum_gap=indicators["curriculum_gap"],
        assignment_gap=indicators["pending_assignments"],
        performance_gap=indicators["performance_gap"],
        indicators=indicators,
    )
    risk = AcademicRiskRecord(
        student_id=student.id,
        subject_id=subject_id,
        risk_level=risk_level,
        risk_reasons=reasons,
        indicators=indicators,
    )
    db.add_all([gap, risk])
    db.flush()
    existing_alert = None
    if refresh_existing_alerts:
        existing_alert = db.execute(
            select(AcademicAlert)
            .where(
                AcademicAlert.student_id == student.id,
                AcademicAlert.subject_id == subject_id,
                AcademicAlert.category == "ACADEMIC_RISK",
                AcademicAlert.status == "OPEN",
            )
            .order_by(AcademicAlert.id.desc())
            .limit(1)
        ).scalars().first()

    if refresh_existing_alerts and risk_level == "LOW":
        if existing_alert:
            existing_alert.status = "RESOLVED"
    elif refresh_existing_alerts and existing_alert:
        changed_severity = existing_alert.severity != risk_level
        existing_alert.severity = risk_level
        existing_alert.title = f"{risk_level.title()} academic risk detected"
        existing_alert.details = "; ".join(reasons)
        if changed_severity and student.user_id is not None:
            db.add(
                Notification(
                    recipient_user_id=student.user_id,
                    title=existing_alert.title,
                    message=existing_alert.details,
                    category="ACADEMIC_RISK",
                )
            )
    elif risk_level != "LOW":
        alert = AcademicAlert(
            student_id=student.id,
            subject_id=subject_id,
            category="ACADEMIC_RISK",
            severity=risk_level,
            title=f"{risk_level.title()} academic risk detected",
            details="; ".join(reasons),
        )
        db.add(alert)
        if student.user_id is not None:
            db.add(
                Notification(
                    recipient_user_id=student.user_id,
                    title=alert.title,
                    message=alert.details or "Academic risk indicators require attention.",
                    category="ACADEMIC_RISK",
                )
            )
    if risk_level != "LOW":
        action_by_reason = {
            "attendance": "Meet with your teacher to plan attendance recovery",
            "syllabus": "Review the outstanding syllabus topics with your teacher",
            "assignment": "Submit overdue assignments or contact the instructor",
            "assessment": "Arrange targeted support for upcoming assessments",
        }
        for key, action in action_by_reason.items():
            if any(key in reason.lower() for reason in reasons):
                if refresh_existing_alerts and db.execute(
                    select(AIRecommendation.id).where(
                        AIRecommendation.student_id == student.id,
                        AIRecommendation.subject_id == subject_id,
                        AIRecommendation.action == action,
                        AIRecommendation.is_completed.is_(False),
                    ).limit(1)
                ).first():
                    continue
                db.add(
                    AIRecommendation(
                        student_id=student.id,
                        subject_id=subject_id,
                        risk_record_id=risk.id,
                        action=action,
                        rationale="Generated from the recorded academic risk indicators",
                        priority=risk_level,
                    )
                )
    db.commit()
    db.refresh(gap)
    db.refresh(risk)
    return gap, risk


def list_risk_records(
    db: Session,
    user: User,
    student_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    risk_level: Optional[str] = None,
) -> list[AcademicRiskRecord]:
    query = select(AcademicRiskRecord)
    if user.role == UserRole.STUDENT:
        student_id = _student_profile(user).id
    if student_id is not None:
        student = _get_or_404(db, Student, student_id, "Student")
        _check_student_scope(db, user, student, subject_id)
        query = query.where(AcademicRiskRecord.student_id == student_id)
    if subject_id is not None:
        query = query.where(AcademicRiskRecord.subject_id == subject_id)
    if risk_level is not None:
        query = query.where(AcademicRiskRecord.risk_level == risk_level)
    if user.role == UserRole.TEACHER:
        teacher = user.teacher_profile
        if teacher is None:
            raise HTTPException(status_code=403, detail="Teacher profile is required")
        query = query.join(Student, Student.id == AcademicRiskRecord.student_id).where(
            exists(
                select(TeacherAssignment.id).where(
                    _teacher_student_assignment_scope(
                        teacher.id, Student
                    ),
                    or_(
                        AcademicRiskRecord.subject_id.is_(None),
                        TeacherAssignment.subject_id == AcademicRiskRecord.subject_id,
                    ),
                )
            )
        )
    return list(
        db.execute(query.order_by(AcademicRiskRecord.detected_at.desc())).scalars()
    )


def list_gap_snapshots(
    db: Session,
    user: User,
    student_id: Optional[int] = None,
    subject_id: Optional[int] = None,
) -> list[AcademicGapSnapshot]:
    query = select(AcademicGapSnapshot)
    if user.role == UserRole.STUDENT:
        student_id = _student_profile(user).id
    if student_id is not None:
        student = _get_or_404(db, Student, student_id, "Student")
        _check_student_scope(db, user, student, subject_id)
        query = query.where(AcademicGapSnapshot.student_id == student_id)
    if subject_id is not None:
        query = query.where(AcademicGapSnapshot.subject_id == subject_id)
    if user.role == UserRole.TEACHER:
        teacher = user.teacher_profile
        if teacher is None:
            raise HTTPException(status_code=403, detail="Teacher profile is required")
        query = query.join(Student, Student.id == AcademicGapSnapshot.student_id).where(
            exists(
                select(TeacherAssignment.id).where(
                    _teacher_student_assignment_scope(
                        teacher.id, Student
                    ),
                    or_(
                        AcademicGapSnapshot.subject_id.is_(None),
                        TeacherAssignment.subject_id == AcademicGapSnapshot.subject_id,
                    ),
                )
            )
        )
    return list(db.execute(query.order_by(AcademicGapSnapshot.detected_at.desc())).scalars())


def list_academic_alerts(
    db: Session, user: User, student_id: Optional[int] = None
) -> list[AcademicAlert]:
    query = select(AcademicAlert)
    if user.role == UserRole.STUDENT:
        student_id = _student_profile(user).id
    if student_id is not None:
        student = _get_or_404(db, Student, student_id, "Student")
        _check_student_scope(db, user, student, None)
        query = query.where(AcademicAlert.student_id == student_id)
    if user.role == UserRole.TEACHER:
        teacher = user.teacher_profile
        if teacher is None:
            raise HTTPException(status_code=403, detail="Teacher profile is required")
        query = query.join(Student, Student.id == AcademicAlert.student_id).where(
            exists(
                select(TeacherAssignment.id).where(
                    _teacher_student_assignment_scope(
                        teacher.id, Student
                    ),
                    or_(
                        AcademicAlert.subject_id.is_(None),
                        TeacherAssignment.subject_id == AcademicAlert.subject_id,
                    ),
                )
            )
        )
    return list(db.execute(query.order_by(AcademicAlert.detected_at.desc())).scalars())
