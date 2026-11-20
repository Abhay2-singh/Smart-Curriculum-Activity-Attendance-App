import secrets
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from app.models.attendance import AttendanceRecord, AttendanceSession
from app.models.academic import AcademicYear, Semester, Division, Batch
from app.core.config import settings
from app.models.subject import Subject
from app.models.assignments import TeacherAssignment, ClassSubjectAssignment
from app.models.profiles import Student, Teacher
from app.models.timetable import Timetable
from app.models.enums import AttendanceStatus, SessionStatus, UserRole
from app.models.user import User
from app.schemas.attendance_session import AttendanceSessionCreate


def _get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _evaluate_expired_sessions(db: Session) -> None:
    now_utc = _get_utc_now()
    active_sessions = db.execute(
        select(AttendanceSession).where(AttendanceSession.status == SessionStatus.ACTIVE)
    ).scalars().all()

    modified = False
    for session in active_sessions:
        exp = session.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp <= now_utc:
            session.status = SessionStatus.EXPIRED
            modified = True

    if modified:
        db.commit()


def create_attendance_session(db: Session, data: AttendanceSessionCreate) -> AttendanceSession:
    _evaluate_expired_sessions(db)

    if data.start_time >= data.end_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time must be strictly before end_time"
        )

    now_utc = _get_utc_now()
    exp_dt = data.expires_at
    if exp_dt.tzinfo is None:
        exp_dt = exp_dt.replace(tzinfo=timezone.utc)

    if exp_dt <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="expires_at must be a future timestamp"
        )

    # Validate foreign keys
    academic_year = db.get(AcademicYear, data.academic_year_id)
    if not academic_year:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Academic year with ID {data.academic_year_id} does not exist"
        )
    semester = db.get(Semester, data.semester_id)
    if not semester:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Semester with ID {data.semester_id} does not exist"
        )
    division = db.get(Division, data.division_id)
    if not division:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Division with ID {data.division_id} does not exist"
        )
    batch = db.get(Batch, data.batch_id) if data.batch_id is not None else None
    if data.batch_id is not None and not batch:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch with ID {data.batch_id} does not exist"
        )
    subject = db.get(Subject, data.subject_id)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Subject with ID {data.subject_id} does not exist"
        )
    if not db.get(Teacher, data.teacher_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Teacher with ID {data.teacher_id} does not exist"
        )

    # Harmonize division, semester, and academic year if division specifies them
    if division.semester_id and division.semester_id != semester.id:
        sem_override = db.get(Semester, division.semester_id)
        if sem_override:
            semester = sem_override
            data.semester_id = semester.id
    if division.academic_year_id and division.academic_year_id != academic_year.id:
        ay_override = db.get(AcademicYear, division.academic_year_id)
        if ay_override:
            academic_year = ay_override
            data.academic_year_id = academic_year.id

    if batch is not None and batch.division_id != division.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch does not belong to the selected division"
        )
    if subject.semester_id != semester.id:
        # Check if subject is assigned to this semester/division via TeacherAssignment or ClassSubjectAssignment
        is_assigned = db.query(TeacherAssignment).filter(
            TeacherAssignment.subject_id == subject.id,
            TeacherAssignment.semester_id == semester.id,
        ).first() or db.query(ClassSubjectAssignment).filter(
            ClassSubjectAssignment.subject_id == subject.id,
            ClassSubjectAssignment.semester_id == semester.id,
        ).first()
        if not is_assigned:
            # Auto-assign so teacher can conduct the session smoothly
            auto_ta = TeacherAssignment(
                teacher_id=data.teacher_id,
                subject_id=subject.id,
                academic_class_id=division.academic_class_id,
                academic_year_id=academic_year.id,
                semester_id=semester.id,
                division_id=division.id,
                batch_id=batch.id if batch else None,
                is_active=True,
            )
            db.add(auto_ta)
            db.flush()
    if data.timetable_id is not None and not db.get(Timetable, data.timetable_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Timetable entry with ID {data.timetable_id} does not exist"
        )

    # Prevent duplicate active session conflict
    batch_cond = (
        AttendanceSession.batch_id == data.batch_id
        if data.batch_id is not None
        else AttendanceSession.batch_id.is_(None)
    )
    existing_active = db.execute(
        select(AttendanceSession).where(
            and_(
                AttendanceSession.division_id == data.division_id,
                batch_cond,
                AttendanceSession.subject_id == data.subject_id,
                AttendanceSession.teacher_id == data.teacher_id,
                AttendanceSession.session_date == data.session_date,
                AttendanceSession.status == SessionStatus.ACTIVE
            )
        )
    ).scalars().first()

    if existing_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An active attendance session already exists for this division, subject, teacher, and date"
        )

    token = secrets.token_urlsafe(32)
    session_expiry = exp_dt
    token_expiry = min(
        now_utc + timedelta(seconds=settings.ATTENDANCE_QR_TOKEN_TTL_SECONDS),
        session_expiry,
    )

    session_obj = AttendanceSession(
        session_token=token,
        academic_year_id=data.academic_year_id,
        semester_id=data.semester_id,
        division_id=data.division_id,
        batch_id=data.batch_id,
        subject_id=data.subject_id,
        teacher_id=data.teacher_id,
        timetable_id=data.timetable_id,
        session_date=data.session_date,
        start_time=data.start_time,
        end_time=data.end_time,
        expires_at=data.expires_at,
        qr_token_expires_at=token_expiry,
        status=SessionStatus.ACTIVE
    )
    db.add(session_obj)
    db.commit()
    db.refresh(session_obj)
    return session_obj


# Grace period cache for rotated dynamic QR tokens: token -> (session_id, valid_until_utc)
_RECENTLY_ROTATED_TOKENS: dict[str, tuple[int, datetime]] = {}


def _cleanup_rotated_tokens(now_utc: datetime) -> None:
    expired_keys = [k for k, (_, exp) in _RECENTLY_ROTATED_TOKENS.items() if exp <= now_utc]
    for k in expired_keys:
        _RECENTLY_ROTATED_TOKENS.pop(k, None)


def refresh_attendance_session_token(db: Session, session_id: int) -> AttendanceSession:
    now_utc = _get_utc_now()
    _cleanup_rotated_tokens(now_utc)
    session_obj = db.execute(
        select(AttendanceSession)
        .where(AttendanceSession.id == session_id)
        .with_for_update()
    ).scalars().first()
    if not session_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance session not found")

    session_expiry = session_obj.expires_at
    if session_expiry.tzinfo is None:
        session_expiry = session_expiry.replace(tzinfo=timezone.utc)
    if session_obj.status != SessionStatus.ACTIVE or session_expiry <= now_utc:
        if session_obj.status == SessionStatus.ACTIVE:
            session_obj.status = SessionStatus.EXPIRED
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance session is no longer active",
        )

    current_token_expiry = session_obj.qr_token_expires_at or session_expiry
    if current_token_expiry.tzinfo is None:
        current_token_expiry = current_token_expiry.replace(tzinfo=timezone.utc)
    refresh_window = max(
        settings.ATTENDANCE_QR_TOKEN_TTL_SECONDS
        - settings.ATTENDANCE_QR_REFRESH_INTERVAL_SECONDS,
        0,
    )
    # If refresh is requested too quickly after last rotation, safely return existing session without throwing 429
    if current_token_expiry - now_utc > timedelta(seconds=refresh_window + 5):
        return session_obj

    # Store old token in grace period cache (10 minutes validity)
    old_token = session_obj.session_token
    if old_token:
        _RECENTLY_ROTATED_TOKENS[old_token] = (session_obj.id, now_utc + timedelta(seconds=600))

    session_obj.session_token = secrets.token_urlsafe(32)
    session_obj.qr_token_expires_at = min(
        now_utc + timedelta(seconds=settings.ATTENDANCE_QR_TOKEN_TTL_SECONDS),
        session_expiry,
    )
    db.commit()
    db.refresh(session_obj)
    return session_obj


def list_attendance_sessions(
    db: Session,
    academic_year_id: Optional[int] = None,
    semester_id: Optional[int] = None,
    division_id: Optional[int] = None,
    batch_id: Optional[int] = None,
    subject_id: Optional[int] = None,
    teacher_id: Optional[int] = None,
    session_date: Optional[date] = None,
    session_status: Optional[SessionStatus] = None
) -> List[AttendanceSession]:
    _evaluate_expired_sessions(db)

    query = select(AttendanceSession)
    if academic_year_id is not None:
        query = query.where(AttendanceSession.academic_year_id == academic_year_id)
    if semester_id is not None:
        query = query.where(AttendanceSession.semester_id == semester_id)
    if division_id is not None:
        query = query.where(AttendanceSession.division_id == division_id)
    if batch_id is not None:
        query = query.where(AttendanceSession.batch_id == batch_id)
    if subject_id is not None:
        query = query.where(AttendanceSession.subject_id == subject_id)
    if teacher_id is not None:
        query = query.where(AttendanceSession.teacher_id == teacher_id)
    if session_date is not None:
        query = query.where(AttendanceSession.session_date == session_date)
    if session_status is not None:
        query = query.where(AttendanceSession.status == session_status)

    return list(db.execute(query.order_by(AttendanceSession.id.desc())).scalars().all())


def get_attendance_session(db: Session, session_id: int) -> AttendanceSession:
    _evaluate_expired_sessions(db)
    session_obj = db.get(AttendanceSession, session_id)
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance session with ID {session_id} not found"
        )
    return session_obj


def get_attendance_session_by_token(db: Session, session_token: str) -> AttendanceSession:
    _evaluate_expired_sessions(db)
    session_obj = db.execute(
        select(AttendanceSession).where(AttendanceSession.session_token == session_token)
    ).scalars().first()

    if not session_obj:
        now_utc = _get_utc_now()
        if session_token in _RECENTLY_ROTATED_TOKENS:
            cached_id, valid_until = _RECENTLY_ROTATED_TOKENS[session_token]
            if now_utc <= valid_until:
                session_obj = db.get(AttendanceSession, cached_id)

    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance session token '{session_token}' not found"
        )
    return session_obj


def close_attendance_session(db: Session, session_id: int) -> AttendanceSession:
    _evaluate_expired_sessions(db)
    session_obj = get_attendance_session(db, session_id)

    if session_obj.status != SessionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot close session with status {session_obj.status.value}"
        )

    session_obj.status = SessionStatus.CLOSED
    session_obj.closed_at = _get_utc_now()
    db.commit()
    db.refresh(session_obj)
    return session_obj


def cancel_attendance_session(db: Session, session_id: int) -> AttendanceSession:
    _evaluate_expired_sessions(db)
    session_obj = get_attendance_session(db, session_id)

    if session_obj.status != SessionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel session with status {session_obj.status.value}"
        )

    session_obj.status = SessionStatus.CANCELLED
    db.commit()
    db.refresh(session_obj)
    return session_obj


def get_attendance_session_monitor(
    db: Session, session_id: int, current_user: User
) -> dict:
    session_obj = get_attendance_session(db, session_id)
    if current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile or session_obj.teacher_id != current_user.teacher_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers can only monitor their own attendance sessions",
            )

    roster_query = select(Student).where(
        Student.division_id == session_obj.division_id,
        Student.academic_year_id == session_obj.academic_year_id,
        Student.semester_id == session_obj.semester_id,
        Student.academic_class_id == session_obj.division.academic_class_id,
        Student.is_active.is_(True),
    )
    if session_obj.batch_id is not None:
        roster_query = roster_query.where(Student.batch_id == session_obj.batch_id)
    roster = list(db.execute(roster_query.order_by(Student.roll_number)).scalars())

    records = list(
        db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.attendance_session_id == session_obj.id
            )
        ).scalars()
    )
    records_by_student = {record.student_id: record for record in records}
    roster_ids = {student.id for student in roster}
    records_by_student = {
        student_id: record
        for student_id, record in records_by_student.items()
        if student_id in roster_ids
    }
    present_count = sum(
        record.status == AttendanceStatus.PRESENT for record in records
    )
    closed = session_obj.status in (SessionStatus.CLOSED, SessionStatus.EXPIRED)
    students = []
    for student in roster:
        record = records_by_student.get(student.id)
        student_status = (
            record.status.value
            if record
            else "ABSENT" if closed else "NOT_MARKED"
        )
        students.append(
            {
                "student_id": student.id,
                "roll_number": student.roll_number,
                "full_name": student.full_name,
                "status": student_status,
                "marked_at": record.marked_at if record else None,
            }
        )

    total_enrolled = len(roster)
    absent_count = sum(student["status"] == "ABSENT" for student in students)
    not_marked_count = sum(
        student["status"] == "NOT_MARKED" for student in students
    )
    return {
        "session_id": session_obj.id,
        "total_enrolled": total_enrolled,
        "present_count": present_count,
        "absent_count": absent_count,
        "not_marked_count": not_marked_count,
        "attendance_percentage": round(present_count * 100 / total_enrolled, 2)
        if total_enrolled
        else 0.0,
        "students": students,
    }
