import ast
import os
from pathlib import Path

os.environ["ENVIRONMENT"] = "test"
os.environ["RUN_DB_SETUP"] = "false"

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main
from exam_evaluation import should_short_circuit_answer


@pytest.mark.parametrize(
    ("word_count", "lexical_score", "contradiction", "expected"),
    [
        (8, 0.02, False, True),
        (12, 0.62, True, True),
        (30, 0.149, False, True),
        (30, 0.15, False, False),
        (31, 0.01, True, True),
        (31, 0.62, True, False),
        (31, 0.80, False, False),
        (10, 0.80, False, False),
    ],
)
def test_concise_wrong_answers_short_circuit_heavy_model_inference(
    word_count, lexical_score, contradiction, expected
):
    assert should_short_circuit_answer(
        word_count, lexical_score, contradiction
    ) is expected


def test_alembic_revision_graph_has_unique_ids_and_one_head():
    migration_dir = Path(__file__).parents[1] / "alembic" / "versions"
    migrations = []
    for path in sorted(migration_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        values = {}
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"revision", "down_revision"}:
                        values[target.id] = ast.literal_eval(node.value)
        if "revision" in values:
            migrations.append((path.name, values["revision"], values.get("down_revision")))

    revisions = [revision for _, revision, _ in migrations]
    assert len(revisions) == len(set(revisions)), "Alembic revision identifiers must be unique"
    known = set(revisions)
    parents = set()
    for filename, revision, down_revision in migrations:
        if down_revision is None:
            continue
        parent_ids = list(down_revision) if isinstance(down_revision, tuple) else [down_revision]
        for parent in parent_ids:
            assert parent in known, f"{filename} references missing parent revision {parent}"
            parents.add(parent)

    heads = known - parents
    assert len(heads) == 1, f"Expected one Alembic head, found {sorted(heads)}"


def test_production_frontend_cors_preflight_is_allowed():
    origin = "https://frontend-plum-mu-90.vercel.app"
    response = TestClient(main.app).options(
        "/login",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == origin


def test_readiness_requires_both_postgres_and_mongodb(monkeypatch):
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def execute(self, statement):
            return None

    class HealthyEngine:
        def connect(self):
            return Connection()

    class HealthyMongo:
        def command(self, command):
            assert command == "ping"
            return {"ok": 1}

    monkeypatch.setattr(main, "engine", HealthyEngine())
    monkeypatch.setattr(main, "mongo_db", HealthyMongo())
    assert main.readiness() == {
        "status": "ready",
        "checks": {"postgres": True, "mongodb": True},
    }


def test_readiness_returns_503_when_dependencies_are_unavailable(monkeypatch):
    class BrokenEngine:
        def connect(self):
            raise RuntimeError("database unavailable")

    class BrokenMongo:
        def command(self, command):
            raise RuntimeError("mongodb unavailable")

    monkeypatch.setattr(main, "engine", BrokenEngine())
    monkeypatch.setattr(main, "mongo_db", BrokenMongo())
    with pytest.raises(HTTPException) as exc:
        main.readiness()

    assert exc.value.status_code == 503
    assert exc.value.detail == {
        "error": "DEPENDENCIES_UNAVAILABLE",
        "checks": {"postgres": False, "mongodb": False},
    }


def test_question_updates_tolerate_embedding_model_outage():
    source = Path(__file__).parents[1].joinpath("exam_evaluation.py").read_text(encoding="utf-8")
    update_endpoint = source.split('@router.put("/assignments/{assignment_id}/questions/{question_id}")', 1)[1]
    update_endpoint = update_endpoint.split('@router.post("/assignments/{assignment_id}/questions/suggest-rubric")', 1)[0]
    assert "q.reference_embedding = _optional_embedding(ref_ans)" in update_endpoint
    assert "crit_vec = _optional_embedding(c.criterion_text.strip())" in update_endpoint
