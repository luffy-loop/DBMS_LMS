import asyncio
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from bson import ObjectId

from auth import get_user
from database import SessionLocal
from models import Enrollment, Course
from mongodb import mongo_db
from material_service import prepare_resource
from notification_service import notify_users

router=APIRouter(prefix="/resources",tags=["resources"])


async def _process_and_notify(resource_id:str):
    if not await asyncio.to_thread(prepare_resource,resource_id): return
    try:
        resource=await asyncio.to_thread(mongo_db.resources.find_one,{"_id":ObjectId(resource_id)})
        if not resource:return
        db=SessionLocal()
        try:
            ids=[row[0] for row in db.query(Enrollment.student_id).filter(Enrollment.course_id==resource.get("course_id")).all()]
            course=db.query(Course).filter(Course.id==resource.get("course_id")).first()
            if ids and course:
                notify_users(db,ids,"material_uploaded","New learning material",resource.get("title","Learning material")+" is ready in "+course.title+".","resource",resource_id)
        finally: db.close()
    except Exception: pass


@router.post("/{resource_id}/retry")
async def retry_resource(resource_id:str,background_tasks:BackgroundTasks,user=Depends(get_user)):
    try: resource=mongo_db.resources.find_one({"_id":ObjectId(resource_id)})
    except Exception: raise HTTPException(status_code=400,detail="Invalid resource id")
    if not resource: raise HTTPException(status_code=404,detail="Resource not found")
    if user["role"]!="admin" and resource.get("teacher_id")!=user["id"]:
        raise HTTPException(status_code=403,detail="Access denied")
    if resource.get("processing_status") not in {"FAILED","UPLOADED"}:
        raise HTTPException(status_code=409,detail="Only failed or pending materials can be retried")
    mongo_db.resources.update_one({"_id":resource["_id"]},{"$set":{"processing_status":"UPLOADED","error_message":None}})
    background_tasks.add_task(_process_and_notify,resource_id)
    return {"id":resource_id,"status":"UPLOADED"}
