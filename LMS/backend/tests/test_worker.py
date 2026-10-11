import json
import os
os.environ["ENVIRONMENT"] = "test"
os.environ["RUN_DB_SETUP"] = "false"
os.environ["ENABLE_RESOURCE_VECTOR_SEARCH"] = "false"

from datetime import datetime, timedelta
from types import SimpleNamespace

import worker


class FakeQuery:
    def __init__(self, rows): self.rows = rows
    def filter(self, *args, **kwargs): return self
    def order_by(self, *args, **kwargs): return self
    def limit(self, count): return self
    def all(self): return self.rows
    def with_for_update(self, **kwargs): return self
    def first(self): return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self, rows): self.rows = rows; self.commits = 0; self.rollbacks = 0
    def query(self, model): return FakeQuery(self.rows)
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1
    def close(self): pass


def test_stale_quiz_job_is_requeued_with_attempt_count(monkeypatch):
    job = SimpleNamespace(job_type="quiz", status="RETRIEVING", updated_at=datetime.utcnow()-timedelta(hours=1), payload="{}", error=None)
    session = FakeSession([job])
    monkeypatch.setattr(worker, "SessionLocal", lambda: session)
    assert worker._recover_stale_ai_jobs() == 1
    assert job.status == "QUEUED"
    assert json.loads(job.payload)["_worker_attempts"] == 1
    assert session.commits == 1


def test_stale_quiz_job_fails_after_retry_limit(monkeypatch):
    job = SimpleNamespace(job_type="quiz", status="GENERATING", updated_at=datetime.utcnow()-timedelta(hours=1), payload=json.dumps({"_worker_attempts": worker.MAX_ATTEMPTS}), error=None)
    session = FakeSession([job])
    monkeypatch.setattr(worker, "SessionLocal", lambda: session)
    assert worker._recover_stale_ai_jobs() == 1
    assert job.status == "FAILED"
    assert json.loads(job.error)["error"] == "WORKER_RETRY_LIMIT"


def test_run_once_dispatches_persisted_material_and_quiz_jobs(monkeypatch):
    calls = []
    async def process_material(value):
        calls.append(("material", value))
    monkeypatch.setattr(worker, "_recover_stale_ai_jobs", lambda: 0)
    monkeypatch.setattr(worker, "_next_material_id", lambda: "material-1")
    monkeypatch.setattr(worker, "_process_and_notify", process_material)
    monkeypatch.setattr(worker, "_claim_quiz_job", lambda: 42)
    monkeypatch.setattr(worker, "run_quiz_job", lambda value: calls.append(("quiz", value)))
    assert worker.run_once() is True
    assert calls == [("material", "material-1"), ("quiz", 42)]
