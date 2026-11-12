from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, select

from app.core.database import get_db
from app.api.deps import require_roles, get_current_active_user
from app.models.user import User
from app.models.enums import UserRole, SessionStatus
from app.models.academic import Division
from app.models.assignments import TeacherAssignment
from app.models.attendance import AttendanceSession
from app.models.timetable import Timetable
from app.schemas.attendance_session import (
    AttendanceSessionCreate,
    AttendanceSessionResponse,
    AttendanceSessionMonitorResponse,
)
from app.services import attendance_session_service

router = APIRouter(prefix="/attendance-sessions", tags=["Attendance Session Management"])


def _authorize_session_access(current_user: User, session_obj: AttendanceSession) -> None:
    if current_user.role == UserRole.STUDENT:
        student = current_user.student_profile
        if not student or student.division_id != session_obj.division_id or (
            session_obj.batch_id is not None and student.batch_id != session_obj.batch_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only access sessions for their assigned division and batch"
            )
    elif current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile or session_obj.teacher_id != current_user.teacher_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers can only access their own attendance sessions"
            )


@router.post(
    "",
    response_model=AttendanceSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Attendance Session (Admin & Teacher)",
    description="Creates a new attendance session with ACTIVE status. Teachers can only create sessions for themselves."
)
def create_attendance_session(
    data: AttendanceSessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER))
):
    if current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile or data.teacher_id != current_user.teacher_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers can only create attendance sessions for themselves"
            )
        division = db.get(Division, data.division_id)
        if not division:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Division with ID {data.division_id} does not exist"
            )
        assignment = db.execute(
            select(TeacherAssignment.id).where(
                TeacherAssignment.teacher_id == current_user.teacher_profile.id,
                TeacherAssignment.subject_id == data.subject_id,
                TeacherAssignment.academic_class_id == division.academic_class_id,
                TeacherAssignment.academic_year_id == data.academic_year_id,
                TeacherAssignment.semester_id == data.semester_id,
                TeacherAssignment.is_active.is_(True),
                or_(
                    TeacherAssignment.division_id == data.division_id,
                    TeacherAssignment.division_id.is_(None)
                ),
                or_(
                    TeacherAssignment.batch_id == data.batch_id,
                    TeacherAssignment.batch_id.is_(None)
                )
            )
        ).first()
        timetable_entry = None
        if not assignment:
            timetable_entry = db.execute(
                select(Timetable.id).where(
                    Timetable.teacher_id == current_user.teacher_profile.id,
                    Timetable.subject_id == data.subject_id,
                    Timetable.division_id == data.division_id,
                    Timetable.academic_year_id == data.academic_year_id,
                    Timetable.semester_id == data.semester_id,
                    Timetable.is_active.is_(True),
                    or_(
                        Timetable.batch_id == data.batch_id,
                        Timetable.batch_id.is_(None)
                    )
                )
            ).first()
        if not assignment and not timetable_entry:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers can only create sessions for subjects and classes assigned to them"
            )
    return attendance_session_service.create_attendance_session(db, data)


@router.get(
    "",
    response_model=List[AttendanceSessionResponse],
    status_code=status.HTTP_200_OK,
    summary="List Attendance Sessions (Authenticated Users)",
    description="Retrieves attendance sessions with optional filtering. Automatically evaluates past active sessions as EXPIRED."
)
def list_attendance_sessions(
    academic_year_id: Optional[int] = Query(None, description="Filter by Academic Year ID"),
    semester_id: Optional[int] = Query(None, description="Filter by Semester ID"),
    division_id: Optional[int] = Query(None, description="Filter by Division ID"),
    batch_id: Optional[int] = Query(None, description="Filter by Batch ID"),
    subject_id: Optional[int] = Query(None, description="Filter by Subject ID"),
    teacher_id: Optional[int] = Query(None, description="Filter by Teacher ID"),
    session_date: Optional[date] = Query(None, description="Filter by Session Date"),
    session_status: Optional[SessionStatus] = Query(None, alias="status", description="Filter by Session Status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.role == UserRole.STUDENT:
        if not current_user.student_profile:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student profile not found")
        student = current_user.student_profile
        if division_id is not None and division_id != student.division_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only view sessions for their assigned division"
            )
        division_id = student.division_id
        academic_year_id = student.academic_year_id
        semester_id = student.semester_id
    elif current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teacher profile not found")
        if teacher_id is not None and teacher_id != current_user.teacher_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers can only view their own attendance sessions"
            )
        teacher_id = current_user.teacher_profile.id

    sessions = attendance_session_service.list_attendance_sessions(
        db,
        academic_year_id=academic_year_id,
        semester_id=semester_id,
        division_id=division_id,
        batch_id=batch_id,
        subject_id=subject_id,
        teacher_id=teacher_id,
        session_date=session_date,
        session_status=session_status
    )
    if current_user.role == UserRole.STUDENT:
        student = current_user.student_profile
        return [
            AttendanceSessionResponse.model_validate(session).model_copy(
                update={"session_token": None}
            )
            for session in sessions
            if session.batch_id is None or session.batch_id == student.batch_id
        ]
    return sessions


@router.get(
    "/token/{session_token}",
    response_model=AttendanceSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Session by Unique Token (Authenticated Users)",
    description="Retrieves attendance session details using a secure session token."
)
def get_attendance_session_by_token(
    session_token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    session_obj = attendance_session_service.get_attendance_session_by_token(db, session_token)
    _authorize_session_access(current_user, session_obj)
    if current_user.role == UserRole.STUDENT:
        return AttendanceSessionResponse.model_validate(session_obj).model_copy(
            update={"session_token": None}
        )
    return session_obj


@router.get(
    "/{session_id}",
    response_model=AttendanceSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Attendance Session by ID (Authenticated Users)",
    description="Returns detailed session information for a specific session ID."
)
def get_attendance_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    session_obj = attendance_session_service.get_attendance_session(db, session_id)
    _authorize_session_access(current_user, session_obj)
    if current_user.role == UserRole.STUDENT:
        return AttendanceSessionResponse.model_validate(session_obj).model_copy(
            update={"session_token": None}
        )
    return session_obj


@router.post(
    "/{session_id}/refresh-token",
    response_model=AttendanceSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh Dynamic QR Token",
    description="Rotates the active QR token. The previous token is immediately invalidated.",
)
def refresh_attendance_session_token(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    session_obj = attendance_session_service.get_attendance_session(db, session_id)
    if current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile or session_obj.teacher_id != current_user.teacher_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers can only refresh tokens for their own sessions",
            )
    return attendance_session_service.refresh_attendance_session_token(db, session_id)


@router.get(
    "/{session_id}/monitor",
    response_model=AttendanceSessionMonitorResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Live Attendance Session Monitor",
    description="Returns enrolled students and attendance counts for a teacher's session.",
)
def get_attendance_session_monitor(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER)),
):
    return attendance_session_service.get_attendance_session_monitor(
        db, session_id, current_user
    )


@router.patch(
    "/{session_id}/close",
    response_model=AttendanceSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Close Attendance Session (Admin & Session Teacher)",
    description="Closes an ACTIVE attendance session and records `closed_at` timestamp. Teachers can only close their own sessions."
)
def close_attendance_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER))
):
    session_obj = attendance_session_service.get_attendance_session(db, session_id)
    if current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile or session_obj.teacher_id != current_user.teacher_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers can only close their own attendance sessions"
            )
    return attendance_session_service.close_attendance_session(db, session_id)


@router.patch(
    "/{session_id}/cancel",
    response_model=AttendanceSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel Attendance Session (Admin & Session Teacher)",
    description="Cancels an ACTIVE attendance session. Teachers can only cancel their own sessions."
)
def cancel_attendance_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.TEACHER))
):
    session_obj = attendance_session_service.get_attendance_session(db, session_id)
    if current_user.role == UserRole.TEACHER:
        if not current_user.teacher_profile or session_obj.teacher_id != current_user.teacher_profile.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Teachers can only cancel their own attendance sessions"
            )
    return attendance_session_service.cancel_attendance_session(db, session_id)
