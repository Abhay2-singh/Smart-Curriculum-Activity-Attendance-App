from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.assignments import ClassSubjectAssignment, TeacherAssignment
from app.models.enums import UserRole
from app.models.learning import Assignment, AssignmentSubmission
from app.models.profiles import Student
from app.models.subject import Subject
from app.models.user import User
from app.services import academic_gap_service, learning_service
from app.services.learning_service import _as_utc


def _subject_ids_for_student(db: Session, user: User, student: Student) -> list[int]:
    if user.role == UserRole.TEACHER:
        teacher = user.teacher_profile
        if teacher is None:
            raise HTTPException(status_code=403, detail="Teacher profile is required")
        query = select(TeacherAssignment.subject_id).where(
            learning_service._teacher_student_assignment_scope(teacher.id, student)
        )
    else:
        query = select(ClassSubjectAssignment.subject_id).where(
            ClassSubjectAssignment.academic_class_id == student.academic_class_id,
            ClassSubjectAssignment.academic_year_id == student.academic_year_id,
            ClassSubjectAssignment.semester_id == student.semester_id,
            or_(
                ClassSubjectAssignment.division_id.is_(None),
                ClassSubjectAssignment.division_id == student.division_id,
            ),
            ClassSubjectAssignment.is_active.is_(True),
        )
    return list(db.execute(query.distinct().order_by(query.selected_columns[0])).scalars())


def get_next_best_actions(
    db: Session,
    user: User,
    student_id: Optional[int] = None,
    subject_id: Optional[int] = None,
) -> list[dict]:
    if user.role == UserRole.STUDENT:
        student = user.student_profile
        if student is None:
            raise HTTPException(status_code=403, detail="Student profile is required")
    else:
        if student_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="student_id is required for staff requests",
            )
        student = db.get(Student, student_id)
        if student is None:
            raise HTTPException(status_code=404, detail="Student not found")
        academic_gap_service._check_student_scope(db, user, student, subject_id)

    subject_ids = (
        [subject_id]
        if subject_id is not None
        else _subject_ids_for_student(db, user, student)
    )
    actions: list[dict] = []
    now = datetime.now(timezone.utc)
    for current_subject_id in subject_ids:
        subject = db.get(Subject, current_subject_id)
        if subject is None:
            continue
        indicators = academic_gap_service.calculate_academic_gaps(
            db, student.id, current_subject_id
        )
        has_attendance_sessions = indicators["attendance_sessions_count"] > 0
        syllabus = learning_service.get_syllabus_progress(
            db, user, current_subject_id, student.id if user.role != UserRole.STUDENT else None
        )
        assignments = list(
            db.execute(
                select(Assignment)
                .where(
                    Assignment.subject_id == current_subject_id,
                    Assignment.is_active.is_(True),
                    or_(
                        Assignment.division_id.is_(None),
                        Assignment.division_id == student.division_id,
                    ),
                    ~select(AssignmentSubmission.id)
                    .where(
                        AssignmentSubmission.assignment_id == Assignment.id,
                        AssignmentSubmission.student_id == student.id,
                    )
                    .exists(),
                )
                .order_by(Assignment.due_at)
            ).scalars()
        )

        attendance_gap = indicators["attendance_gap"]
        if has_attendance_sessions and attendance_gap > 0:
            actions.append(
                {
                    "priority": "HIGH" if attendance_gap >= settings.ATTENDANCE_GAP_HIGH else "MEDIUM",
                    "action": f"Improve attendance in {subject.name}",
                    "rationale": (
                        f"Attendance is {indicators['attendance_percentage']:.1f}%, "
                        f"{attendance_gap:.1f} percentage points below the "
                        f"{indicators['required_attendance_percentage']:.1f}% requirement."
                    ),
                    "subject_id": subject.id,
                    "subject_name": subject.name,
                    "indicator": "attendance_gap_percentage_points",
                    "value": attendance_gap,
                    "target": indicators["required_attendance_percentage"],
                }
            )

        curriculum_gap = syllabus["curriculum_gap_percentage"]
        if curriculum_gap >= settings.CURRICULUM_GAP_MEDIUM:
            actions.append(
                {
                    "priority": "HIGH" if curriculum_gap >= settings.CURRICULUM_GAP_HIGH else "MEDIUM",
                    "action": f"Catch up on the {subject.name} syllabus",
                    "rationale": (
                        f"Actual syllabus progress is {syllabus['actual_progress_percentage']:.1f}% "
                        f"against {syllabus['expected_progress_percentage']:.1f}% expected."
                    ),
                    "subject_id": subject.id,
                    "subject_name": subject.name,
                    "indicator": "curriculum_gap_percentage_points",
                    "value": curriculum_gap,
                }
            )

        if assignments:
            overdue = [
                assignment
                for assignment in assignments
                if _as_utc(assignment.due_at) < now
            ]
            due_description = (
                f"The earliest deadline is {_as_utc(assignments[0].due_at).isoformat()}."
                if assignments[0].due_at
                else ""
            )
            actions.append(
                {
                    "priority": "HIGH" if overdue else "MEDIUM",
                    "action": f"Complete pending assignments for {subject.name}",
                    "rationale": (
                        f"{len(assignments)} active assignment(s) have no submission; "
                        f"{len(overdue)} are overdue. {due_description}"
                    ).strip(),
                    "subject_id": subject.id,
                    "subject_name": subject.name,
                    "indicator": "pending_assignments",
                    "value": len(assignments),
                }
            )

        performance = indicators["performance_percentage"]
        if (
            performance is not None
            and performance < settings.PERFORMANCE_TARGET_PERCENTAGE
        ):
            actions.append(
                {
                    "priority": (
                        "HIGH"
                        if performance < settings.PERFORMANCE_HIGH_RISK_PERCENTAGE
                        else "MEDIUM"
                    ),
                    "action": f"Review assessment feedback in {subject.name}",
                    "rationale": (
                        f"Recorded assessment average is {performance:.1f}%, below the "
                        f"{settings.PERFORMANCE_TARGET_PERCENTAGE:.1f}% configured target."
                    ),
                    "subject_id": subject.id,
                    "subject_name": subject.name,
                    "indicator": "assessment_average_percentage",
                    "value": performance,
                    "target": settings.PERFORMANCE_TARGET_PERCENTAGE,
                }
            )

    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return sorted(
        actions,
        key=lambda action: (
            priority_order[action["priority"]],
            action["subject_name"],
            action["indicator"],
        ),
    )
