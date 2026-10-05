import random
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from auth import get_user
from vector_store import search_resources
from database import get_db
from models import Enrollment
from study_knowledge import KNOWLEDGE

router = APIRouter()

def _course_ids(user_id, db: Session):
    return [e[0] for e in db.query(Enrollment.course_id).filter(Enrollment.student_id == user_id).all()]

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
def generate_quiz(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in ["student", "teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        course_ids = _course_ids(user["id"], db) if user["role"] == "student" else None
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
