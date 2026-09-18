import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from vector_store import search_resources
from database import SessionLocal
from models import Enrollment
from study_knowledge import find_knowledge

router = APIRouter()

class CopilotRequest(BaseModel):
    question: str

class NotesRequest(BaseModel):
    topic: str

def _course_ids(user_id):
    db = SessionLocal()
    try:
        return [e.course_id for e in db.query(Enrollment).filter(Enrollment.student_id == user_id).all()]
    finally:
        db.close()

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
        ranked.append({**result, "snippets": [s for _, s in scored[:3]]})
    useful = [r for r in ranked if r["snippets"]] or ranked[:3]
    parts = []
    for result in useful[:3]:
        snippet = " ".join(result["snippets"][:2]).strip()
        if snippet:
            parts.append(snippet)
    return "Based on your course materials: " + " ".join(parts), useful

def build_answer(question, results):
    knowledge = find_knowledge(question)
    if knowledge:
        return {"answer": knowledge["answer"], "confidence": "high", "mode": "study knowledge", "sources": [{"title": knowledge["topic"], "type": "core concept", "course_id": 0, "distance": 0}]}
    if not results:
        return {"answer": "I could not find that topic in your enrolled course material yet. Try asking about a topic from your course PDF or upload the relevant notes first.", "confidence": "low", "mode": "course materials", "sources": []}
    answer, useful = _retrieval_answer(question, results)
    return {"answer": answer, "confidence": "high" if len(useful) >= 2 else "medium", "mode": "course materials", "sources": [{"title": r["title"], "type": r["type"], "course_id": r["course_id"], "distance": r["distance"]} for r in useful[:4]]}

@router.post("/study-copilot")
def study_copilot(data: CopilotRequest, user=Depends(get_user)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    question = data.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        course_ids = _course_ids(user["id"])
        results = search_resources(question, course_ids)
        return {"question": question, **build_answer(question, results)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Study Copilot unavailable: {exc}")

@router.post("/study-notes")
def study_notes(data: NotesRequest, user=Depends(get_user)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    topic = data.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic cannot be empty")
    try:
        knowledge = find_knowledge(topic)
        if knowledge:
            return {"topic": knowledge["topic"], "summary": knowledge["answer"], "bullets": knowledge["bullets"], "key_terms": knowledge["terms"], "exam_tip": knowledge["tip"], "mode": "study knowledge", "sources": [{"title": knowledge["topic"], "type": "core concept", "course_id": 0}]}
        results = search_resources(topic, _course_ids(user["id"]))
        if not results:
            raise HTTPException(status_code=404, detail="No matching course material found for this topic")
        sentences = []
        seen = set()
        for result in results:
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
        return {"topic": topic, "summary": sentences[0], "bullets": sentences[1:5] or sentences[:1], "key_terms": [r["title"] for r in results[:4]], "exam_tip": "Revise the summary first, then use the bullet points as a quick last-minute checklist.", "mode": "course materials", "sources": [{"title": r["title"], "type": r["type"], "course_id": r["course_id"]} for r in results[:4]]}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Quick notes unavailable: {exc}")
