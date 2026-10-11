"""Regression checks for a single, unambiguous Alembic migration history.

These checks are safe to run without production credentials or a live database.
They do not replace upgrade tests against disposable PostgreSQL databases.
"""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


BACKEND_DIR = Path(__file__).resolve().parents[1]


def _script_directory():
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    return ScriptDirectory.from_config(config)


def test_migration_history_has_one_head_and_unique_revision_ids():
    scripts = _script_directory()
    revisions = list(scripts.walk_revisions())

    revision_ids = [revision.revision for revision in revisions]
    assert revision_ids, "Alembic migration history must not be empty"
    assert len(revision_ids) == len(set(revision_ids)), "Duplicate Alembic revision identifiers found"
    assert len(scripts.get_heads()) == 1, f"Expected one migration head, found {scripts.get_heads()}"


def test_reviewable_marks_and_assignment_max_marks_follow_submission_timestamp():
    scripts = _script_directory()
    revisions = {revision.revision: revision for revision in scripts.walk_revisions()}

    assert "0004_submission_timestamp" in revisions
    assert "0005_reviewable_marks" in revisions
    assert "0006_assignment_max_marks" in revisions
    assert revisions["0005_reviewable_marks"].down_revision == "0004_submission_timestamp"
    assert revisions["0006_assignment_max_marks"].down_revision == "0005_reviewable_marks"
