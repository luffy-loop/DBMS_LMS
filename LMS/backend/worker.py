#!/usr/bin/env python3
"""Durable poll-based worker for MongoDB material tasks and PostgreSQL AI jobs."""
import asyncio
import json
import logging
import os
import signal
import time
from datetime import datetime, timedelta

from ai_jobs import run_quiz_job
from database import SessionLocal
from materials import _process_and_notify
from models import AIJob
from mongodb import mongo_db

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("lms.worker")
POLL_SECONDS = max(1.0, float(os.getenv("WORKER_POLL_SECONDS", "2")))
MAX_ATTEMPTS = max(1, int(os.getenv("WORKER_MAX_ATTEMPTS", "3")))
AI_JOB_STALE_SECONDS = max(60, int(os.getenv("AI_JOB_STALE_SECONDS", "300")))
_STOP = False


def _stop(*_args):
    global _STOP
    _STOP = True


def _recover_stale_ai_jobs():
    """Requeue interrupted quiz jobs and stop retrying after a bounded count."""
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(seconds=AI_JOB_STALE_SECONDS)
        stale = db.query(AIJob).filter(
            AIJob.job_type == "quiz",
            AIJob.status.in_({"RETRIEVING", "GENERATING"}),
            AIJob.updated_at < cutoff,
        ).order_by(AIJob.updated_at.asc()).limit(25).all()
        for job in stale:
            try:
                payload = json.loads(job.payload or "{}")
            except (TypeError, ValueError):
                payload = {}
            attempts = int(payload.get("_worker_attempts", 0))
            now = datetime.utcnow()
            if attempts >= MAX_ATTEMPTS:
                job.status = "FAILED"
                job.error = json.dumps({"error": "WORKER_RETRY_LIMIT", "message": "The background task failed repeatedly. Please retry from the LMS."})
            else:
                payload["_worker_attempts"] = attempts + 1
                job.payload = json.dumps(payload)
                job.status = "QUEUED"
                job.error = json.dumps({"error": "WORKER_RECOVERED", "message": "An interrupted task was requeued for processing."})
            job.updated_at = now
        if stale:
            db.commit()
        return len(stale)
    except Exception:
        db.rollback()
        logger.exception("Unable to recover stale AI jobs")
        return 0
    finally:
        db.close()


def _claim_quiz_job():
    """Atomically claim one queued quiz job."""
    db = SessionLocal()
    try:
        job = db.query(AIJob).filter(
            AIJob.job_type == "quiz", AIJob.status == "QUEUED"
        ).order_by(AIJob.created_at.asc()).with_for_update(skip_locked=True).first()
        if not job:
            db.rollback()
            return None
        job.status = "RETRIEVING"
        job.updated_at = datetime.utcnow()
        db.commit()
        return job.id
    except Exception:
        db.rollback()
        logger.exception("Unable to claim quiz job")
        return None
    finally:
        db.close()


def _next_material_id():
    """Find a persisted upload; _process_and_notify claims it with an atomic lease."""
    try:
        row = mongo_db.resources.find_one(
            {"assignment_id": {"$exists": False}, "processing_status": "UPLOADED"},
            {"_id": 1},
            sort=[("created_at", 1)],
        )
        return str(row["_id"]) if row else None
    except Exception:
        logger.exception("Unable to poll material queue")
        return None


def run_once():
    did_work = False
    _recover_stale_ai_jobs()
    material_id = _next_material_id()
    if material_id:
        did_work = True
        try:
            asyncio.run(_process_and_notify(material_id))
        except Exception:
            logger.exception("Material worker task failed resource_id=%s", material_id)
    job_id = _claim_quiz_job()
    if job_id is not None:
        did_work = True
        try:
            run_quiz_job(job_id)
        except Exception:
            logger.exception("Quiz worker task failed job_id=%s", job_id)
    return did_work


def main():
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    logger.info("Durable LMS worker started poll_seconds=%s max_attempts=%s", POLL_SECONDS, MAX_ATTEMPTS)
    while not _STOP:
        try:
            if not run_once():
                time.sleep(POLL_SECONDS)
        except Exception:
            logger.exception("Unexpected worker loop failure")
            time.sleep(POLL_SECONDS)
    logger.info("LMS worker stopped")


if __name__ == "__main__":
    main()
