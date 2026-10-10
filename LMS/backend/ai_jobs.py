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
    values = {"status": status, "updated_at": datetime.utcnow()}
    if result is not None:
        values["result"] = json.dumps(result)
    if error is not None:
        values["error"] = json.dumps(error) if isinstance(error, dict) else str(error)[:2000]

    query = db.query(AIJob).filter(AIJob.id == job.id)
    if status != "CANCELLED":
        query = query.filter(AIJob.status.notin_({"CANCELLED", "COMPLETED", "FAILED"}))
    changed = query.update(values, synchronize_session=False)
    if not changed:
        db.rollback()
        return False
    db.commit()
    db.refresh(job)
    return True


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


def _generate_grounded_questions(results, count):
    """Create deterministic, source-grounded concept-identification questions.

    This is a local template-based fallback, not an LLM. It fails closed when
    the source does not contain enough distinct concepts for defensible options.
    """
    import re

    count = max(1, min(10, int(count)))
    patterns = (
        re.compile(
            r"^\s*(?:(?:a|an|the)\s+)?"
            r"(?P<term>[A-Za-z][A-Za-z0-9/&() -]{1,70}?)\s+"
            r"(?:is|are|means|refers to|can be defined as|is defined as)\s+"
            r"(?P<definition>.+?)\s*[.!?]?\s*$",
            re.IGNORECASE,
        ),
        re.compile(
            r"^\s*(?P<term>[A-Za-z][A-Za-z0-9/&() -]{1,70}?)\s*:\s*"
            r"(?P<definition>.+?)\s*[.!?]?\s*$"
        ),
        re.compile(
            r"^\s*(?P<term>[A-Za-z][A-Za-z0-9/&() -]{1,70}?)\s+[—–-]\s+"
            r"(?P<definition>.+?)\s*[.!?]?\s*$"
        ),
    )
    concepts = []
    seen_terms = set()
    seen_sentences = set()
    for result in results:
        title = " ".join(str(result.get("title") or "Course material").split())[:200]
        content = str(result.get("content") or "")
        for raw_sentence in re.split(r"(?<=[.!?])\s+|[\r\n]+", content):
            sentence = " ".join(raw_sentence.split()).strip()
            if len(sentence.split()) < 8 or len(sentence) > 700:
                continue
            sentence_key = sentence.casefold()
            if sentence_key in seen_sentences:
                continue
            match = next((pattern.match(sentence) for pattern in patterns if pattern.match(sentence)), None)
            if not match:
                continue
            term = re.sub(r"^(?:a|an|the)\s+", "", match.group("term").strip(), flags=re.IGNORECASE)
            definition = match.group("definition").strip(" .,:;—–-")
            term = " ".join(term.split()).strip(" .,:;—–-")
            term_words = term.split()
            definition_words = definition.split()
            if not term or len(term_words) > 6 or len(definition_words) < 5:
                continue
            if len(term) > 70 or len(definition) < 20 or len(definition) > 600:
                continue
            term_key = term.casefold()
            if term_key in seen_terms or term_key in definition.casefold():
                continue
            if len(set(re.findall(r"[a-z]{3,}", definition.casefold()))) < 4:
                continue
            concepts.append({
                "term": term,
                "definition": definition,
                "sentence": sentence,
                "source": title,
            })
            seen_terms.add(term_key)
            seen_sentences.add(sentence_key)

    if len(concepts) < 4:
        return []

    questions = []
    for item in concepts:
        correct_tokens = set(re.findall(r"[a-z]{3,}", item["definition"].casefold()))
        ranked = []
        for other in concepts:
            if other["term"].casefold() == item["term"].casefold():
                continue
            other_tokens = set(re.findall(r"[a-z]{3,}", other["definition"].casefold()))
            union = correct_tokens | other_tokens
            overlap = len(correct_tokens & other_tokens) / max(1, len(union))
            if overlap < 0.8:
                ranked.append((overlap, other))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        distractors = []
        seen_options = {item["term"].casefold()}
        for _, other in ranked:
            key = other["term"].casefold()
            if key not in seen_options:
                distractors.append(other)
                seen_options.add(key)
            if len(distractors) == 3:
                break
        if len(distractors) < 3:
            continue
        options = [item["term"]] + [other["term"] for other in distractors]
        if len({option.casefold() for option in options}) != 4:
            continue
        questions.append({
            "id": len(questions) + 1,
            "question": "Which concept matches this description: " + item["definition"].rstrip(".!?") + "?",
            "context": "Source material: " + item["source"],
            "options": options,
            "answer": item["term"],
            "source": item["source"],
            "question_type": "mcq",
            "max_marks": 1,
            "explanation": "The selected course material describes " + item["term"] + " as: " + item["definition"],
        })
        if len(questions) >= count:
            break
    return questions
