from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CurriculumUnitCreate(BaseModel):
    subject_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    order_index: int = Field(ge=1)
    expected_completion_date: Optional[datetime] = None


class CurriculumTopicCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    order_index: int = Field(ge=1)
    expected_completion_date: Optional[datetime] = None


class CurriculumProgressUpdate(BaseModel):
    status: Literal["NOT_STARTED", "IN_PROGRESS", "COMPLETED"]


class CurriculumUnitResponse(ORMModel):
    id: int
    subject_id: int
    title: str
    description: Optional[str]
    order_index: int
    expected_completion_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class CurriculumTopicResponse(ORMModel):
    id: int
    unit_id: int
    title: str
    description: Optional[str]
    order_index: int
    expected_completion_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class StudentTopicProgressResponse(ORMModel):
    id: int
    student_id: int
    topic_id: int
    status: str
    completed_at: Optional[datetime]
    updated_by: int
    created_at: datetime
    updated_at: datetime


class SyllabusProgressResponse(BaseModel):
    subject_id: int
    subject_name: str
    total_topics: int
    completed_topics: int
    expected_progress_percentage: float
    actual_progress_percentage: float
    curriculum_gap_percentage: float


class AssignmentCreate(BaseModel):
    subject_id: int = Field(gt=0)
    division_id: Optional[int] = Field(default=None, gt=0)
    teacher_id: Optional[int] = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    due_at: datetime
    max_marks: Decimal = Field(gt=0, max_digits=8, decimal_places=2)


class AssignmentUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    max_marks: Optional[Decimal] = Field(default=None, gt=0, max_digits=8, decimal_places=2)
    is_active: Optional[bool] = None


class AssignmentResponse(ORMModel):
    id: int
    subject_id: int
    teacher_id: int
    division_id: Optional[int]
    title: str
    description: Optional[str]
    due_at: datetime
    max_marks: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SubmissionCreate(BaseModel):
    content: str = Field(min_length=1, max_length=100000)


class SubmissionEvaluation(BaseModel):
    score: Decimal = Field(ge=0, max_digits=8, decimal_places=2)
    feedback: Optional[str] = Field(default=None, max_length=10000)


class SubmissionResponse(ORMModel):
    id: int
    assignment_id: int
    student_id: int
    content: str
    submitted_at: datetime
    score: Optional[Decimal]
    feedback: Optional[str]
    evaluated_by: Optional[int]
    evaluated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class AssessmentCreate(BaseModel):
    subject_id: int = Field(gt=0)
    division_id: Optional[int] = Field(default=None, gt=0)
    teacher_id: Optional[int] = Field(default=None, gt=0)
    title: str = Field(min_length=1, max_length=200)
    assessment_type: str = Field(min_length=1, max_length=50)
    scheduled_at: datetime
    max_marks: Decimal = Field(gt=0, max_digits=8, decimal_places=2)


class AssessmentResultCreate(BaseModel):
    student_id: int = Field(gt=0)
    marks: Decimal = Field(ge=0, max_digits=8, decimal_places=2)
    feedback: Optional[str] = Field(default=None, max_length=10000)


class AssessmentMarksUpdate(BaseModel):
    marks: Decimal = Field(ge=0, max_digits=8, decimal_places=2)
    feedback: Optional[str] = Field(default=None, max_length=10000)


class AssessmentResponse(ORMModel):
    id: int
    subject_id: int
    teacher_id: int
    division_id: Optional[int]
    title: str
    assessment_type: str
    scheduled_at: datetime
    max_marks: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AssessmentResultResponse(ORMModel):
    id: int
    assessment_id: int
    student_id: int
    marks: Decimal
    feedback: Optional[str]
    recorded_by: int
    created_at: datetime
    updated_at: datetime


class StudentActivityCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    activity_type: Literal["ACADEMIC", "EXTRACURRICULAR"]
    activity_date: datetime
    subject_id: Optional[int] = Field(default=None, gt=0)


class ActivityParticipationCreate(BaseModel):
    student_id: int = Field(gt=0)
    participated: bool = True
    achievement: Optional[str] = Field(default=None, max_length=200)
    points: int = Field(default=0, ge=0)


class StudentActivityResponse(ORMModel):
    id: int
    title: str
    description: Optional[str]
    activity_type: str
    activity_date: datetime
    subject_id: Optional[int]
    created_by: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ActivityParticipationResponse(ORMModel):
    id: int
    activity_id: int
    student_id: int
    participated: bool
    achievement: Optional[str]
    points: int
    created_at: datetime
    updated_at: datetime


class AcademicGapResponse(BaseModel):
    student_id: int
    subject_id: Optional[int]
    attendance_percentage: Optional[float]
    attendance_sessions_count: int = 0
    required_attendance_percentage: float
    attendance_gap: float
    expected_syllabus_progress_percentage: float
    actual_syllabus_progress_percentage: float
    curriculum_gap: float
    pending_assignments: int
    performance_percentage: Optional[float]
    performance_gap: float
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    risk_reasons: list[str]
    detected_at: datetime


class RiskReportResponse(BaseModel):
    student_id: int
    subject_id: Optional[int]
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    risk_reasons: list[str]
    indicators: dict
    detected_at: datetime


class AcademicAlertResponse(ORMModel):
    id: int
    student_id: int
    subject_id: Optional[int]
    category: str
    severity: str
    title: str
    details: Optional[str]
    status: str
    detected_at: datetime
    created_at: datetime
    updated_at: datetime


class AcademicDocumentResponse(ORMModel):
    id: int
    subject_id: Optional[int]
    department_id: Optional[int]
    academic_class_id: Optional[int]
    academic_year_id: Optional[int]
    semester_id: Optional[int]
    uploaded_by: int
    filename: str
    content_type: str
    sha256: str
    is_active: bool
    processing_status: Literal["READY"] = "READY"
    created_at: datetime
    updated_at: datetime


class AssistantQuery(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    subject_id: Optional[int] = Field(default=None, gt=0)

    @field_validator("question")
    @classmethod
    def strip_question(cls, value: str) -> str:
        question = value.strip()
        if len(question) < 3:
            raise ValueError("question must contain at least three non-space characters")
        return question


class AssistantMessageResponse(ORMModel):
    id: int
    subject_id: Optional[int]
    role: Literal["user", "assistant"]
    content: str
    citations: list[dict]
    created_at: datetime


class NextBestActionResponse(BaseModel):
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    action: str
    rationale: str
    subject_id: Optional[int]
    subject_name: Optional[str]
    indicator: str
    value: float | int
    target: Optional[float] = None


class AssistantCitation(BaseModel):
    document_id: int
    filename: str
    chunk_id: int
    text: str
    score: float


class AssistantResponse(BaseModel):
    answer: str
    citations: list[AssistantCitation]
    academic_context: Optional[dict] = None


class NotificationResponse(ORMModel):
    id: int
    recipient_user_id: int
    title: str
    message: str
    category: str
    read_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
