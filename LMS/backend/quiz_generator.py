import re
import random
from fastapi import APIRouter, Depends, HTTPException
from auth import get_user
from vector_store import search_resources
from database import SessionLocal
from models import Enrollment

router = APIRouter()

def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if len(s.split()) >= 8]

def _build_quiz(results):
    pool = []
    for result in results:
        for sentence in _sentences(result["content"]):
            pool.append({"title": result["title"], "course_id": result["course_id"], "snippet": sentence})
    if not pool:
        return []
    random.shuffle(pool)
    chosen = []
    seen = set()
    for item in pool:
        key = (item["title"], item["snippet"])
        if key not in seen:
            chosen.append(item)
            seen.add(key)
        if len(chosen) == 5:
            break

    titles = list(dict.fromkeys(x["title"] for x in pool))
    questions = []
    for i, item in enumerate(chosen):
        distractors = [t for t in titles if t != item["title"]]
        random.shuffle(distractors)
        options = [item["title"]] + distractors[:3]
        while len(options) < min(4, len(titles)):
            options.append("Another course resource")
        random.shuffle(options)
        questions.append({
            "id": i + 1,
            "question": "Which course resource most directly supports this statement?",
            "context": item["snippet"][:420],
            "options": options,
            "answer": item["title"],
            "source": item["title"]
        })
    return questions

@router.get("/quiz/generate")
def generate_quiz(user=Depends(get_user)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    try:
        db = SessionLocal()
        try:
            course_ids = [e.course_id for e in db.query(Enrollment).filter(Enrollment.student_id == user["id"]).all()]
        finally:
            db.close()
        results = search_resources("key concepts definitions important topics", course_ids)
        quiz = _build_quiz(results)
        if not quiz:
            raise HTTPException(status_code=404, detail="Upload course materials before generating a quiz")
        return {"title": "AI Revision Quiz", "questions": quiz}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Quiz generator unavailable: {exc}")
