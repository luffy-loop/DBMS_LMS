from alembic import op
import sqlalchemy as sa

revision = "0002_ai_jobs_notifications"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("notifications")}
    if "entity_type" not in columns:
        op.add_column("notifications", sa.Column("entity_type", sa.String(length=40), nullable=True))
    if "entity_id" not in columns:
        op.add_column("notifications", sa.Column("entity_id", sa.String(length=100), nullable=True))
    op.create_index("ix_notifications_user_entity", "notifications", ["user_id", "entity_type", "entity_id"], if_not_exists=True)

    tables = set(inspector.get_table_names())
    if "ai_jobs" not in tables:
        op.create_table(
            "ai_jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("job_id", sa.String(length=36), nullable=False, unique=True),
            sa.Column("job_type", sa.String(length=40), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=True),
            sa.Column("payload", sa.String(), nullable=False, server_default="{}"),
            sa.Column("result", sa.String(), nullable=True),
            sa.Column("error", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_ai_jobs_job_id", "ai_jobs", ["job_id"], unique=True)
        op.create_index("ix_ai_jobs_job_type", "ai_jobs", ["job_type"])
        op.create_index("ix_ai_jobs_status", "ai_jobs", ["status"])
        op.create_index("ix_ai_jobs_user_id", "ai_jobs", ["user_id"])
        op.create_index("ix_ai_jobs_course_id", "ai_jobs", ["course_id"])
        op.create_index("ix_ai_jobs_assignment_id", "ai_jobs", ["assignment_id"])


def downgrade():
    raise RuntimeError("Downgrade is intentionally disabled to prevent destructive LMS data loss.")
