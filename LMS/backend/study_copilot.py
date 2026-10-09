import asyncio
import re
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_user
from database import get_db
from study_knowledge import find_knowledge
from models import Course, Enrollment

router = APIRouter(tags=["study"])


class CopilotRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1200)
    course_id: int | None = Field(default=None, gt=0)


class NotesRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=300)


def _course_ids(user_id, db: Session):
    return [e[0] for e in db.query(Enrollment.course_id).filter(Enrollment.student_id == user_id).all()]



def _authorized_course_ids(user, db: Session, course_id: int | None):
    if course_id is None:
        return None
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if user["role"] == "student":
        enrolled = db.query(Enrollment.id).filter(Enrollment.student_id == user["id"], Enrollment.course_id == course_id).first()
        if not enrolled:
            raise HTTPException(status_code=403, detail="You are not enrolled in this course")
    elif user["role"] == "teacher" and course.teacher_id != user["id"]:
        raise HTTPException(status_code=403, detail="You can only use your own course")
    return [course_id]

def _sentence_parts(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if len(s.split()) >= 6]


def _retrieval_answer(question, results):
    words = set(re.findall(r"[a-zA-Z]{3,}", question.lower()))
    ranked = []
    for result in results:
        sentences = _sentence_parts(result["content"])
        scored = []
        for sentence in sentences:
            s_words = set(re.findall(r"[a-zA-Z]{3,}", sentence.lower()))
            score = len(words & s_words)
            if score:
                scored.append((score, sentence))
        scored.sort(key=lambda x: x[0], reverse=True)
        ranked.append({**result, "snippets": [s for _, s in scored[:2]]})
    useful = [r for r in ranked if r["snippets"]] or ranked[:3]
    parts = []
    for result in useful[:3]:
        snippet = " ".join(result["snippets"][:2]).strip()
        if snippet:
            parts.append(snippet)
    answer = "Based on your course materials: " + " ".join(parts)
    return answer[:5000], useful


def _looks_academic_question(question):
    text = (question or "").lower()
    cues = (
        "explain", "define", "definition", "algorithm", "programming", "code",
        "database", "sql", "python", "java", "operating system", "computer",
        "network", "mathematics", "math", "physics", "chemistry", "biology",
        "machine learning", "study", "concept", "formula", "equation",
        "difference between",
    )
    return any(cue in text for cue in cues)


def build_answer(question, results):
    knowledge = find_knowledge(question)
    if knowledge:
        return {
            "answer": knowledge["answer"],
            "confidence": "high",
            "mode": "general study knowledge" if not results else "study knowledge + course context",
            "sources": [{"title": knowledge["topic"], "type": "general study knowledge", "course_id": 0, "distance": 0}] + [{"title": r["title"], "type": r["type"], "course_id": r["course_id"], "distance": r["distance"]} for r in results[:3]],
        }
    if not results:
        if not _looks_academic_question(question):
            return {
                "answer": "This does not appear to be an academic study question supported by the configured knowledge topics. Ask about a course concept or provide relevant course material.",
                "confidence": "low",
                "mode": "unsupported query",
                "sources": [],
            }
        return {
            "answer": "This deployment does not have a general-purpose model provider configured for this topic, and no matching course material was found. Try a supported study topic or provide relevant course material.",
            "confidence": "low",
            "mode": "general study assistant",
            "sources": [],
        }
    answer, useful = _retrieval_answer(question, results)
    return {
        "answer": answer,
        "confidence": "high" if len(useful) >= 2 else "medium",
        "mode": "course materials",
        "sources": [{"title": r["title"], "type": r["type"], "course_id": r["course_id"], "distance": r["distance"]} for r in useful[:4]],
    }


async def _search(question, course_ids):
    from vector_store import search_resources_detailed
    return await asyncio.to_thread(search_resources_detailed, question, course_ids)


@router.post("/study-copilot")
async def study_copilot(data: CopilotRequest, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in {"student", "teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Access denied")
    question = data.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail={"error": "VALIDATION_ERROR", "message": "Question cannot be empty"})
    try:
        course_ids = _authorized_course_ids(user, db, data.course_id)
        started = time.perf_counter()
        results = []
        metrics = {"embedding_ms": 0.0, "vector_search_ms": 0.0, "context_build_ms": 0.0, "llm_ms": 0.0}
        if course_ids:
            results, metrics = await asyncio.wait_for(_search(question, course_ids), timeout=12)
        answer = build_answer(question, results)
        metrics["context_build_ms"] = round((time.perf_counter() - started) * 1000 - metrics["embedding_ms"] - metrics["vector_search_ms"], 2)
        metrics["total_ms"] = round((time.perf_counter() - started) * 1000, 2)
        return {"question": question, "course_id": data.course_id, **answer, "metrics": metrics}
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail={"error": "AI_TIMEOUT", "message": "The AI request took too long. Please retry."})
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail={"error": "AI_UNAVAILABLE", "message": "The study assistant is temporarily unavailable."})


@router.post("/study-notes")
async def study_notes(data: NotesRequest, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in {"student", "teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Access denied")
    topic = data.topic.strip()
    knowledge = find_knowledge(topic)
    if knowledge:
        return {"topic": knowledge["topic"], "summary": knowledge["answer"], "bullets": knowledge["bullets"], "key_terms": knowledge["terms"], "exam_tip": knowledge["tip"], "mode": "study knowledge", "sources": [{"title": knowledge["topic"], "type": "core concept", "course_id": 0}]}
    try:
        results, _ = await asyncio.wait_for(_search(topic, _course_ids(user["id"], db) if user["role"] == "student" else None), timeout=12)
        if not results:
            raise HTTPException(status_code=404, detail="No matching course material found for this topic")
        sentences = []
        seen = set()
        for result in results[:4]:
            for sentence in _sentence_parts(result["content"]):
                key = sentence.lower()
                if key not in seen:
                    sentences.append(sentence)
                    seen.add(key)
                if len(sentences) >= 5:
                    break
            if len(sentences) >= 5:
                break
        if not sentences:
            raise HTTPException(status_code=404, detail="The matching resource does not contain enough text to make notes")
        return {"topic": topic, "summary": sentences[0][:1200], "bullets": [x[:600] for x in sentences[1:5]] or sentences[:1], "key_terms": [r["title"] for r in results[:4]], "exam_tip": "Revise the summary first, then use the bullet points as a quick last-minute checklist.", "mode": "course materials", "sources": [{"title": r["title"], "type": r["type"], "course_id": r["course_id"]} for r in results[:4]]}
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail={"error": "AI_TIMEOUT", "message": "Study notes took too long. Please retry."})
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail={"error": "AI_UNAVAILABLE", "message": "Study notes are temporarily unavailable."})
