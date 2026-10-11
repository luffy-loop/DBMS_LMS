import asyncio
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from auth import get_user
from database import SessionLocal
from models import Enrollment, Course
from mongodb import mongo_db
from material_service import prepare_resource
from notification_service import notify_users

router = APIRouter(prefix="/resources", tags=["resources"])
PROCESSING_LEASE_SECONDS = max(60, int(os.getenv("RESOURCE_PROCESSING_LEASE_SECONDS", "600")))


async def _process_and_notify(resource_id: str):
    """Claim and process one resource; expired leases can be reclaimed after restarts."""
    try:
        object_id = ObjectId(resource_id)
    except Exception:
        return False

    now = datetime.utcnow()
    stale_before = now - timedelta(seconds=PROCESSING_LEASE_SECONDS)
    claim_filter = {
        "_id": object_id,
        "$or": [
            {"processing_status": "UPLOADED"},
            {"processing_status": "PROCESSING", "processing_lease_until": {"$lt": now}},
            {
                "processing_status": "PROCESSING",
                "processing_lease_until": {"$exists": False},
                "updated_at": {"$lt": stale_before},
            },
        ],
    }
    claimed = await asyncio.to_thread(
        mongo_db.resources.find_one_and_update,
        claim_filter,
        {
            "$set": {
                "processing_status": "PROCESSING",
                "processing_started_at": now,
                "processing_lease_until": now + timedelta(seconds=PROCESSING_LEASE_SECONDS),
                "updated_at": now,
            },
            "$inc": {"processing_attempts": 1},
        },
        return_document=ReturnDocument.AFTER,
    )
    if not claimed:
        return False

    if not await asyncio.to_thread(prepare_resource, resource_id):
        return False

    try:
        resource = await asyncio.to_thread(mongo_db.resources.find_one, {"_id": object_id})
        if not resource:
            return True
        db = SessionLocal()
        try:
            ids = [
                row[0]
                for row in db.query(Enrollment.student_id)
                .filter(Enrollment.course_id == resource.get("course_id"))
                .all()
            ]
            course = db.query(Course).filter(Course.id == resource.get("course_id")).first()
            if ids and course:
                notify_users(
                    db, ids, "material_uploaded", "New learning material",
                    resource.get("title", "Learning material") + " is ready in " + course.title + ".",
                    "resource", resource_id,
                )
        finally:
            db.close()
    except Exception:
        # Notifications are secondary; a ready resource must not be downgraded.
        import logging
        logging.getLogger("lms.materials").exception("Resource is ready but notification failed: %s", resource_id)
    return True


@router.post("/{resource_id}/retry")
async def retry_resource(
    resource_id: str,
    background_tasks: BackgroundTasks,
    user=Depends(get_user),
):
    try:
        resource = mongo_db.resources.find_one({"_id": ObjectId(resource_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid resource id")
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    if user["role"] not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Access denied")
    if user["role"] == "teacher" and resource.get("teacher_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    status = resource.get("processing_status")
    lexical_retry = status == "READY" and resource.get("indexing_status") == "LEXICAL_ONLY"
    if status == "UPLOADED":
        return {"id": resource_id, "status": "UPLOADED", "message": "Processing is already queued"}
    if status != "FAILED" and not lexical_retry:
        raise HTTPException(status_code=409, detail="Only failed materials or lexical-only resources can be retried")

    updates = {"processing_status": "UPLOADED", "error_message": None, "updated_at": datetime.utcnow()}
    if resource.get("course_id") is not None and resource.get("sha256"):
        updates["active_content_key"] = f'{resource["course_id"]}:{resource["sha256"]}'
    try:
        result = mongo_db.resources.update_one(
            {"_id": resource["_id"], "processing_status": status, "indexing_status": resource.get("indexing_status")},
            {"$set": updates},
        )
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="An identical material is already active in this course")
    if not result.modified_count:
        raise HTTPException(status_code=409, detail="Resource state changed; refresh its status before retrying")
    background_tasks.add_task(_process_and_notify, resource_id)
    return {"id": resource_id, "status": "UPLOADED"}
