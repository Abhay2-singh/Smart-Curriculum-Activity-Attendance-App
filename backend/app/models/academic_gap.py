from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.learning import TimestampMixin


class AcademicGapSnapshot(TimestampMixin, Base):
    __tablename__ = "academic_gap_snapshots"
    __table_args__ = (Index("ix_gap_snapshot_student_detected", "student_id", "detected_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL")
    )
    attendance_gap: Mapped[float] = mapped_column(nullable=False)
    curriculum_gap: Mapped[float] = mapped_column(nullable=False)
    assignment_gap: Mapped[int] = mapped_column(Integer, nullable=False)
    performance_gap: Mapped[float] = mapped_column(nullable=False)
    indicators: Mapped[dict] = mapped_column(JSON, nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    student = relationship("Student")
    subject = relationship("Subject")
