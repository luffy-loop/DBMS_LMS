import chromadb
from functools import lru_cache
from mongodb import mongo_db

client = chromadb.PersistentClient(path="./vector_data")
collection = client.get_or_create_collection("lms_resources")

@lru_cache(maxsize=1)
def get_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("all-MiniLM-L6-v2")

def _sync_resources(resources):
    if not resources:
        return
    model = get_model()
    ids, docs, metas, embeddings = [], [], [], []
    for item in resources:
        ids.append(str(item["id"]))
        docs.append(f'{item["title"]}. {item["content"]}')
        metas.append({"type": item["type"], "course_id": str(item["course_id"])})
        embeddings.append(model.encode(docs[-1]).tolist())
    collection.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)

def search_resources(query, course_ids=None):
    from database import SessionLocal
    from models import Course
    db = SessionLocal()
    try:
        resources = []
        course_query = db.query(Course)
        if course_ids is not None:
            course_query = course_query.filter(Course.id.in_(course_ids)) if course_ids else course_query.filter(False)
        for course in course_query.all():
            resources.append({"id": f"course-{course.id}", "title": course.title, "content": course.description, "type": "course", "course_id": course.id})
        resource_query = {"course_id": {"$in": course_ids}} if course_ids is not None else {}
        for resource in mongo_db.resources.find(resource_query):
            resources.append({"id": f"resource-{resource['_id']}", "title": resource.get("title", ""), "content": resource.get("content", ""), "type": "resource", "course_id": resource.get("course_id", 0)})
        _sync_resources(resources)
        if not resources:
            return []
        model = get_model()
        kwargs = {"query_embeddings":[model.encode(query).tolist()],"n_results":min(8,len(resources)),"include":["documents","metadatas","distances"]}
        if course_ids is not None and course_ids:
            kwargs["where"] = {"course_id":{"$in":[str(x) for x in course_ids]}}
        result = collection.query(**kwargs)
        return [{
            "title": doc.split(". ", 1)[0],
            "content": doc,
            "type": result["metadatas"][0][i]["type"],
            "course_id": int(result["metadatas"][0][i]["course_id"]),
            "distance": round(float(result["distances"][0][i]), 4)
        } for i, doc in enumerate(result["documents"][0])]
    finally:
        db.close()
