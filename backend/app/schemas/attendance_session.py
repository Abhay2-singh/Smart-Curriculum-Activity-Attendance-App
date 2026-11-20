from datetime import date, time, datetime, timezone
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_serializer
from app.core.config import settings
from app.models.enums import SessionStatus


class AttendanceSessionCreate(BaseModel):
    academic_year_id: int = Field(..., description="Academic Year ID", example=1)
    semester_id: int = Field(..., description="Semester ID", example=1)
    division_id: int = Field(..., description="Division ID", example=1)
    batch_id: Optional[int] = Field(None, description="Optional Batch ID", example=1)
    subject_id: int = Field(..., description="Subject ID", example=1)
    teacher_id: int = Field(..., description="Teacher ID", example=1)
    timetable_id: Optional[int] = Field(None, description="Optional Timetable ID", example=1)
    session_date: date = Field(..., description="Session date (YYYY-MM-DD)", example="2026-08-19")
    start_time: time = Field(..., description="Session start time (HH:MM:SS)", example="09:00:00")
    end_time: time = Field(..., description="Session end time (HH:MM:SS)", example="10:00:00")
    expires_at: datetime = Field(..., description="Session expiration datetime", example="2026-08-19T10:15:00Z")


class AttendanceSessionResponse(BaseModel):
    id: int
    session_token: Optional[str] = None
    academic_year_id: int
    semester_id: int
    division_id: int
    batch_id: Optional[int] = None
    subject_id: int
    subject_name: Optional[str] = None
    teacher_id: int
    timetable_id: Optional[int] = None
    session_date: date
    start_time: time
    end_time: time
    expires_at: datetime
    qr_token_expires_at: Optional[datetime] = None
    qr_token_ttl_seconds: int = Field(
        default_factory=lambda: settings.ATTENDANCE_QR_TOKEN_TTL_SECONDS
    )
    qr_refresh_interval_seconds: int = Field(
        default_factory=lambda: settings.ATTENDANCE_QR_REFRESH_INTERVAL_SECONDS
    )
    status: SessionStatus
    created_at: datetime
    closed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("expires_at", "qr_token_expires_at", "created_at", "closed_at")
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()


class AttendanceMonitorStudent(BaseModel):
    student_id: int
    roll_number: str
    full_name: str
    status: str
    marked_at: Optional[datetime] = None


class AttendanceSessionMonitorResponse(BaseModel):
    session_id: int
    total_enrolled: int
    present_count: int
    absent_count: int
    not_marked_count: int
    attendance_percentage: float
    students: list[AttendanceMonitorStudent]
