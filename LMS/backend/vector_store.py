import re
import time
from functools import lru_cache

import chromadb

from mongodb import mongo_db

client = chromadb.PersistentClient(path="./vector_data")
collection = client.get_or_create_collection("lms_resources")
CACHE_TTL = 45
_cache = {}


@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")


@lru_cache(maxsize=512)
def embed_text(text):
    return get_model().encode(text).tolist()


def clear_search_cache():
    _cache.clear()


def index_resource(item):
    content = item.get("content") or ""
    document = f'{item.get("title", "")}. {content}'.strip()
    if not document:
        return
    collection.upsert(
        ids=[item["id"]],
        documents=[document],
        metadatas=[{
            "type": item.get("type", "resource"),
            "course_id": str(item["course_id"]),
        }],
        embeddings=[embed_text(document)],
    )


def remove_resource(resource_id):
    try:
        collection.delete(ids=[resource_id])
    finally:
        clear_search_cache()


def _resources(course_ids=None):
    from database import SessionLocal
    from models import Course

    db = SessionLocal()
    try:
        resources = []
        query = db.query(Course)
        if course_ids is not None:
            query = query.filter(Course.id.in_(course_ids)) if course_ids else query.filter(False)
        for course in query.all():
            resources.append({
                "id": f"course-{course.id}",
                "title": course.title,
                "content": course.description or "",
                "type": "course",
                "course_id": course.id,
            })
        resource_query = {"processing_status": "READY"}
        if course_ids is not None:
            resource_query["course_id"] = {"$in": course_ids}
        for resource in mongo_db.resources.find(resource_query, {"_id": 1, "title": 1, "content": 1, "course_id": 1}):
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


def _lexical_search(query, resources):
    words = set(re.findall(r"[a-zA-Z0-9]{3,}", query.lower()))
    if not words:
        return []
    ranked = []
    for item in resources:
        text = f'{item["title"]} {item["content"]}'.lower()
        hits = sum(1 for word in words if word in text)
        if hits:
            ranked.append((hits / len(words), item))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return [{
        "title": item["title"],
        "content": f'{item["title"]}. {item["content"]}'[:8000],
        "type": item["type"],
        "course_id": int(item["course_id"]),
        "distance": round(1 - score, 4),
    } for score, item in ranked[:6]]


def search_resources_detailed(query, course_ids=None):
    normalized = " ".join((query or "").split()).lower()
    ids_key = tuple(sorted(set(course_ids))) if course_ids is not None else None
    cache_key = (normalized, ids_key)
    now = time.monotonic()
    cached = _cache.get(cache_key)
    if cached and now - cached[0] < CACHE_TTL:
        return cached[1], dict(cached[2])

    metrics = {"embedding_ms": 0.0, "vector_search_ms": 0.0, "context_build_ms": 0.0, "total_ms": 0.0}
    started = time.perf_counter()
    if not normalized:
        return [], metrics

    try:
        t = time.perf_counter()
        embedding = embed_text(normalized)
        metrics["embedding_ms"] = round((time.perf_counter() - t) * 1000, 2)

        t = time.perf_counter()
        where = {"course_id": {"$in": [str(x) for x in ids_key]}} if ids_key is not None else None
        count = collection.count()
        if count:
            result = collection.query(
                query_embeddings=[embedding],
                n_results=min(6, count),
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        else:
            result = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        metrics["vector_search_ms"] = round((time.perf_counter() - t) * 1000, 2)

        results = []
        if result["documents"] and result["documents"][0]:
            seen = set()
            for doc, metadata, distance in zip(
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
            ):
                title = doc.split(". ", 1)[0]
                key = (title, metadata.get("course_id"))
                if key in seen or float(distance) > 0.72:
                    continue
                seen.add(key)
                results.append({
                    "title": title,
                    "content": doc[:8000],
                    "type": metadata.get("type", "resource"),
                    "course_id": int(metadata.get("course_id", 0)),
                    "distance": round(float(distance), 4),
                })
        if not results:
            t = time.perf_counter()
            results = _lexical_search(normalized, _resources(ids_key))
            metrics["context_build_ms"] = round((time.perf_counter() - t) * 1000, 2)
        metrics["total_ms"] = round((time.perf_counter() - started) * 1000, 2)
        _cache[cache_key] = (time.monotonic(), results, metrics)
        if len(_cache) > 512:
            _cache.pop(next(iter(_cache)))
        return results, metrics
    except Exception:
        metrics["total_ms"] = round((time.perf_counter() - started) * 1000, 2)
        resources = _resources(ids_key)
        results = _lexical_search(normalized, resources)
        _cache[cache_key] = (time.monotonic(), results, metrics)
        return results, metrics


def search_resources(query, course_ids=None):
    return search_resources_detailed(query, course_ids)[0]
