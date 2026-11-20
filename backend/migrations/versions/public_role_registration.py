"""Store self-service registration names and enrollment numbers on user accounts."""

from alembic import op
import sqlalchemy as sa

revision = "public_role_registration"
down_revision = "phase5_academic_assistant"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("users")
    }
    with op.batch_alter_table("users") as batch:
        if "full_name" not in existing_columns:
            batch.add_column(sa.Column("full_name", sa.String(length=100), nullable=True))
        if "enrollment_number" not in existing_columns:
            batch.add_column(
                sa.Column("enrollment_number", sa.String(length=50), nullable=True)
            )

    indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("users")
    }
    if "ix_users_enrollment_number" not in indexes:
        op.create_index(
            "ix_users_enrollment_number",
            "users",
            ["enrollment_number"],
            unique=True,
        )


def downgrade() -> None:
    raise RuntimeError(
        "This migration is intentionally additive; downgrading would delete registered user data."
    )
