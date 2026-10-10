from alembic import op
import sqlalchemy as sa

revision = "0004_assignment_max_marks"
down_revision = "0003_audit_logs"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("assignments")}
    if "max_marks" not in columns:
        op.add_column("assignments", sa.Column("max_marks", sa.Integer(), nullable=False, server_default="10"))
    op.alter_column("assignments", "max_marks", server_default=None)

def downgrade():
    raise RuntimeError("Downgrade is intentionally disabled to prevent destructive LMS data loss.")
