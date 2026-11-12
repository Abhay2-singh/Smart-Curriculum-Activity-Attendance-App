from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError

from app.models.attendance import AttendanceSession, AttendanceRecord, AttendanceCorrection
from app.models.profiles import Student
from app.models.academic import Division
from app.models.assignments import TeacherAssignment
from app.models.assignments import ClassSubjectAssignment
from app.models.subject import Subject
from app.models.timetable import Timetable
from app.models.user import User
from app.core.config import settings
from app.models.enums import UserRole, SessionStatus, AttendanceStatus, AttendanceSource
from app.schemas.attendance import (
    StudentAttendanceMarkRequest,
    ManualAttendanceMarkRequest,
    AttendanceRecordResponse,
    AttendanceCorrectionRequest,
    AttendanceCorrectionResponse,
    StudentAttendanceReport,
    SubjectAttendanceSummary,
    DefaulterStudent,
    DefaulterReportResponse
)


def _enrich_record_response(record: AttendanceRecord) -> AttendanceRecordResponse:
    res = AttendanceRecordResponse.model_validate(record)
    if record.student:
        res.student_roll_number = record.student.roll_number
        res.student_full_name = record.student.full_name
        res.student_code = record.student.student_id
        res.student_email = record.student.email
    return res


def mark_student_attendance(
    db: Session,
    current_user: User,
    data: StudentAttendanceMarkRequest
) -> AttendanceRecordResponse:
    if current_user.role != UserRole.STUDENT or not current_user.student_profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authenticated student accounts can mark attendance"
        )
    
    student = current_user.student_profile
    if not student.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive student profiles cannot mark attendance",
        )

    # Fetch session by token
    session_obj = db.execute(
        select(AttendanceSession)
        .where(AttendanceSession.session_token == data.session_token)
        .with_for_update()
    ).scalars().first()

    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid attendance session token"
        )

    # Expiry validation
    now_utc = datetime.now(timezone.utc)
    expires_at = session_obj.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    qr_expires_at = session_obj.qr_token_expires_at or session_obj.expires_at
    if qr_expires_at.tzinfo is None:
        qr_expires_at = qr_expires_at.replace(tzinfo=timezone.utc)

    if now_utc >= expires_at or session_obj.status == SessionStatus.EXPIRED:
        if session_obj.status == SessionStatus.ACTIVE:
            session_obj.status = SessionStatus.EXPIRED
            db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attendance session has expired"
        )

    if now_utc >= qr_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="QR code has expired. Ask the teacher to refresh it.",
        )

    if session_obj.status != SessionStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Attendance session is {session_obj.status.value} and does not accept attendance"
        )

    # Academic Structure Match
    if (
        student.division_id != session_obj.division_id
        or student.academic_year_id != session_obj.academic_year_id
        or student.semester_id != session_obj.semester_id
        or student.academic_class_id != session_obj.division.academic_class_id
        or student.department_id != session_obj.subject.department_id
        or session_obj.subject.semester_id != session_obj.semester_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student is not assigned to the division of this attendance session"
        )

    if session_obj.batch_id is not None and student.batch_id != session_obj.batch_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student is not assigned to the batch of this attendance session"
        )

    subject_enrollment = db.execute(
        select(ClassSubjectAssignment.id).where(
            ClassSubjectAssignment.academic_class_id == student.academic_class_id,
            ClassSubjectAssignment.subject_id == session_obj.subject_id,
            ClassSubjectAssignment.academic_year_id == session_obj.academic_year_id,
            ClassSubjectAssignment.semester_id == session_obj.semester_id,
            ClassSubjectAssignment.is_active.is_(True),
            or_(
                ClassSubjectAssignment.division_id == student.division_id,
                ClassSubjectAssignment.division_id.is_(None),
            ),
        ).limit(1)
    ).first()
    if not subject_enrollment:
        subject_enrollment = db.execute(
            select(TeacherAssignment.id).where(
                TeacherAssignment.teacher_id == session_obj.teacher_id,
                TeacherAssignment.subject_id == session_obj.subject_id,
                TeacherAssignment.academic_class_id == student.academic_class_id,
                TeacherAssignment.academic_year_id == session_obj.academic_year_id,
                TeacherAssignment.semester_id == session_obj.semester_id,
                TeacherAssignment.is_active.is_(True),
                or_(
                    TeacherAssignment.division_id == student.division_id,
                    TeacherAssignment.division_id.is_(None),
                ),
                or_(
                    TeacherAssignment.batch_id == student.batch_id,
                    TeacherAssignment.batch_id.is_(None),
                ),
            ).limit(1)
        ).first()
    if not subject_enrollment:
        subject_enrollment = db.execute(
            select(Timetable.id).where(
                Timetable.teacher_id == session_obj.teacher_id,
                Timetable.subject_id == session_obj.subject_id,
                Timetable.academic_year_id == session_obj.academic_year_id,
                Timetable.semester_id == session_obj.semester_id,
                Timetable.division_id == student.division_id,
                Timetable.is_active.is_(True),
                or_(
                    Timetable.batch_id == session_obj.batch_id,
                    Timetable.batch_id.is_(None),
                ),
            ).limit(1)
        ).first()
    if not subject_enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student is not enrolled in this subject for the selected academic period",
        )

    # Duplicate check
    existing_record = db.query(AttendanceRecord).filter(
        AttendanceRecord.attendance_session_id == session_obj.id,
        AttendanceRecord.student_id == student.id
    ).first()

    if existing_record:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance has already been marked for this session"
        )

    # Create record
    record = AttendanceRecord(
        attendance_session_id=session_obj.id,
        student_id=student.id,
        status=AttendanceStatus.PRESENT,
        marked_by=current_user.id,
        source=AttendanceSource.QR
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance has already been marked for this session"
        ) from exc
    from app.services.academic_gap_service import analyze_student

    analyze_student(
        db,
        current_user,
        student.id,
        session_obj.subject_id,
        refresh_existing_alerts=True,
    )
    db.refresh(record)

    return _enrich_record_response(record)


def manual_mark_attendance(
    db: Session,
    session_id: int,
    data: ManualAttendanceMarkRequest,
    current_user: User
) -> List[AttendanceRecordResponse]:
    session_obj = db.query(AttendanceSession).filter(AttendanceSession.id == session_id).first()
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance session not found"
        )

    if current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile or session_obj.teacher_id != current_user.teacher_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers can only mark attendance for their own sessions"
            )

    if not data.records:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one attendance record is required"
        )

    student_ids = [item.student_id for item in data.records]
    if len(set(student_ids)) != len(student_ids):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A student can appear only once in an attendance request"
        )

    students = db.query(Student).filter(Student.id.in_(student_ids)).all()
    students_by_id = {student.id: student for student in students}
    for student_id in student_ids:
        student = students_by_id.get(student_id)
        if student is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student ID {student_id} not found"
            )

        if student.division_id != session_obj.division_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Student {student.full_name} does not belong to session's division"
            )
        if session_obj.batch_id is not None and student.batch_id != session_obj.batch_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Student {student.full_name} does not belong to session's batch"
            )

    existing_records = db.query(AttendanceRecord).filter(
        AttendanceRecord.attendance_session_id == session_id,
        AttendanceRecord.student_id.in_(student_ids)
    ).all()
    records_by_student = {record.student_id: record for record in existing_records}
    result_records = []
    for item in data.records:
        record = records_by_student.get(item.student_id)

        if record:
            record.status = item.status
            record.marked_by = current_user.id
            record.source = AttendanceSource.MANUAL
        else:
            record = AttendanceRecord(
                attendance_session_id=session_id,
                student_id=item.student_id,
                status=item.status,
                marked_by=current_user.id,
                source=AttendanceSource.MANUAL
            )
            db.add(record)

        result_records.append(record)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance records changed concurrently; reload and retry"
        ) from exc

    for record in result_records:
        db.refresh(record)

    return [_enrich_record_response(record) for record in result_records]


def get_session_attendance_records(
    db: Session,
    session_id: int,
    current_user: User
) -> List[AttendanceRecordResponse]:
    session_obj = db.query(AttendanceSession).filter(AttendanceSession.id == session_id).first()
    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance session not found"
        )

    if current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile or session_obj.teacher_id != current_user.teacher_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers can only view attendance for their own sessions"
            )

    records = db.query(AttendanceRecord).options(
        joinedload(AttendanceRecord.student)
    ).filter(AttendanceRecord.attendance_session_id == session_id).all()

    return [_enrich_record_response(r) for r in records]


def correct_attendance_record(
    db: Session,
    record_id: int,
    data: AttendanceCorrectionRequest,
    current_user: User
) -> AttendanceCorrectionResponse:
    record = db.query(AttendanceRecord).options(
        joinedload(AttendanceRecord.session)
    ).filter(AttendanceRecord.id == record_id).first()

    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attendance record not found"
        )

    # Authorization Check
    if current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile or record.session.teacher_id != current_user.teacher_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers can only correct attendance for their own sessions"
            )
    elif current_user.role == UserRole.STUDENT:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Students cannot modify attendance records"
        )

    old_status = record.status

    # Create correction audit log
    correction = AttendanceCorrection(
        attendance_id=record.id,
        corrected_by=current_user.id,
        old_status=old_status,
        new_status=data.new_status,
        reason=data.reason
    )
    db.add(correction)

    # Update record
    record.status = data.new_status
    record.source = AttendanceSource.CORRECTION

    db.commit()
    db.refresh(correction)

    return AttendanceCorrectionResponse.model_validate(correction)


def get_student_attendance_summary(
    db: Session,
    student_id: int,
    current_user: User
) -> StudentAttendanceReport:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found"
        )

    # Authorization check
    if current_user.role == UserRole.STUDENT:
        if not current_user.student_profile or current_user.student_profile.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only view their own attendance records"
            )
    elif current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teacher profile not found"
            )
        assignment = db.query(TeacherAssignment.id).filter(
            TeacherAssignment.teacher_id == current_user.teacher_profile.id,
            TeacherAssignment.academic_year_id == student.academic_year_id,
            TeacherAssignment.semester_id == student.semester_id,
            TeacherAssignment.academic_class_id == student.academic_class_id,
            TeacherAssignment.is_active.is_(True),
            or_(
                TeacherAssignment.division_id == student.division_id,
                TeacherAssignment.division_id.is_(None)
            )
        ).first()
        if not assignment:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers can only view students in their assigned classes"
            )

    # Total relevant sessions for student's division
    conducted_statuses = (SessionStatus.ACTIVE, SessionStatus.CLOSED, SessionStatus.EXPIRED)
    total_sessions_query = db.query(AttendanceSession).filter(
        AttendanceSession.division_id == student.division_id,
        AttendanceSession.status.in_(conducted_statuses),
        AttendanceSession.academic_year_id == student.academic_year_id,
        AttendanceSession.semester_id == student.semester_id,
        AttendanceSession.session_date <= datetime.now(timezone.utc).date(),
        or_(
            AttendanceSession.batch_id.is_(None),
            AttendanceSession.batch_id == student.batch_id
        )
    )
    total_sessions_count = total_sessions_query.count()

    # Total attended by student
    attended_records = db.query(AttendanceRecord).join(AttendanceSession).filter(
        AttendanceRecord.student_id == student_id,
        AttendanceRecord.status == AttendanceStatus.PRESENT,
        AttendanceSession.division_id == student.division_id,
        AttendanceSession.status.in_(conducted_statuses),
        AttendanceSession.academic_year_id == student.academic_year_id,
        AttendanceSession.semester_id == student.semester_id,
        AttendanceSession.session_date <= datetime.now(timezone.utc).date(),
        or_(
            AttendanceSession.batch_id.is_(None),
            AttendanceSession.batch_id == student.batch_id
        )
    ).all()
    attended_count = len(attended_records)

    overall_pct = round((attended_count / total_sessions_count * 100.0), 2) if total_sessions_count > 0 else 0.0

    # Subject breakdown
    subjects = db.query(Subject).filter(
        Subject.semester_id == student.semester_id,
        Subject.department_id == student.department_id,
    ).all()
    subject_summaries = []
    for sub in subjects:
        sub_total = db.query(AttendanceSession).filter(
            AttendanceSession.division_id == student.division_id,
            AttendanceSession.subject_id == sub.id,
            AttendanceSession.status.in_(conducted_statuses),
            AttendanceSession.academic_year_id == student.academic_year_id,
            AttendanceSession.semester_id == student.semester_id,
            AttendanceSession.session_date <= datetime.now(timezone.utc).date(),
            or_(
                AttendanceSession.batch_id.is_(None),
                AttendanceSession.batch_id == student.batch_id
            )
        ).count()
        sub_attended = db.query(AttendanceRecord).join(AttendanceSession).filter(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.status == AttendanceStatus.PRESENT,
            AttendanceSession.subject_id == sub.id,
            AttendanceSession.division_id == student.division_id,
            AttendanceSession.status.in_(conducted_statuses),
            AttendanceSession.academic_year_id == student.academic_year_id,
            AttendanceSession.semester_id == student.semester_id,
            AttendanceSession.session_date <= datetime.now(timezone.utc).date(),
            or_(
                AttendanceSession.batch_id.is_(None),
                AttendanceSession.batch_id == student.batch_id
            )
        ).count()
        sub_pct = round((sub_attended / sub_total * 100.0), 2) if sub_total > 0 else 0.0

        subject_summaries.append(SubjectAttendanceSummary(
            subject_id=sub.id,
            subject_code=sub.code,
            subject_name=sub.name,
            total_sessions=sub_total,
            attended_sessions=sub_attended,
            percentage=sub_pct
        ))

    return StudentAttendanceReport(
        student_id=student.id,
        roll_number=student.roll_number,
        full_name=student.full_name,
        department_name=student.department.name if student.department else None,
        division_name=student.division.name if student.division else None,
        total_sessions=total_sessions_count,
        attended_sessions=attended_count,
        overall_percentage=overall_pct,
        required_attendance_percentage=settings.REQUIRED_ATTENDANCE_PERCENTAGE,
        subject_breakdown=subject_summaries
    )


def get_defaulter_report(
    db: Session,
    academic_year_id: Optional[int] = None,
    division_id: Optional[int] = None,
    threshold_percentage: float = 75.0,
    current_user: Optional[User] = None
) -> DefaulterReportResponse:
    query = db.query(Student)
    if current_user and current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teacher profile not found"
            )
        visible_division_ids = {
            row[0] for row in db.query(Division.id).join(
                TeacherAssignment,
                and_(
                    TeacherAssignment.academic_class_id == Division.academic_class_id,
                    TeacherAssignment.academic_year_id == Division.academic_year_id,
                    TeacherAssignment.semester_id == Division.semester_id,
                    or_(
                        TeacherAssignment.division_id == Division.id,
                        TeacherAssignment.division_id.is_(None)
                    )
                )
            ).filter(
                TeacherAssignment.teacher_id == current_user.teacher_profile.id,
                TeacherAssignment.is_active.is_(True)
            ).all()
        }
        if division_id is not None and division_id not in visible_division_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers can only view reports for their assigned divisions"
            )
        query = query.filter(Student.division_id.in_(visible_division_ids))
    if academic_year_id:
        query = query.filter(Student.academic_year_id == academic_year_id)
    if division_id:
        query = query.filter(Student.division_id == division_id)

    students = query.all()
    defaulters_list = []

    for st in students:
        total_sess = db.query(AttendanceSession).filter(
            AttendanceSession.division_id == st.division_id,
            AttendanceSession.status != SessionStatus.CANCELLED,
            or_(
                AttendanceSession.batch_id.is_(None),
                AttendanceSession.batch_id == st.batch_id
            )
        ).count()
        attended_sess = db.query(AttendanceRecord).join(AttendanceSession).filter(
            AttendanceRecord.student_id == st.id,
            AttendanceRecord.status == AttendanceStatus.PRESENT,
            AttendanceSession.division_id == st.division_id,
            AttendanceSession.status != SessionStatus.CANCELLED,
            or_(
                AttendanceSession.batch_id.is_(None),
                AttendanceSession.batch_id == st.batch_id
            )
        ).count()

        pct = round((attended_sess / total_sess * 100.0), 2) if total_sess > 0 else 100.0

        if pct < threshold_percentage:
            defaulters_list.append(DefaulterStudent(
                student_id=st.id,
                roll_number=st.roll_number,
                full_name=st.full_name,
                email=st.email,
                division_name=st.division.name if st.division else None,
                total_sessions=total_sess,
                attended_sessions=attended_sess,
                attendance_percentage=pct
            ))

    return DefaulterReportResponse(
        academic_year_id=academic_year_id,
        division_id=division_id,
        threshold_percentage=threshold_percentage,
        defaulters_count=len(defaulters_list),
        defaulters=defaulters_list
    )


def get_attendance_audit_logs(db: Session, current_user: User) -> List[dict]:
    query = db.query(AttendanceCorrection).options(
        joinedload(AttendanceCorrection.attendance_record).joinedload(AttendanceRecord.student),
        joinedload(AttendanceCorrection.corrector)
    )
    if current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teacher profile not found"
            )
        query = query.join(
            AttendanceCorrection.attendance_record
        ).join(AttendanceRecord.session).filter(
            AttendanceSession.teacher_id == current_user.teacher_profile.id
        )
    corrections = query.order_by(AttendanceCorrection.corrected_at.desc()).all()

    result = []
    for c in corrections:
        rec = c.attendance_record
        student_name = rec.student.full_name if rec and rec.student else "Unknown Student"
        student_roll = rec.student.roll_number if rec and rec.student else "-"
        corrector_name = c.corrector.username if c.corrector else "System"

        result.append({
            "id": c.id,
            "attendance_id": c.attendance_id,
            "student_roll_number": student_roll,
            "student_full_name": student_name,
            "corrected_by_name": corrector_name,
            "old_status": c.old_status.value if hasattr(c.old_status, 'value') else str(c.old_status),
            "new_status": c.new_status.value if hasattr(c.new_status, 'value') else str(c.new_status),
            "reason": c.reason,
            "created_at": c.corrected_at.isoformat() if c.corrected_at else None
        })
    return result


def get_student_attendance_history(db: Session, student_id: int) -> List[dict]:
    records = db.query(AttendanceRecord).options(
        joinedload(AttendanceRecord.session).joinedload(AttendanceSession.subject)
    ).filter(
        AttendanceRecord.student_id == student_id
    ).order_by(AttendanceRecord.marked_at.desc()).all()

    result = []
    for r in records:
        sess = r.session
        subject_name = sess.subject.name if sess and sess.subject else "General Session"
        subject_code = sess.subject.code if sess and sess.subject else ""

        result.append({
            "id": r.id,
            "session_id": r.attendance_session_id,
            "subject_name": subject_name,
            "subject_code": subject_code,
            "session_date": sess.session_date.isoformat() if sess and sess.session_date else "",
            "status": r.status.value if hasattr(r.status, 'value') else str(r.status),
            "source": r.source.value if hasattr(r.source, 'value') else str(r.source),
            "marked_at": r.marked_at.isoformat() if r.marked_at else None
        })
    return result
