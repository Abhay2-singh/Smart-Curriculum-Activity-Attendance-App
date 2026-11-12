"""Add short-lived QR token expiry to attendance sessions."""

from alembic import op
import sqlalchemy as sa

revision = "dynamic_qr_tokens"
down_revision = "phase2_academic_models"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing_columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("attendance_sessions")
    }
    if "qr_token_expires_at" not in existing_columns:
        op.add_column(
            "attendance_sessions",
            sa.Column("qr_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        )
    op.execute(
        "UPDATE attendance_sessions "
        "SET qr_token_expires_at = expires_at "
        "WHERE qr_token_expires_at IS NULL"
    )


def downgrade() -> None:
    existing_columns = {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("attendance_sessions")
    }
    if "qr_token_expires_at" in existing_columns:
        op.drop_column("attendance_sessions", "qr_token_expires_at")
