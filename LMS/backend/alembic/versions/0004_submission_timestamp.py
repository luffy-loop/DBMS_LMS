from alembic import op
import sqlalchemy as sa

revision = "0004_submission_timestamp"
down_revision = "0003_audit_logs"
branch_labels = None
depends_on = None

def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "created_at" not in {column["name"] for column in inspector.get_columns("submissions")}:
        op.add_column("submissions", sa.Column("created_at", sa.DateTime(), nullable=True))

def downgrade():
    raise RuntimeError("Downgrade is intentionally disabled to prevent destructive LMS data loss.")
