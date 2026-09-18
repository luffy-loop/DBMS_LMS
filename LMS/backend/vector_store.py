import re
from functools import lru_cache

import chromadb
from mongodb import mongo_db

client = chromadb.PersistentClient(path="./vector_data")
collection = client.get_or_create_collection("lms_resources")

@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")

def _resources(course_ids=None):
    from database import SessionLocal
    from models import Course
    db = SessionLocal()
    try:
        resources = []
        course_query = db.query(Course)
        if course_ids is not None:
            course_query = course_query.filter(Course.id.in_(course_ids)) if course_ids else course_query.filter(False)
        for course in course_query.all():
            resources.append({
                "id": f"course-{course.id}",
                "title": course.title,
                "content": course.description or "",
                "type": "course",
                "course_id": course.id
            })
        resource_query = {"course_id": {"$in": course_ids}} if course_ids is not None else {}
        for resource in mongo_db.resources.find(resource_query):
            resources.append({
                "id": f"resource-{resource['_id']}",
                "title": resource.get("title", ""),
                "content": resource.get("content", ""),
                "type": "resource",
                "course_id": resource.get("course_id", 0)
            })
        return resources
    finally:
        db.close()

def _sync_resources(resources):
    if not resources:
        return
    ids = [item["id"] for item in resources]
    existing = collection.get(ids=ids, include=["documents"])
    old = dict(zip(existing["ids"], existing.get("documents") or []))
    changed = [item for item in resources if old.get(item["id"]) != f'{item["title"]}. {item["content"]}']
    if not changed:
        return
    model = get_model()
    docs = [f'{item["title"]}. {item["content"]}' for item in changed]
    collection.upsert(
        ids=[item["id"] for item in changed],
        documents=docs,
        metadatas=[{"type": item["type"], "course_id": str(item["course_id"])} for item in changed],
        embeddings=model.encode(docs).tolist()
    )

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
        "distance": round(1 - score, 4)
    } for score, item in ranked[:8]]

def search_resources(query, course_ids=None):
    resources = _resources(course_ids)
    if not resources:
        return []
    try:
        _sync_resources(resources)
        model = get_model()
        result = collection.query(
            query_embeddings=[model.encode(query).tolist()],
            ids=[item["id"] for item in resources],
            n_results=min(8, len(resources)),
            include=["documents", "metadatas", "distances"]
        )
        return [{
            "title": doc.split(". ", 1)[0],
            "content": doc,
            "type": result["metadatas"][0][i]["type"],
            "course_id": int(result["metadatas"][0][i]["course_id"]),
            "distance": round(float(result["distances"][0][i]), 4)
        } for i, doc in enumerate(result["documents"][0])]
    except Exception:
        return _lexical_search(query, resources)
