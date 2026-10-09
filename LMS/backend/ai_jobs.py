import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime
from uuid import uuid4

from database import SessionLocal
from models import AIJob

logger = logging.getLogger("lms.ai_jobs")
JOB_TIMEOUT = max(5, int(os.getenv("AI_JOB_TIMEOUT_SECONDS", "20")))


def create_job(db, user_id, course_id, job_type, payload):
    job = AIJob(job_id=str(uuid4()), job_type=job_type, status="QUEUED", user_id=user_id, course_id=course_id, payload=json.dumps(payload), created_at=datetime.utcnow(), updated_at=datetime.utcnow())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def set_job(db, job, status, result=None, error=None):
    job.status=status
    job.updated_at=datetime.utcnow()
    if result is not None: job.result=json.dumps(result)
    if error is not None: job.error=json.dumps(error) if isinstance(error,dict) else str(error)[:2000]
    db.commit()


def _timed_search(query, course_id):
    from vector_store import search_resources_for_quiz
    executor=ThreadPoolExecutor(max_workers=1)
    future=executor.submit(search_resources_for_quiz,query,course_id)
    try:
        return future.result(timeout=JOB_TIMEOUT)
    except FutureTimeout:
        future.cancel()
        executor.shutdown(wait=False,cancel_futures=True)
        raise TimeoutError()
    finally:
        if not future.done():
            executor.shutdown(wait=False,cancel_futures=True)
        else:
            executor.shutdown(wait=True,cancel_futures=True)


def run_quiz_job(job_id):
    db=SessionLocal()
    try:
        job=db.query(AIJob).filter(AIJob.id==job_id).first()
        if not job or job.status=="CANCELLED": return
        payload=json.loads(job.payload or "{}")
        set_job(db,job,"RETRIEVING")
        results,metrics=_timed_search(payload.get("query","key concepts important definitions"),job.course_id)
        db.refresh(job)
        if job.status=="CANCELLED": return
        if not results: raise ValueError("No processed course material is available. Upload a PDF or other supported material and wait until processing finishes.")
        set_job(db,job,"GENERATING")
        questions=_generate_grounded_questions(results,int(payload.get("question_count",5)))
        if not questions: raise ValueError("Not enough distinct statements were found in processed course material to draft a quiz. Upload or process more course material.")
        db.refresh(job)
        if job.status=="CANCELLED": return
        set_job(db,job,"COMPLETED",{"title":"Course Revision Quiz","course_id":job.course_id,"questions":questions,"metrics":metrics})
    except TimeoutError:
        job=db.query(AIJob).filter(AIJob.id==job_id).first()
        if job and job.status!="CANCELLED": set_job(db,job,"FAILED",error={"error":"AI_TIMEOUT","message":"Quiz generation took too long. Please retry."})
    except Exception as exc:
        logger.warning("AI quiz job failed job_id=%s error_type=%s", job_id, type(exc).__name__)
        job=db.query(AIJob).filter(AIJob.id==job_id).first()
        if job and job.status!="CANCELLED":
            safe_messages = {
                "No processed course material is available. Upload a PDF or other supported material and wait until processing finishes.": "NO_COURSE_MATERIAL",
                "Not enough distinct statements were found in processed course material to draft a quiz. Upload or process more course material.": "INSUFFICIENT_MATERIAL",
            }
            message = str(exc) if str(exc) in safe_messages else "Quiz retrieval or generation failed. Check that course material is processed and the database is reachable."
            code = safe_messages.get(str(exc), "AI_GENERATION_FAILED")
            set_job(db,job,"FAILED",error={"error":code,"message":message[:300]})
    finally:
        db.close()


def _generate_grounded_questions(results,count):
    import re
    count=max(1,min(10,count))
    clean=[];seen=set()
    for result in results:
        title=" ".join(str(result.get("title") or "Course material").split())
        sentences=[x.strip() for x in re.split(r"(?<=[.!?])\s+",str(result.get("content") or "")) if len(x.split())>=8]
        for sentence in sentences:
            sentence=sentence[:700].strip()
            key=sentence.lower()
            if key not in seen:
                clean.append((title,sentence));seen.add(key)
            if len(clean)>=count: break
        if len(clean)>=count: break
    if len(clean)<2:return []
    questions=[]
    option_count=min(4,len(clean))
    for i,(title,sentence) in enumerate(clean[:count],1):
        options=[clean[(i-1+j)%len(clean)][1] for j in range(option_count)]
        questions.append({"id":i,"question":"Which statement is supported by the selected course material?","context":sentence,"options":options,"answer":sentence,"source":title,"question_type":"mcq","max_marks":1,"explanation":"This statement is quoted from processed course material."})
    return questions
