import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth import get_user
from vector_store import search_resources
from database import SessionLocal
from models import Enrollment

router = APIRouter()

class CopilotRequest(BaseModel):
    question: str

def build_answer(question, results):
    if not results:
        return {
            "answer": "I could not find relevant material in your course resources. Try uploading a PDF or asking about a topic covered in your materials.",
            "confidence": "low",
            "sources": []
        }

    words = set(re.findall(r"[a-zA-Z]{3,}", question.lower()))
    ranked = []
    for result in results:
        text = result["content"]
        sentences = re.split(r"(?<=[.!?])\s+", text)
        scored = []
        for sentence in sentences:
            s_words = set(re.findall(r"[a-zA-Z]{3,}", sentence.lower()))
            score = len(words & s_words)
            if score:
                scored.append((score, sentence.strip()))
        scored.sort(key=lambda x: x[0], reverse=True)
        ranked.append({
            **result,
            "snippets": [s for _, s in scored[:3]]
        })

    useful = [r for r in ranked if r["snippets"]]
    if not useful:
        useful = ranked[:3]

    answer_parts = []
    for result in useful[:3]:
        snippet = " ".join(result["snippets"][:2]).strip()
        if snippet:
            answer_parts.append(snippet)

    answer = "Based on your learning materials: " + " ".join(answer_parts)
    return {
        "answer": answer,
        "confidence": "high" if len(useful) >= 2 else "medium",
        "sources": [{
            "title": r["title"],
            "type": r["type"],
            "course_id": r["course_id"],
            "distance": r["distance"]
        } for r in useful[:4]]
    }

@router.post("/study-copilot")
def study_copilot(data: CopilotRequest, user=Depends(get_user)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    question = data.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    try:
        db = SessionLocal()
        try:
            course_ids = [e.course_id for e in db.query(Enrollment).filter(Enrollment.student_id == user["id"]).all()]
        finally:
            db.close()
        results = search_resources(question, course_ids)
        return {"question": question, **build_answer(question, results)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Study Copilot unavailable: {exc}")
