from alembic import op
import sqlalchemy as sa

revision = "0005_reviewable_marks"
down_revision = "0004_submission_timestamp"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("submissions")}
    if "marks_published" not in columns:
        op.add_column("submissions", sa.Column("marks_published", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "teacher_review_note" not in columns:
        op.add_column("submissions", sa.Column("teacher_review_note", sa.String(), nullable=True))
    if "graded_by" not in columns:
        op.add_column("submissions", sa.Column("graded_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    if "graded_at" not in columns:
        op.add_column("submissions", sa.Column("graded_at", sa.DateTime(), nullable=True))

    op.alter_column(
        "submissions",
        "marks",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using="marks::double precision",
    )

    bind = op.get_bind()
    bind.execute(sa.text("""
        UPDATE submissions
        SET marks_published = TRUE
        WHERE marks IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM student_question_answers
              WHERE student_question_answers.submission_id = submissions.id
                AND student_question_answers.review_status NOT IN ('reviewed', 'published')
          )
    """))
    op.alter_column("submissions", "marks_published", server_default=None)


def downgrade():
    raise RuntimeError("Downgrade is intentionally disabled to prevent destructive LMS data loss.")
