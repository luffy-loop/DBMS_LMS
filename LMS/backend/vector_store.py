import re
from functools import lru_cache

from sqlalchemy.orm import Session

from database import SessionLocal
from models import Course, ResourceEmbedding
from mongodb import mongo_db


@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


def _resources(course_ids=None):
    db = SessionLocal()
    try:
        resources = []
        course_query = db.query(Course)
        if course_ids is not None:
            course_query = (
                course_query.filter(Course.id.in_(course_ids))
                if course_ids
                else course_query.filter(False)
            )

        for course in course_query.all():
            resources.append({
                "id": f"course-{course.id}",
                "title": course.title,
                "content": course.description or "",
                "type": "course",
                "course_id": course.id,
            })

        resource_query = {"course_id": {"$in": course_ids}} if course_ids is not None else {}
        for resource in mongo_db.resources.find(resource_query):
            resources.append({
                "id": f"resource-{resource['_id']}",
                "title": resource.get("title", ""),
                "content": resource.get("content", ""),
                "type": "resource",
                "course_id": resource.get("course_id", 0),
            })

        return resources
    finally:
        db.close()


def _sync_resources(resources):
    if not resources:
        return

    model = get_model()
    db = SessionLocal()
    try:
        for item in resources:
            source = f'{item["title"]}. {item["content"]}'
            row = (
                db.query(ResourceEmbedding)
                .filter(ResourceEmbedding.source_id == item["id"])
                .first()
            )

            if row and row.content == item["content"] and row.title == item["title"]:
                continue

            vector = model.encode(source).tolist()

            if row:
                row.title = item["title"]
                row.content = item["content"]
                row.source_type = item["type"]
                row.course_id = item["course_id"]
                row.embedding = vector
            else:
                db.add(ResourceEmbedding(
                    source_id=item["id"],
                    source_type=item["type"],
                    course_id=item["course_id"],
                    title=item["title"],
                    content=item["content"],
                    embedding=vector,
                ))

        db.commit()
    finally:
        db.close()


def _lexical_search(query, resources):
    words = set(re.findall(r"[a-zA-Z0-9]{3,}", query.lower()))
    if not words:
        return []

    ranked = []
    for item in resources:
        text = f'{item["title"]} {item["title"]} {item["content"]}'.lower()
        hits = sum(1 for word in words if word in text)
        if hits:
            ranked.append((hits / len(words), item))

    ranked.sort(key=lambda x: x[0], reverse=True)

    return [{
        "title": item["title"],
        "content": f'{item["title"]}. {item["content"]}',
        "type": item["type"],
        "course_id": int(item["course_id"]),
        "distance": round(1 - score, 4),
    } for score, item in ranked[:8]]


def search_resources(query, course_ids=None):
    resources = _resources(course_ids)
    if not resources:
        return []

    try:
        _sync_resources(resources)

        model = get_model()
        query_vector = model.encode(query).tolist()

        db: Session = SessionLocal()
        try:
            q = db.query(ResourceEmbedding)
            if course_ids is not None:
                q = q.filter(ResourceEmbedding.course_id.in_(course_ids))

            rows = (
                q.order_by(ResourceEmbedding.embedding.cosine_distance(query_vector))
                .limit(8)
                .all()
            )

            return [{
                "title": row.title,
                "content": f"{row.title}. {row.content}",
                "type": row.source_type,
                "course_id": int(row.course_id or 0),
                "distance": round(
                    float(row.embedding.cosine_distance(query_vector))
                    if row.embedding is not None else 1.0,
                    4,
                ),
            } for row in rows]
        finally:
            db.close()

    except Exception:
        return _lexical_search(query, resources)
