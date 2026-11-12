from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class CurriculumUnit(TimestampMixin, Base):
    __tablename__ = "curriculum_units"
    __table_args__ = (
        UniqueConstraint("subject_id", "order_index", name="uq_curriculum_unit_order"),
        CheckConstraint("order_index >= 1", name="ck_curriculum_unit_order"),
        Index("ix_curriculum_units_subject", "subject_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_completion_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    subject = relationship("Subject")
    topics: Mapped[list["CurriculumTopic"]] = relationship(
        back_populates="unit", cascade="all, delete-orphan"
    )


class CurriculumTopic(TimestampMixin, Base):
    __tablename__ = "curriculum_topics"
    __table_args__ = (
        UniqueConstraint("unit_id", "order_index", name="uq_curriculum_topic_order"),
        CheckConstraint("order_index >= 1", name="ck_curriculum_topic_order"),
        Index("ix_curriculum_topics_unit", "unit_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    unit_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum_units.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_completion_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    unit: Mapped[CurriculumUnit] = relationship(back_populates="topics")
    progress: Mapped[list["StudentTopicProgress"]] = relationship(
        back_populates="topic", cascade="all, delete-orphan"
    )


class StudentTopicProgress(TimestampMixin, Base):
    __tablename__ = "student_topic_progress"
    __table_args__ = (
        UniqueConstraint("student_id", "topic_id", name="uq_student_topic_progress"),
        CheckConstraint(
            "status IN ('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED')",
            name="ck_topic_progress_status",
        ),
        Index("ix_topic_progress_student", "student_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum_topics.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="NOT_STARTED", nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    student = relationship("Student")
    topic: Mapped[CurriculumTopic] = relationship(back_populates="progress")


class Assignment(TimestampMixin, Base):
    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint("max_marks > 0", name="ck_assignment_max_marks"),
        Index("ix_assignments_subject_due", "subject_id", "due_at"),
        Index("ix_assignments_division", "division_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False
    )
    division_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("divisions.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_marks: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    subject = relationship("Subject")
    teacher = relationship("Teacher")
    division = relationship("Division")
    submissions: Mapped[list["AssignmentSubmission"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan"
    )


class AssignmentSubmission(TimestampMixin, Base):
    __tablename__ = "assignment_submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "student_id", name="uq_assignment_student_submission"),
        CheckConstraint("score IS NULL OR score >= 0", name="ck_submission_score_nonnegative"),
        Index("ix_submissions_student", "student_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2))
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    evaluated_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    assignment: Mapped[Assignment] = relationship(back_populates="submissions")
    student = relationship("Student")


class Assessment(TimestampMixin, Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint("max_marks > 0", name="ck_assessment_max_marks"),
        Index("ix_assessments_subject_date", "subject_id", "scheduled_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False
    )
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("teachers.id", ondelete="RESTRICT"), nullable=False
    )
    division_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("divisions.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_marks: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    subject = relationship("Subject")
    teacher = relationship("Teacher")
    division = relationship("Division")
    results: Mapped[list["AssessmentResult"]] = relationship(
        back_populates="assessment", cascade="all, delete-orphan"
    )


class AssessmentResult(TimestampMixin, Base):
    __tablename__ = "assessment_results"
    __table_args__ = (
        UniqueConstraint("assessment_id", "student_id", name="uq_assessment_student_result"),
        CheckConstraint("marks >= 0", name="ck_assessment_marks_nonnegative"),
        Index("ix_assessment_results_student", "student_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    marks: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    feedback: Mapped[Optional[str]] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    assessment: Mapped[Assessment] = relationship(back_populates="results")
    student = relationship("Student")


class StudentActivity(TimestampMixin, Base):
    __tablename__ = "student_activities"
    __table_args__ = (
        CheckConstraint(
            "activity_type IN ('ACADEMIC', 'EXTRACURRICULAR')",
            name="ck_student_activity_type",
        ),
        Index("ix_student_activities_date", "activity_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    activity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    activity_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    subject_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL")
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    subject = relationship("Subject")
    participations: Mapped[list["ActivityParticipation"]] = relationship(
        back_populates="activity", cascade="all, delete-orphan"
    )


class ActivityParticipation(TimestampMixin, Base):
    __tablename__ = "activity_participations"
    __table_args__ = (
        UniqueConstraint("activity_id", "student_id", name="uq_activity_student"),
        CheckConstraint("points >= 0", name="ck_activity_points_nonnegative"),
        Index("ix_activity_participation_student", "student_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("student_activities.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    participated: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    achievement: Mapped[Optional[str]] = mapped_column(String(200))
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    activity: Mapped[StudentActivity] = relationship(back_populates="participations")
    student = relationship("Student")


class AcademicAlert(TimestampMixin, Base):
    __tablename__ = "academic_alerts"
    __table_args__ = (
        CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_academic_alert_severity"
        ),
        Index("ix_academic_alert_student_status", "student_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL")
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student = relationship("Student")
    subject = relationship("Subject")


class AcademicRiskRecord(TimestampMixin, Base):
    __tablename__ = "academic_risk_records"
    __table_args__ = (
        CheckConstraint("risk_level IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_academic_risk_level"),
        Index("ix_academic_risk_student_subject", "student_id", "subject_id", "detected_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL")
    )
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    risk_reasons: Mapped[list] = mapped_column(JSON, nullable=False)
    indicators: Mapped[dict] = mapped_column(JSON, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student = relationship("Student")
    subject = relationship("Subject")


class AIRecommendation(TimestampMixin, Base):
    __tablename__ = "ai_recommendations"
    __table_args__ = (
        CheckConstraint("priority IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_recommendation_priority"),
        Index("ix_recommendation_student_status", "student_id", "is_completed"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL")
    )
    risk_record_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("academic_risk_records.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(500), nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10), nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    student = relationship("Student")
    subject = relationship("Subject")
    risk_record = relationship("AcademicRiskRecord")


class AcademicDocument(TimestampMixin, Base):
    __tablename__ = "academic_documents"
    __table_args__ = (Index("ix_academic_documents_subject", "subject_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL")
    )
    department_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL")
    )
    academic_class_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("academic_classes.id", ondelete="SET NULL")
    )
    academic_year_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("academic_years.id", ondelete="SET NULL")
    )
    semester_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("semesters.id", ondelete="SET NULL")
    )
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    chunks: Mapped[list["AcademicDocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    subject = relationship("Subject")
    department = relationship("Department")
    academic_class = relationship("AcademicClass")
    academic_year = relationship("AcademicYear")
    semester = relationship("Semester")


class AcademicDocumentChunk(TimestampMixin, Base):
    __tablename__ = "academic_document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunk_index"),
        Index("ix_document_chunk_document", "document_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("academic_documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Optional[list]] = mapped_column(JSON)

    document: Mapped[AcademicDocument] = relationship(back_populates="chunks")


class AcademicAssistantMessage(Base):
    __tablename__ = "academic_assistant_messages"
    __table_args__ = (
        Index("ix_assistant_message_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL")
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User")
    subject = relationship("Subject")


class Notification(TimestampMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_recipient_read", "recipient_user_id", "read_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    recipient_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    recipient = relationship("User")
