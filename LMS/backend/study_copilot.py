import asyncio
import re
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth import get_user
from database import get_db
from vector_store import search_resources_detailed
from study_knowledge import find_knowledge
from models import Enrollment

router = APIRouter(tags=["study"])


class CopilotRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1200)


class NotesRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=300)


def _course_ids(user_id, db: Session):
    return [e[0] for e in db.query(Enrollment.course_id).filter(Enrollment.student_id == user_id).all()]


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


def build_answer(question, results):
    knowledge = find_knowledge(question)
    if knowledge:
        return {
            "answer": knowledge["answer"],
            "confidence": "high",
            "mode": "study knowledge",
            "sources": [{"title": knowledge["topic"], "type": "core concept", "course_id": 0, "distance": 0}],
        }
    if not results:
        return {
            "answer": "I could not find that topic in your authorized course material yet. Try a topic from your course resources or upload the relevant notes first.",
            "confidence": "low",
            "mode": "course materials",
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
    return await asyncio.to_thread(search_resources_detailed, question, course_ids)


@router.post("/study-copilot")
async def study_copilot(data: CopilotRequest, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in {"student", "teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Access denied")
    question = data.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        course_ids = _course_ids(user["id"], db) if user["role"] == "student" else None
        started = time.perf_counter()
        results, metrics = await asyncio.wait_for(_search(question, course_ids), timeout=20)
        answer = build_answer(question, results)
        metrics["context_build_ms"] = round((time.perf_counter() - started) * 1000 - metrics["embedding_ms"] - metrics["vector_search_ms"], 2)
        metrics["llm_ms"] = 0
        metrics["total_ms"] = round((time.perf_counter() - started) * 1000, 2)
        return {"question": question, **answer, "metrics": metrics}
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail={"error": "AI_TIMEOUT", "message": "Study Copilot took too long. Please retry."})
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail={"error": "AI_UNAVAILABLE", "message": "Study Copilot is temporarily unavailable."})


@router.post("/study-notes")
async def study_notes(data: NotesRequest, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in {"student", "teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Access denied")
    topic = data.topic.strip()
    knowledge = find_knowledge(topic)
    if knowledge:
        return {"topic": knowledge["topic"], "summary": knowledge["answer"], "bullets": knowledge["bullets"], "key_terms": knowledge["terms"], "exam_tip": knowledge["tip"], "mode": "study knowledge", "sources": [{"title": knowledge["topic"], "type": "core concept", "course_id": 0}]}
    try:
        results, _ = await asyncio.wait_for(_search(topic, _course_ids(user["id"], db) if user["role"] == "student" else None), timeout=20)
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
