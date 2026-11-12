"""Add document scope metadata and private assistant history."""

from alembic import op
import sqlalchemy as sa

revision = "phase5_academic_assistant"
down_revision = "dynamic_qr_tokens"
branch_labels = None
depends_on = None


DOCUMENT_COLUMNS = (
    ("department_id", sa.Integer(), "departments", "id"),
    ("academic_class_id", sa.Integer(), "academic_classes", "id"),
    ("academic_year_id", sa.Integer(), "academic_years", "id"),
    ("semester_id", sa.Integer(), "semesters", "id"),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "academic_documents" in inspector.get_table_names():
        existing_columns = {
            column["name"] for column in inspector.get_columns("academic_documents")
        }
        existing_foreign_keys = {
            tuple(foreign_key.get("constrained_columns") or [])
            for foreign_key in inspector.get_foreign_keys("academic_documents")
        }
        with op.batch_alter_table("academic_documents") as batch:
            for column_name, column_type, target_table, target_column in DOCUMENT_COLUMNS:
                if column_name not in existing_columns:
                    batch.add_column(sa.Column(column_name, column_type, nullable=True))
                if (column_name,) not in existing_foreign_keys:
                    batch.create_foreign_key(
                        f"fk_academic_documents_{column_name}",
                        target_table,
                        [column_name],
                        [target_column],
                        ondelete="SET NULL",
                    )

        op.execute(
            "UPDATE academic_documents "
            "SET department_id = (SELECT department_id FROM subjects "
            "WHERE subjects.id = academic_documents.subject_id) "
            "WHERE subject_id IS NOT NULL AND department_id IS NULL"
        )
        op.execute(
            "UPDATE academic_documents "
            "SET semester_id = (SELECT semester_id FROM subjects "
            "WHERE subjects.id = academic_documents.subject_id) "
            "WHERE subject_id IS NOT NULL AND semester_id IS NULL"
        )
        op.execute(
            "UPDATE academic_documents "
            "SET academic_year_id = (SELECT semesters.academic_year_id FROM semesters "
            "JOIN subjects ON subjects.semester_id = semesters.id "
            "WHERE subjects.id = academic_documents.subject_id) "
            "WHERE subject_id IS NOT NULL AND academic_year_id IS NULL"
        )

    from app.core.database import Base
    import app.models

    Base.metadata.create_all(
        bind=bind,
        tables=[Base.metadata.tables["academic_assistant_messages"]],
        checkfirst=True,
    )


def downgrade() -> None:
    raise RuntimeError(
        "This migration is intentionally additive; automatic downgrade would delete assistant history."
    )
