"""Additive Phase 2 academic models."""

from alembic import op

from app.core.database import Base
import app.models

revision = "phase2_academic_models"
down_revision = None
branch_labels = None
depends_on = None

NEW_TABLES = (
    "curriculum_units",
    "curriculum_topics",
    "student_topic_progress",
    "assignments",
    "assignment_submissions",
    "assessments",
    "assessment_results",
    "student_activities",
    "activity_participations",
    "academic_alerts",
    "academic_risk_records",
    "ai_recommendations",
    "academic_documents",
    "academic_document_chunks",
    "notifications",
    "academic_gap_snapshots",
)


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(
        bind=bind,
        tables=[Base.metadata.tables[name] for name in NEW_TABLES],
        checkfirst=True,
    )


def downgrade() -> None:
    raise RuntimeError(
        "This migration is intentionally additive; automatic downgrade would delete academic data."
    )
