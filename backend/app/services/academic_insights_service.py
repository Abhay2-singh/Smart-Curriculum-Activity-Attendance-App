from typing import Optional

from fastapi import HTTPException
from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.models.assignments import ClassSubjectAssignment, TeacherAssignment
from app.models.academic import Department
from app.models.enums import UserRole
from app.models.profiles import Student
from app.models.subject import Subject
from app.models.user import User
from app.services.academic_gap_service import calculate_academic_gaps, classify_risk
from app.services.learning_service import (
    _require_teaching_scope,
    _teacher_student_assignment_scope,
)


def get_staff_academic_insights(
    db: Session,
    user: User,
    subject_id: Optional[int] = None,
    department_id: Optional[int] = None,
    limit: int = 50,
) -> dict:
    if user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Academic insights are restricted to staff")
    if not 1 <= limit <= 200:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 200")

    students_query = select(Student).where(Student.is_active.is_(True))
    if user.role == UserRole.TEACHER:
        teacher = user.teacher_profile
        if teacher is None:
            raise HTTPException(status_code=403, detail="Teacher profile is required")
        if subject_id is None:
            raise HTTPException(status_code=422, detail="Teachers must select a subject")
        _require_teaching_scope(db, user, subject_id)
        if department_id is not None and department_id != teacher.department_id:
            raise HTTPException(status_code=403, detail="Department is outside teacher scope")
        assignment_exists = exists(
            select(TeacherAssignment.id).where(
                _teacher_student_assignment_scope(
                    teacher.id, Student, subject_id
                )
            )
        )
        students_query = students_query.where(assignment_exists)
    else:
        if department_id is not None:
            if db.get(Department, department_id) is None:
                raise HTTPException(status_code=404, detail="Department not found")
            students_query = students_query.where(Student.department_id == department_id)
        if subject_id is not None:
            subject = db.get(Subject, subject_id)
            if subject is None:
                raise HTTPException(status_code=404, detail="Subject not found")
            enrollment_exists = exists(
                select(ClassSubjectAssignment.id).where(
                    ClassSubjectAssignment.subject_id == subject_id,
                    ClassSubjectAssignment.academic_class_id == Student.academic_class_id,
                    ClassSubjectAssignment.academic_year_id == Student.academic_year_id,
                    ClassSubjectAssignment.semester_id == Student.semester_id,
                    or_(
                        ClassSubjectAssignment.division_id.is_(None),
                        ClassSubjectAssignment.division_id == Student.division_id,
                    ),
                    ClassSubjectAssignment.is_active.is_(True),
                )
            )
            students_query = students_query.where(enrollment_exists)
    if subject_id is not None and department_id is not None:
        subject = db.get(Subject, subject_id)
        if subject.department_id != department_id:
            raise HTTPException(status_code=422, detail="Subject is outside the department")

    students_query = students_query.order_by(Student.id).limit(limit + 1)
    students = list(db.execute(students_query).scalars())
    truncated = len(students) > limit
    students = students[:limit]
    subject_names = {
        subject.id: subject.name
        for subject in db.execute(select(Subject)).scalars()
    }
    department_names = {
        department.id: department.name
        for department in db.execute(select(Department)).scalars()
    }

    risk_distribution = {"LOW": 0, "MEDIUM": 0, "HIGH": 0}
    subject_totals: dict[int, dict] = {}
    department_totals: dict[int, dict] = {}
    attention = []
    analyzed = 0
    for student in students:
        if subject_id is not None:
            student_subject_ids = [subject_id]
        else:
            student_subject_ids = list(
                db.execute(
                    select(ClassSubjectAssignment.subject_id)
                    .where(
                        ClassSubjectAssignment.academic_class_id == student.academic_class_id,
                        ClassSubjectAssignment.academic_year_id == student.academic_year_id,
                        ClassSubjectAssignment.semester_id == student.semester_id,
                        or_(
                            ClassSubjectAssignment.division_id.is_(None),
                            ClassSubjectAssignment.division_id == student.division_id,
                        ),
                        ClassSubjectAssignment.is_active.is_(True),
                    )
                    .distinct()
                ).scalars()
            )
        for current_subject_id in student_subject_ids:
            indicators = calculate_academic_gaps(db, student.id, current_subject_id)
            risk_level, reasons = classify_risk(indicators)
            risk_distribution[risk_level] += 1
            analyzed += 1
            totals = subject_totals.setdefault(
                current_subject_id,
                {
                    "subject_id": current_subject_id,
                    "subject_name": subject_names.get(current_subject_id, "Unknown subject"),
                    "students_analyzed": 0,
                    "risk_distribution": {"LOW": 0, "MEDIUM": 0, "HIGH": 0},
                    "attendance_gap_total": 0.0,
                    "curriculum_gap_total": 0.0,
                },
            )
            totals["students_analyzed"] += 1
            totals["risk_distribution"][risk_level] += 1
            totals["attendance_gap_total"] += indicators["attendance_gap"]
            totals["curriculum_gap_total"] += indicators["curriculum_gap"]
            department = department_totals.setdefault(
                student.department_id,
                {
                    "department_id": student.department_id,
                    "department_name": department_names.get(
                        student.department_id, "Unknown department"
                    ),
                    "student_subject_analyses": 0,
                    "risk_distribution": {"LOW": 0, "MEDIUM": 0, "HIGH": 0},
                    "attendance_gap_total": 0.0,
                    "curriculum_gap_total": 0.0,
                },
            )
            department["student_subject_analyses"] += 1
            department["risk_distribution"][risk_level] += 1
            department["attendance_gap_total"] += indicators["attendance_gap"]
            department["curriculum_gap_total"] += indicators["curriculum_gap"]
            if risk_level != "LOW" or indicators["pending_assignments"] > 0:
                attention.append(
                    {
                        "student_id": student.id,
                        "student_name": student.full_name,
                        "department_id": student.department_id,
                        "department_name": department_names.get(
                            student.department_id, "Unknown department"
                        ),
                        "subject_id": current_subject_id,
                        "subject_name": subject_names.get(current_subject_id, "Unknown subject"),
                        "risk_level": risk_level,
                        "risk_reasons": reasons,
                        "attendance_percentage": indicators["attendance_percentage"],
                        "required_attendance_percentage": indicators[
                            "required_attendance_percentage"
                        ],
                        "curriculum_gap": indicators["curriculum_gap"],
                        "pending_assignments": indicators["pending_assignments"],
                        "performance_percentage": indicators["performance_percentage"],
                    }
                )

    subjects = []
    for totals in subject_totals.values():
        count = totals["students_analyzed"]
        attendance_gap_total = totals["attendance_gap_total"]
        curriculum_gap_total = totals["curriculum_gap_total"]
        subject_summary = {
            key: value
            for key, value in totals.items()
            if key not in {"attendance_gap_total", "curriculum_gap_total"}
        }
        subjects.append(
            {
                **subject_summary,
                "average_attendance_gap": round(attendance_gap_total / count, 2),
                "average_curriculum_gap": round(curriculum_gap_total / count, 2),
            }
        )
    departments = []
    for totals in department_totals.values():
        count = totals["student_subject_analyses"]
        departments.append(
            {
                **{
                    key: value
                    for key, value in totals.items()
                    if key not in {"attendance_gap_total", "curriculum_gap_total"}
                },
                "average_attendance_gap": round(totals["attendance_gap_total"] / count, 2),
                "average_curriculum_gap": round(totals["curriculum_gap_total"] / count, 2),
            }
        )
    attention.sort(
        key=lambda item: (
            {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[item["risk_level"]],
            -item["pending_assignments"],
            item["student_name"].casefold(),
        )
    )
    return {
        "students_analyzed": len(students),
        "subject_student_analyses": analyzed,
        "truncated": truncated,
        "risk_distribution": risk_distribution,
        "departments": sorted(
            departments, key=lambda item: item["department_name"].casefold()
        ),
        "subjects": sorted(subjects, key=lambda item: item["subject_name"].casefold()),
        "students_requiring_attention": attention[:100],
    }
