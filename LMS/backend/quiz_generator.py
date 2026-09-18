import random
from fastapi import APIRouter, Depends, HTTPException
from auth import get_user
from vector_store import search_resources
from database import SessionLocal
from models import Enrollment
from study_knowledge import KNOWLEDGE

router = APIRouter()

def _course_ids(user_id):
    db = SessionLocal()
    try:
        return [e.course_id for e in db.query(Enrollment).filter(Enrollment.student_id == user_id).all()]
    finally:
        db.close()

def _relevant_topics(results):
    text = " ".join(r.get("content", "") for r in results).lower()
    return [item for item in KNOWLEDGE if any(alias in text for alias in item["aliases"])]

def _make_questions(topics):
    random.shuffle(topics)
    selected = topics[:5]
    questions = []
    for i, item in enumerate(selected):
        distractors = [x["topic"] for x in KNOWLEDGE if x["topic"] != item["topic"]]
        random.shuffle(distractors)
        options = [item["topic"]] + distractors[:3]
        random.shuffle(options)
        questions.append({"id": i + 1, "question": "Which concept best matches this definition?", "context": item["answer"], "options": options, "answer": item["topic"], "source": item["topic"]})
    return questions

@router.get("/quiz/generate")
def generate_quiz(user=Depends(get_user)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    try:
        course_ids = _course_ids(user["id"])
        results = search_resources("key concepts definitions important topics", course_ids)
        topics = _relevant_topics(results)
        if len(topics) < 5:
            topics.extend([x for x in KNOWLEDGE if x not in topics])
        if not topics:
            raise HTTPException(status_code=404, detail="Upload course materials before generating a quiz")
        return {"title": "AI Revision Quiz", "questions": _make_questions(topics)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Quiz generator unavailable: {exc}")
