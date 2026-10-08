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
    from vector_store import search_resources_detailed
    executor=ThreadPoolExecutor(max_workers=1)
    future=executor.submit(search_resources_detailed,query,(course_id,))
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
        if not results: raise ValueError("No indexed learning material is ready for this course")
        set_job(db,job,"GENERATING")
        questions=_generate_grounded_questions(results,int(payload.get("question_count",5)))
        if not questions: raise ValueError("Not enough grounded material to generate a quiz")
        set_job(db,job,"COMPLETED",{"title":"Course Revision Quiz","course_id":job.course_id,"questions":questions,"metrics":metrics})
    except TimeoutError:
        job=db.query(AIJob).filter(AIJob.id==job_id).first()
        if job and job.status!="CANCELLED": set_job(db,job,"FAILED",error={"error":"AI_TIMEOUT","message":"Quiz generation took too long. Please retry."})
    except Exception as exc:
        logger.exception("AI quiz job failed")
        job=db.query(AIJob).filter(AIJob.id==job_id).first()
        if job and job.status!="CANCELLED": set_job(db,job,"FAILED",error={"error":"AI_GENERATION_FAILED","message":str(exc)[:500]})
    finally:
        db.close()


def _generate_grounded_questions(results,count):
    import re
    count=max(1,min(10,count))
    clean=[];seen=set()
    for result in results:
        sentences=[x.strip() for x in re.split(r"(?<=[.!?])\s+",result.get("content","")) if len(x.split())>=8]
        for sentence in sentences:
            key=sentence.lower()
            if key not in seen:
                clean.append((result.get("title","Course material"),sentence));seen.add(key)
            if len(clean)>=count: break
        if len(clean)>=count: break
    if not clean:return []
    titles=list(dict.fromkeys(title for title,_ in clean))
    questions=[]
    for i,(title,sentence) in enumerate(clean[:count],1):
        options=list(dict.fromkeys([title]+titles))
        while len(options)<4: options.append("Course material "+str(len(options)+1))
        options=options[:4]
        questions.append({"id":i,"question":"Which course material contains the following concept?","context":sentence[:700],"options":options,"answer":title,"source":title,"question_type":"mcq","max_marks":1,"explanation":"The correct option is the learning material from which this passage was retrieved."})
    return questions
