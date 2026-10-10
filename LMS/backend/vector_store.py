import re
import time
from functools import lru_cache

import chromadb
from bson import ObjectId

from mongodb import mongo_db

client = chromadb.PersistentClient(path="./vector_data")
collection = client.get_or_create_collection("lms_resources")
CACHE_TTL = 45
_cache = {}
_vectors_reconciled = False
VECTOR_PAGE_SIZE = 100


@lru_cache(maxsize=32)
def _embed_text(text):
    from evaluation_service import generate_embedding
    return generate_embedding(text)


def embed_text(text):
    # Truncate before caching so long extracted documents are not retained as cache keys.
    return _embed_text((text or "")[:2000])


def clear_search_cache():
    _cache.clear()


def prune_orphaned_resource_vectors():
    """Remove indexed material vectors whose source documents no longer exist."""
    global _vectors_reconciled
    if _vectors_reconciled:
        return

    vector_ids = []
    offset = 0
    try:
        while True:
            page = collection.get(
                where={"type": "resource"},
                include=["metadatas"],
                limit=VECTOR_PAGE_SIZE,
                offset=offset,
            )
            ids = page.get("ids") or []
            vector_ids.extend(ids)
            if len(ids) < VECTOR_PAGE_SIZE:
                break
            offset += len(ids)

        valid_object_ids = []
        for vector_id in vector_ids:
            raw_id = vector_id.removeprefix("resource-")
            try:
                valid_object_ids.append((vector_id, ObjectId(raw_id)))
            except Exception:
                continue

        existing = set()
        for start in range(0, len(valid_object_ids), VECTOR_PAGE_SIZE):
            batch = valid_object_ids[start:start + VECTOR_PAGE_SIZE]
            documents = mongo_db.resources.find(
                {"_id": {"$in": [object_id for _, object_id in batch]}},
                {"_id": 1},
            )
            existing.update("resource-" + str(document["_id"]) for document in documents)

        stale_ids = [
            vector_id for vector_id in vector_ids
            if not vector_id.startswith("resource-") or vector_id not in existing
        ]
        for start in range(0, len(stale_ids), VECTOR_PAGE_SIZE):
            collection.delete(ids=stale_ids[start:start + VECTOR_PAGE_SIZE])

        _vectors_reconciled = True
        if stale_ids:
            clear_search_cache()
    except Exception:
        # Never delete vectors if MongoDB cannot be checked reliably; retry on a later search.
        return


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

    prune_orphaned_resource_vectors()
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


def search_resources_for_quiz(query, course_id):
    """Retrieve processed material for one course without cold-loading the embedding model."""
    started = time.perf_counter()
    resources = _resources((course_id,))
    results = []
    seen = set()
    for item in resources:
        if item.get("type") != "resource":
            continue
        title = " ".join(str(item.get("title") or "Course material").split())
        content = " ".join(str(item.get("content") or "").split())
        if len(content) < 40:
            continue
        key = (title.lower(), content[:180].lower())
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "title": title,
            "content": (title + ". " + content)[:8000],
            "type": item.get("type", "resource"),
            "course_id": int(item.get("course_id", course_id)),
            "distance": 0.0,
        })
        if len(results) >= 20:
            break
    return results, {"mode": "course_scoped_lexical", "retrieval_ms": round((time.perf_counter() - started) * 1000, 2), "resources_considered": len(resources)}
