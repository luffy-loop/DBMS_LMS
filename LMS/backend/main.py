import re
import asyncio
import os
import time
import logging
import json
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pypdf import PdfReader
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from passlib.context import CryptContext
from jose import jwt
from bson import ObjectId
from database import Base, engine, get_db
from models import User, Course, Enrollment, Assignment, Submission
from schemas import Register, Login, CourseCreate, CourseUpdate, EnrollmentCreate, AssignmentCreate, SubmissionCreate, AdminUserCreate, AdminRoleUpdate
from auth import get_user, key, alg
from mongodb import mongo_db
from notifications import router as notifications_router
from notification_service import notify_users
from learning_insights import router as learning_router
from study_copilot import router as copilot_router
from quiz_generator import router as quiz_router
from teacher_insights import router as teacher_insights_router
from analytics import router as analytics_router
from exam_evaluation import router as exam_router, evaluate_and_record_exam
from material_service import build_metadata, duplicate_hash, prepare_resource, validate_file
from materials import router as materials_router, _process_and_notify
from audit_log import router as audit_router, record_audit

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lms.api")

app = FastAPI(title="LMS")

@app.on_event("startup")
async def startup():
    run_db_setup = os.getenv(
        "RUN_DB_SETUP",
        "true" if os.getenv("ENVIRONMENT", "development").lower() == "production" or os.getenv("RENDER_GIT_COMMIT") else "false",
    ).lower() == "true"
    if not run_db_setup:
        return

    def run_migrations():
        from alembic import command
        from alembic.config import Config
        command.upgrade(Config("alembic.ini"), "head")

    await asyncio.to_thread(run_migrations)
    try:
        mongo_db.resources.create_index("assignment_id")
        mongo_db.resources.create_index("course_id")
        mongo_db.submission_files.create_index("submission_id")
        mongo_db.resources.create_index("processing_status")
        mongo_db.resources.create_index([("course_id", 1), ("sha256", 1)], unique=False)
    except Exception as exc:
        logger.warning("Optional MongoDB indexes unavailable: %s", exc)

slow_request_ms = float(os.getenv("SLOW_REQUEST_MS", "150"))
max_upload_mb = max(1, int(os.getenv("MAX_UPLOAD_MB", "10")))
max_upload_bytes = max_upload_mb * 1024 * 1024
cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,https://frontend-5fcio5bcj-poojasrikandhula-6164s-projects.vercel.app,https://frontend-plum-mu-90.vercel.app,https://frontend-poojasrikandhula-6164s-projects.vercel.app,https://frontend-git-main-poojasrikandhula-6164s-projects.vercel.app"
    ).split(",")
    if origin.strip()
]

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    request.state.request_id = request_id
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time * 1000:.2f}ms"
    log_event = {
        "event": "http_request",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": response.status_code,
        "duration_ms": round(process_time * 1000, 2),
    }
    if process_time * 1000 > slow_request_ms:
        log_event["slow"] = True
    logger.info(json.dumps(log_event, separators=(",", ":")))
    return response

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": "Request validation failed", "errors": exc.errors()},
    )

@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database operation failed")
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    return JSONResponse(
        status_code=503,
        content={
            "detail": {
                "error": "DATABASE_UNAVAILABLE",
                "message": "The LMS database is temporarily unavailable. Please retry.",
                "request_id": request_id,
            }
        },
        headers={"X-Request-ID": request_id},
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled application error")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(learning_router)
app.include_router(copilot_router)
app.include_router(quiz_router)
app.include_router(teacher_insights_router)
app.include_router(analytics_router)
app.include_router(exam_router)
app.include_router(notifications_router)
app.include_router(materials_router)
app.include_router(audit_router)


pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
LOGIN_DUMMY_HASH = pwd.hash(os.getenv("AUTH_DUMMY_PASSWORD", "lms-dummy-password"))

@app.get("/")
def home():
    return {"message": "LMS Backend Running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/health/ready")
def readiness():
    checks = {"postgres": False, "mongodb": False}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = True
    except Exception:
        pass
    try:
        mongo_db.command("ping")
        checks["mongodb"] = True
    except Exception:
        pass
    if not all(checks.values()):
        raise HTTPException(status_code=503, detail={"error": "DEPENDENCIES_UNAVAILABLE", "checks": checks})
    return {"status": "ready", "checks": checks}

@app.post("/register")
async def register(data: Register, db: Session = Depends(get_db)):
    t0 = time.perf_counter()
    user = db.query(User).filter(User.email == data.roll_no).first()
    if user:
        raise HTTPException(status_code=400, detail="Roll number already registered")
    if data.role != "student":
        raise HTTPException(status_code=403, detail="Only students can self-register. Teacher accounts are created by an administrator.")
    section = "Unassigned"
    password_hash = await asyncio.to_thread(pwd.hash, data.password)
    user = User(name=data.name, email=data.roll_no, password=password_hash, role=data.role, section=section)
    db.add(user)
    db.commit()
    db.refresh(user)
    dur = (time.perf_counter() - t0) * 1000
    logger.info(f"[AUTH] Register for user={user.id} ({user.role}) took {dur:.2f}ms")
    return {"message": "User registered successfully", "id": user.id, "role": user.role}

@app.post("/login")
def login(data: Login, request: Request, db: Session = Depends(get_db)):
    started = time.perf_counter()
    timings = {}
    status = "database_failure"

    try:
        acquire_started = time.perf_counter()
        try:
            db.connection()
        finally:
            timings["db_connection_acquire_ms"] = round((time.perf_counter() - acquire_started) * 1000, 2)

        query_started = time.perf_counter()
        user = db.query(User).filter(User.email == data.roll_no).first()
        timings["user_query_ms"] = round((time.perf_counter() - query_started) * 1000, 2)

        password_started = time.perf_counter()
        stored_hash = user.password if user else LOGIN_DUMMY_HASH
        valid = pwd.verify(data.password, stored_hash)
        timings["password_verification_ms"] = round((time.perf_counter() - password_started) * 1000, 2)
        if not user or not valid:
            status = "invalid_credentials"
            raise HTTPException(status_code=401, detail="Invalid roll number or password")

        jwt_started = time.perf_counter()
        token = jwt.encode({"id": user.id, "role": user.role}, key, algorithm=alg)
        timings["jwt_generation_ms"] = round((time.perf_counter() - jwt_started) * 1000, 2)

        audit_started = time.perf_counter()
        try:
            record_audit(db, user.id, "login", "user", user.id, {"role": user.role}, raise_on_error=True)
        except Exception:
            timings["audit_persistence_ms"] = round((time.perf_counter() - audit_started) * 1000, 2)
            status = "audit_persistence_failure"
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "AUDIT_UNAVAILABLE",
                    "message": "Login could not be completed because the security audit could not be persisted. Please retry.",
                },
            )
        timings["audit_persistence_ms"] = round((time.perf_counter() - audit_started) * 1000, 2)
        status = "success"
        return {"message": "Login successful", "token": token, "id": user.id, "name": user.name, "role": user.role}
    except SQLAlchemyError:
        status = "database_failure"
        raise
    except HTTPException:
        if status == "database_failure" and "user_query_ms" in timings:
            status = "request_rejected"
        raise
    finally:
        timings["total_login_ms"] = round((time.perf_counter() - started) * 1000, 2)
        logger.info(json.dumps({
            "event": "login_timing",
            "request_id": getattr(request.state, "request_id", None),
            "status": status,
            "timings_ms": timings,
        }, separators=(",", ":")))

@app.get("/auth/session")
def auth_session(request: Request, user=Depends(get_user), db: Session = Depends(get_db)):
    started = time.perf_counter()
    acquire_started = time.perf_counter()
    db.connection()
    acquire_ms = round((time.perf_counter() - acquire_started) * 1000, 2)
    query_started = time.perf_counter()
    account = db.query(User).filter(User.id == user["id"]).first()
    query_ms = round((time.perf_counter() - query_started) * 1000, 2)
    if not account:
        logger.info(json.dumps({
            "event": "auth_session_timing",
            "request_id": getattr(request.state, "request_id", None),
            "status": "account_missing",
            "db_connection_acquire_ms": acquire_ms,
            "user_query_ms": query_ms,
            "total_ms": round((time.perf_counter() - started) * 1000, 2),
        }, separators=(",", ":")))
        raise HTTPException(status_code=401, detail="Account no longer exists")
    logger.info(json.dumps({
        "event": "auth_session_timing",
        "request_id": getattr(request.state, "request_id", None),
        "status": "success",
        "db_connection_acquire_ms": acquire_ms,
        "user_query_ms": query_ms,
        "total_ms": round((time.perf_counter() - started) * 1000, 2),
    }, separators=(",", ":")))
    return {"id": account.id, "name": account.name, "role": account.role}

@app.get("/profile")
def profile(request: Request, user=Depends(get_user), db: Session = Depends(get_db)):
    started = time.perf_counter()
    acquire_started = time.perf_counter()
    db.connection()
    acquire_ms = round((time.perf_counter() - acquire_started) * 1000, 2)
    profile_work_started = time.perf_counter()
    account = db.query(User).filter(User.id == user["id"]).first()
    if not account:
        raise HTTPException(status_code=404, detail="Profile not found")
    if account.role == "student":
        course_rows = db.query(Course).join(Enrollment, Enrollment.course_id == Course.id).filter(Enrollment.student_id == account.id).all()
        ids = [c.id for c in course_rows]
        assignments = db.query(Assignment).filter(Assignment.course_id.in_(ids)).all() if ids else []
    elif account.role == "teacher":
        course_rows = db.query(Course).filter(Course.teacher_id == account.id).all()
        assignments = db.query(Assignment).filter(Assignment.teacher_id == account.id).all()
    else:
        course_rows = db.query(Course).all()
        assignments = db.query(Assignment).all()
    
    course_map = {c.id: c.title for c in course_rows}
    missing_cids = [a.course_id for a in assignments if a.course_id not in course_map]
    if missing_cids:
        for cid, ctitle in db.query(Course.id, Course.title).filter(Course.id.in_(missing_cids)).all():
            course_map[cid] = ctitle

    now = get_now()
    upcoming = []
    for a in assignments:
        deadline = assessment_deadline(a)
        if deadline and deadline > now:
            c_title = course_map.get(a.course_id, "Course")
            upcoming.append({"id": a.id, "title": a.title, "type": a.type, "course": c_title, "start_time": format_iso(a.start_time), "deadline": format_iso(deadline)})
    upcoming.sort(key=lambda x: x["deadline"])
    logger.info(json.dumps({
        "event": "profile_timing",
        "request_id": getattr(request.state, "request_id", None),
        "status": "success",
        "db_connection_acquire_ms": acquire_ms,
        "profile_queries_and_projection_ms": round((time.perf_counter() - profile_work_started) * 1000, 2),
        "total_ms": round((time.perf_counter() - started) * 1000, 2),
    }, separators=(",", ":")))
    return {"id": account.id, "name": account.name, "email": account.email, "role": account.role, "section": account.section or "Unassigned", "courses": [{"id": c.id, "title": c.title, "description": c.description} for c in course_rows], "upcoming": upcoming[:6]}

@app.get("/student")
def student(user=Depends(get_user)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    return {"message": "Welcome Student", "user": user["id"]}

@app.get("/teacher")
def teacher(user=Depends(get_user)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")
    return {"message": "Welcome Teacher", "user": user["id"]}

@app.get("/teacher/overview")
def teacher_overview(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")
    courses = db.query(Course.id).filter(Course.teacher_id == user["id"]).all()
    course_ids = [c[0] for c in courses]
    asgn_rows = db.query(Assignment.id).filter(Assignment.teacher_id == user["id"]).all()
    asgn_ids = [a[0] for a in asgn_rows]
    assessments = len(asgn_ids)
    if asgn_ids:
        submissions = db.query(Submission.id).filter(Submission.assignment_id.in_(asgn_ids)).count()
        pending = db.query(Submission.id).filter(Submission.marks == None, Submission.assignment_id.in_(asgn_ids)).count()
    else:
        submissions = 0
        pending = 0
    try:
        pdfs = mongo_db.resources.count_documents({"teacher_id": user["id"], "assignment_id": {"$exists": False}})
    except Exception:
        pdfs = 0
    return {"courses": len(course_ids), "assessments": assessments, "course_pdfs": pdfs, "submissions": submissions, "pending_grading": pending}

@app.get("/admin")
def admin(user=Depends(get_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    return {"message": "Welcome Admin", "user": user["id"]}

@app.post("/courses")
def create_course(data: CourseCreate, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")
    course = Course(title=data.title, description=data.description, teacher_id=user["id"])
    db.add(course)
    db.commit()
    db.refresh(course)
    record_audit(db, user["id"], "course_created", "course", course.id, {"title": course.title})
    return {"message": "Course created", "id": course.id, "title": course.title}


@app.put("/courses/{course_id}")
def update_course(course_id: int, data: CourseUpdate, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in ["teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Teacher or admin access only")
    query = db.query(Course).filter(Course.id == course_id)
    if user["role"] == "teacher":
        query = query.filter(Course.teacher_id == user["id"])
    course = query.first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    title = data.title.strip()
    description = data.description.strip()
    if not title or not description:
        raise HTTPException(status_code=400, detail="Course title and description are required")
    course.title = title
    course.description = description
    db.commit()
    student_ids = [row[0] for row in db.query(Enrollment.student_id).filter(Enrollment.course_id == course.id).all()]
    notify_users(db, student_ids, "course_update", "Course updated", f"{course.title} was updated.", "course", course.id)
    record_audit(db, user["id"], "course_updated", "course", course.id, {"title": course.title})
    return {"message": "Course updated", "id": course.id, "title": course.title, "description": course.description}


@app.get("/courses")
def get_courses(page: int = 1, page_size: int = 50, db: Session = Depends(get_db)):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    return (
        db.query(Course)
        .order_by(Course.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

@app.post("/enroll")
def enroll(data: EnrollmentCreate, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    course = db.query(Course).filter(Course.id == data.course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    old = db.query(Enrollment).filter(Enrollment.student_id == user["id"], Enrollment.course_id == data.course_id).first()
    if old:
        raise HTTPException(status_code=400, detail="Already enrolled")
    enrollment = Enrollment(student_id=user["id"], course_id=data.course_id)
    db.add(enrollment)
    db.commit()
    record_audit(db, user["id"], "enrollment_created", "course", course.id, {"student_id": user["id"]})
    return {"message": "Enrolled successfully", "course_id": course.id}

@app.get("/my-courses")
def my_courses(user=Depends(get_user), db: Session = Depends(get_db)):
    t0 = time.perf_counter()
    if user["role"] == "student":
        rows = db.query(Course).join(Enrollment, Enrollment.course_id == Course.id).filter(Enrollment.student_id == user["id"]).all()
    elif user["role"] == "teacher":
        rows = db.query(Course).filter(Course.teacher_id == user["id"]).all()
    elif user["role"] == "admin":
        rows = db.query(Course).all()
    else:
        raise HTTPException(status_code=403, detail="Access denied")
    dur = (time.perf_counter() - t0) * 1000
    logger.info(f"[COURSES] my_courses for user={user['id']} ({user['role']}, count={len(rows)}) took {dur:.2f}ms")
    return rows

@app.post("/assignments")
async def create_assignment(
    course_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    type: str = Form("assignment"),
    start_time: datetime | None = Form(None),
    end_time: datetime | None = Form(None),
    duration_minutes: int | None = Form(None),
    reference_answer: str = Form(""),
    max_marks: int = Form(10),
    marking_criteria: str = Form(""),
    file: UploadFile | None = File(None),
    user=Depends(get_user),
    db: Session = Depends(get_db)
):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")
    if type not in ["assignment", "test", "exam"]:
        raise HTTPException(status_code=400, detail="Invalid assessment type")
    if start_time and end_time and end_time <= start_time:
        raise HTTPException(status_code=400, detail="Due time must be after start time")
    if duration_minutes is not None and duration_minutes <= 0:
        raise HTTPException(status_code=400, detail="Duration must be greater than zero")
    if duration_minutes is not None and not start_time:
        raise HTTPException(status_code=400, detail="Start time is required when duration is set")

    reference_answer = (reference_answer or "").strip()
    criteria = [line.strip() for line in (marking_criteria or "").splitlines() if line.strip()]
    if reference_answer and (max_marks < 1 or max_marks > 100):
        raise HTTPException(status_code=400, detail="AI-assisted correction maximum marks must be between 1 and 100")
    if len(reference_answer) > 10000:
        raise HTTPException(status_code=400, detail="Reference answer must be 10,000 characters or fewer")
    if len(criteria) > 20 or any(len(line) > 300 for line in criteria):
        raise HTTPException(status_code=400, detail="Provide at most 20 marking criteria, each no longer than 300 characters")
    if criteria and not reference_answer:
        raise HTTPException(status_code=400, detail="Add a reference answer before adding marking criteria")

    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == user["id"]).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    file_data = None
    file_content = ""
    if file:
        file_data, file_content = await read_pdf_upload(file)

    assignment = Assignment(
        title=title,
        description=description,
        course_id=course.id,
        teacher_id=user["id"],
        type=type,
        start_time=normalize_datetime(start_time),
        end_time=normalize_datetime(end_time),
        duration_minutes=duration_minutes
    )
    db.add(assignment)
    db.flush()

    ai_question_id = None
    if reference_answer:
        from models import AssessmentQuestion, AssessmentQuestionRubric
        ai_question = AssessmentQuestion(
            assignment_id=assignment.id,
            question_text=description.strip() or title.strip(),
            question_type="descriptive",
            max_marks=max_marks,
            order_index=0,
            reference_answer=reference_answer,
        )
        db.add(ai_question)
        db.flush()
        ai_question_id = ai_question.id
        if criteria:
            criterion_marks = float(max_marks) / len(criteria)
            for idx, criterion in enumerate(criteria):
                db.add(AssessmentQuestionRubric(
                    question_id=ai_question.id,
                    criterion_text=criterion,
                    max_marks=criterion_marks,
                    order_index=idx,
                ))
    db.commit()
    db.refresh(assignment)

    if file_data:
        await asyncio.to_thread(
            mongo_db.resources.insert_one,
            {
                "course_id": course.id,
                "assignment_id": assignment.id,
                "title": file.filename or "Assignment Handout",
                "filename": file.filename or "handout.pdf",
                "content_type": "application/pdf",
                "content": file_content,
                "teacher_id": user["id"],
                "file": file_data,
                "created_at": datetime.utcnow()
            }
        )

    student_ids = [row[0] for row in db.query(Enrollment.student_id).filter(Enrollment.course_id == course.id).all()]
    notify_users(db, student_ids, "assignment_created", f"New assessment", f"{assignment.title} was added to {course.title}.", "assignment", assignment.id)
    record_audit(db, user["id"], "assignment_created", "assignment", assignment.id, {"course_id": course.id, "type": type})

    return {"message": "Assessment created", "id": assignment.id, "title": assignment.title, "ai_grading_enabled": bool(ai_question_id), "ai_question_id": ai_question_id}

def normalize_datetime(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

def get_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

get_utc_now = get_now

def extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages).strip()


def safe_upload_filename(filename: str | None, default: str = "submission.pdf") -> str:
    name = os.path.basename((filename or "").replace("\\", "/")).strip()
    name = "".join(ch for ch in name if ch.isprintable() and ch not in "\r\n\t")
    return name[:180] or default


async def read_pdf_upload(file: UploadFile) -> tuple[bytes, str]:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type not in {"", "application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="PDF uploads must use the application/pdf content type")
    data = await file.read(max_upload_bytes + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Empty PDF file")
    if len(data) > max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"PDF exceeds the {max_upload_mb} MB upload limit")
    if b"%PDF-" not in data[:1024]:
        raise HTTPException(status_code=400, detail="Invalid PDF file")
    try:
        content = await asyncio.to_thread(extract_pdf_text, data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid PDF file")
    return data, content


def read_pdf_upload_sync(file: UploadFile) -> tuple[bytes, str]:
    """Read and validate a submission PDF inside FastAPI's sync worker thread."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type not in {"", "application/pdf", "application/octet-stream"}:
        raise HTTPException(status_code=400, detail="PDF uploads must use the application/pdf content type")
    data = file.file.read(max_upload_bytes + 1)
    if not data:
        raise HTTPException(status_code=400, detail="Empty PDF file")
    if len(data) > max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"PDF exceeds the {max_upload_mb} MB upload limit")
    if b"%PDF-" not in data[:1024]:
        raise HTTPException(status_code=400, detail="Invalid PDF file")
    try:
        content = extract_pdf_text(data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid PDF file")
    return data, content


def format_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    norm = normalize_datetime(dt)
    return norm.isoformat()

format_iso_utc = format_iso

def assessment_deadline(assignment):
    deadlines = []
    end = normalize_datetime(assignment.end_time)
    start = normalize_datetime(assignment.start_time)
    if end:
        deadlines.append(end)
    if start and assignment.duration_minutes and assignment.type in {"test", "exam"}:
        deadlines.append(start + timedelta(minutes=assignment.duration_minutes))
    return min(deadlines) if deadlines else None

def assessment_status(assignment):
    now = get_now()
    start = normalize_datetime(assignment.start_time)
    if start and now < start:
        return "upcoming"
    deadline = assessment_deadline(assignment)
    if deadline and now >= deadline:
        return "closed"
    return "open"

def db_submission_exists(assignment_id, student_id, db: Session | None = None):
    if db is not None:
        return db.query(Submission.id).filter(Submission.assignment_id == assignment_id, Submission.student_id == student_id).first() is not None
    from database import SessionLocal
    db_local = SessionLocal()
    try:
        return db_local.query(Submission.id).filter(Submission.assignment_id == assignment_id, Submission.student_id == student_id).first() is not None
    finally:
        db_local.close()

def assessment_payload(assignment, student_id=None, db: Session | None = None):
    handout = None
    try:
        handout = mongo_db.resources.find_one(
            {"assignment_id": assignment.id},
            {"_id": 1, "title": 1, "filename": 1}
        )
    except Exception:
        handout = None
    return {
        "id": assignment.id,
        "title": assignment.title,
        "description": assignment.description,
        "course_id": assignment.course_id,
        "teacher_id": assignment.teacher_id,
        "type": assignment.type,
        "start_time": format_iso(assignment.start_time),
        "end_time": format_iso(assignment.end_time),
        "duration_minutes": assignment.duration_minutes,
        "deadline": format_iso(assessment_deadline(assignment)),
        "status": assessment_status(assignment),
        "submitted": bool(student_id and db_submission_exists(assignment.id, student_id, db)),
        "handout": {
            "id": str(handout["_id"]),
            "title": handout.get("title", ""),
            "filename": handout.get("filename", "")
        } if handout else None
    }

@app.get("/my-assignments")
def my_assignments(user=Depends(get_user), db: Session = Depends(get_db)):
    t0 = time.perf_counter()
    if user["role"] == "student":
        enrollments = db.query(Enrollment.course_id).filter(Enrollment.student_id == user["id"]).all()
        cids = [e[0] for e in enrollments]
    elif user["role"] == "teacher":
        courses = db.query(Course.id).filter(Course.teacher_id == user["id"]).all()
        cids = [c[0] for c in courses]
    elif user["role"] == "admin":
        courses = db.query(Course.id).all()
        cids = [c[0] for c in courses]
    else:
        raise HTTPException(status_code=403, detail="Access denied")

    if not cids:
        return []

    assignments = db.query(Assignment).filter(Assignment.course_id.in_(cids)).all()
    if not assignments:
        return []

    asgn_ids = [a.id for a in assignments]
    submitted_ids = set()
    if user["role"] == "student":
        subs = db.query(Submission.assignment_id).filter(
            Submission.assignment_id.in_(asgn_ids),
            Submission.student_id == user["id"]
        ).all()
        submitted_ids = {s[0] for s in subs}

    handouts_map = {}
    try:
        handouts = mongo_db.resources.find(
            {"assignment_id": {"$in": asgn_ids}},
            {"_id": 1, "assignment_id": 1, "title": 1, "filename": 1}
        )
        for h in handouts:
            asgn_id = h.get("assignment_id")
            if asgn_id:
                handouts_map[asgn_id] = {
                    "id": str(h["_id"]),
                    "title": h.get("title", ""),
                    "filename": h.get("filename", "")
                }
    except Exception:
        handouts_map = {}

    dur = (time.perf_counter() - t0) * 1000
    logger.info(f"[ASSIGNMENTS] my_assignments for user={user['id']} ({user['role']}, count={len(assignments)}) took {dur:.2f}ms")

    return [{
        "id": a.id,
        "title": a.title,
        "description": a.description,
        "course_id": a.course_id,
        "teacher_id": a.teacher_id,
        "type": a.type,
        "start_time": format_iso(a.start_time),
        "end_time": format_iso(a.end_time),
        "duration_minutes": a.duration_minutes,
        "deadline": format_iso(assessment_deadline(a)),
        "status": assessment_status(a),
        "submitted": a.id in submitted_ids,
        "handout": handouts_map.get(a.id)
    } for a in assignments]

@app.get("/assignments/{course_id}")
def get_assignments(course_id: int, user=Depends(get_user), db: Session = Depends(get_db)):
    t0 = time.perf_counter()
    if user["role"] not in ["student", "teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    if user["role"] == "student":
        if not db.query(Enrollment.id).filter(Enrollment.student_id == user["id"], Enrollment.course_id == course_id).first():
            raise HTTPException(status_code=403, detail="You are not enrolled in this course")
    elif user["role"] == "teacher":
        if not db.query(Course.id).filter(Course.id == course_id, Course.teacher_id == user["id"]).first():
            raise HTTPException(status_code=403, detail="You can only access your own course")
    
    assignments = db.query(Assignment).filter(Assignment.course_id == course_id).all()
    if not assignments:
        return []

    asgn_ids = [a.id for a in assignments]
    submitted_ids = set()
    if user["role"] == "student":
        subs = db.query(Submission.assignment_id).filter(
            Submission.assignment_id.in_(asgn_ids),
            Submission.student_id == user["id"]
        ).all()
        submitted_ids = {s[0] for s in subs}

    handouts_map = {}
    try:
        handouts = mongo_db.resources.find(
            {"assignment_id": {"$in": asgn_ids}},
            {"_id": 1, "assignment_id": 1, "title": 1, "filename": 1}
        )
        for h in handouts:
            asgn_id = h.get("assignment_id")
            if asgn_id:
                handouts_map[asgn_id] = {
                    "id": str(h["_id"]),
                    "title": h.get("title", ""),
                    "filename": h.get("filename", "")
                }
    except Exception:
        handouts_map = {}

    dur = (time.perf_counter() - t0) * 1000
    logger.info(f"[ASSIGNMENTS] List for course={course_id} user={user['id']} (count={len(assignments)}) took {dur:.2f}ms")

    return [{
        "id": a.id,
        "title": a.title,
        "description": a.description,
        "course_id": a.course_id,
        "teacher_id": a.teacher_id,
        "type": a.type,
        "start_time": format_iso(a.start_time),
        "end_time": format_iso(a.end_time),
        "duration_minutes": a.duration_minutes,
        "deadline": format_iso(assessment_deadline(a)),
        "status": assessment_status(a),
        "submitted": a.id in submitted_ids,
        "handout": handouts_map.get(a.id)
    } for a in assignments]

@app.post("/submissions")
def submit_assignment(
    assignment_id: int = Form(...),
    answer: str = Form(""),
    answers_json: str | None = Form(None),
    file: UploadFile | None = File(None),
    user=Depends(get_user),
    db: Session = Depends(get_db)
):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    enrollment = db.query(Enrollment.id).filter(Enrollment.student_id == user["id"], Enrollment.course_id == assignment.course_id).first()
    if not enrollment:
        raise HTTPException(status_code=403, detail="You must be enrolled in this course to submit")

    now = get_now()
    start = normalize_datetime(assignment.start_time)
    if start and now < start:
        raise HTTPException(status_code=400, detail="This assessment is not open yet")
    deadline = assessment_deadline(assignment)
    if deadline and now >= deadline:
        raise HTTPException(status_code=400, detail="Submission deadline has passed")

    old = db.query(Submission).filter(
        Submission.assignment_id == assignment.id,
        Submission.student_id == user["id"]
    ).first()
    if old:
        raise HTTPException(status_code=400, detail="You have already submitted this assessment")

    file_data = None
    if file:
        file_data, file_content = read_pdf_upload_sync(file)

    if not answer.strip() and not file_data and not answers_json:
        raise HTTPException(status_code=400, detail="Write an answer, select options, or upload a PDF")

    from models import AssessmentQuestion
    assessment_questions = db.query(AssessmentQuestion).filter(
        AssessmentQuestion.assignment_id == assignment.id
    ).order_by(AssessmentQuestion.order_index, AssessmentQuestion.id).all()
    has_questions = bool(assessment_questions)

    if answers_json or has_questions:
        import json
        try:
            answers_map = parse_question_answers(answers_json, {question.id for question in assessment_questions})
            answers_map, _mapping_status = map_pdf_answers(
                assessment_questions, answers_map, answer, file_content if file_data else "",
                readable_pdf=(len((file_content or "").split()) >= 2) if file_data else None,
            )
        except ValueError as exc:
            detail = str(exc)
            if "cannot be mapped reliably" in detail:
                raise HTTPException(status_code=400, detail={
                    "error": "QUESTION_MAPPING_REQUIRED",
                    "message": detail + " No submission has been recorded; the selected PDF remains available for retry.",
                }) from exc
            raise HTTPException(status_code=400, detail=detail) from exc

        try:
            submission, recorded = evaluate_and_record_exam(assignment, user["id"], answers_map, db)
        except HTTPException as exc:
            if exc.status_code == 500 and db.query(Submission.id).filter(
                Submission.assignment_id == assignment.id,
                Submission.student_id == user["id"],
            ).first():
                raise HTTPException(status_code=409, detail="You have already submitted this assessment") from exc
            raise
        if answer.strip():
            submission.answer = answer.strip()
            db.commit()
    else:
        submission = Submission(
            assignment_id=assignment.id,
            student_id=user["id"],
            answer=answer.strip()
        )
        db.add(submission)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            if db.query(Submission.id).filter(
                Submission.assignment_id == assignment.id,
                Submission.student_id == user["id"],
            ).first():
                raise HTTPException(status_code=409, detail="You have already submitted this assessment") from exc
            raise
        db.refresh(submission)

    if file_data:
        try:
            mongo_db.submission_files.insert_one(
                {
                    "submission_id": submission.id,
                    "assignment_id": assignment.id,
                    "student_id": user["id"],
                    "filename": safe_upload_filename(file.filename),
                    "content_type": "application/pdf",
                    "file": file_data,
                    "created_at": datetime.utcnow()
                }
            )
        except Exception:
            logger.exception("Submission PDF storage failed submission_id=%s", submission.id)
            mongo_cleanup_ok = True
            try:
                mongo_db.submission_files.delete_many(
                    {"submission_id": submission.id}
                )
            except Exception:
                mongo_cleanup_ok = False
                logger.exception("Submission PDF compensation failed submission_id=%s", submission.id)
            db_cleanup_ok = True
            try:
                from models import StudentQuestionAnswer
                db.query(StudentQuestionAnswer).filter(
                    StudentQuestionAnswer.submission_id == submission.id
                ).delete(synchronize_session=False)
                db.query(Submission).filter(Submission.id == submission.id).delete(synchronize_session=False)
                db.commit()
            except Exception:
                db.rollback()
                db_cleanup_ok = False
                logger.exception("Submission database compensation failed submission_id=%s", submission.id)
            if mongo_cleanup_ok and db_cleanup_ok:
                raise HTTPException(
                    status_code=503,
                    detail={
                        "error": "SUBMISSION_STORAGE_FAILED",
                        "message": "PDF storage failed and the submission was rolled back. Please retry."
                    },
                )
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "SUBMISSION_RECONCILIATION_REQUIRED",
                    "message": "PDF storage failed and automatic cleanup could not be confirmed. Contact the course teacher before retrying."
                },
            )

    notify_users(db, [assignment.teacher_id], "submission_received", "New submission", f"A student submitted {assignment.title}.")
    return {"message": "Submission successful", "id": submission.id, "marks": submission.marks if submission.marks_published else None, "marks_published": bool(submission.marks_published), "grading_status": "published" if submission.marks_published else ("awaiting_publication" if submission.marks is not None else "awaiting_grading"), "submitted_at": submission.created_at.isoformat() if submission.created_at else None}

def parse_question_answers(raw_answers: str | None, valid_question_ids: set[int]) -> dict[int, dict]:
    if not raw_answers:
        return {}
    try:
        items = json.loads(raw_answers)
    except (TypeError, ValueError) as exc:
        raise ValueError("answers_json must be valid JSON") from exc
    if not isinstance(items, list):
        raise ValueError("answers_json must be a JSON array")
    parsed = {}
    for item in items:
        if not isinstance(item, dict) or not item.get("question_id"):
            raise ValueError("Each answer must include question_id")
        try:
            qid = int(item["question_id"])
        except (TypeError, ValueError) as exc:
            raise ValueError("Question IDs must be integers") from exc
        if qid not in valid_question_ids:
            raise ValueError(f"Question {qid} does not belong to this assessment")
        if qid in parsed:
            raise ValueError(f"Duplicate answer submitted for question {qid}")
        answer_text = item.get("student_answer", "")
        if answer_text is not None and not isinstance(answer_text, str):
            raise ValueError(f"Answer for question {qid} must be text")
        parsed[qid] = {"selected_option_id": item.get("selected_option_id"), "student_answer": answer_text or ""}
    return parsed


def map_pdf_answers(questions, answers_map, written_answer, pdf_text, readable_pdf: bool | None = None):
    def field(question, name):
        return question.get(name) if isinstance(question, dict) else getattr(question, name)
    mapped = {int(field(q, "id")): dict(answers_map.get(int(field(q, "id")), {})) for q in questions}
    extracted = (pdf_text or "").strip()
    readable = len(extracted.split()) >= 2 if readable_pdf is None else readable_pdf
    if len(questions) == 1 and field(questions[0], "question_type") == "descriptive":
        qid = int(field(questions[0], "id"))
        row = mapped.setdefault(qid, {})
        if not (row.get("student_answer") or "").strip():
            if (written_answer or "").strip():
                row["student_answer"] = written_answer.strip()
                return mapped, "mapped"
            if readable:
                row["student_answer"] = extracted
                return mapped, "mapped"
            row["manual_review_required"] = True
            return mapped, "manual_review"
        return mapped, "question_answer"
    if not readable:
        for question in questions:
            if field(question, "question_type") == "descriptive":
                qid = int(field(question, "id"))
                row = mapped.setdefault(qid, {})
                if not (row.get("student_answer") or "").strip():
                    row["manual_review_required"] = True
        return mapped, "manual_review"
    missing = [
        int(field(question, "id")) for question in questions
        if len(questions) > 1
        and field(question, "question_type") == "descriptive"
        and not (mapped.get(int(field(question, "id")), {}).get("student_answer") or "").strip()
    ]
    if missing:
        raise ValueError("Readable PDF cannot be mapped reliably to multiple questions; provide question-wise answers. Missing question IDs: " + str(missing))
    return mapped, "question_wise"


def submission_payload(submission, db: Session | None = None):
    file_doc = None
    try:
        file_doc = mongo_db.submission_files.find_one(
            {"submission_id": submission.id},
            {"_id": 1, "filename": 1}
        )
    except Exception:
        file_doc = None
    from models import StudentQuestionAnswer
    close_db = False
    if db is None:
        from database import SessionLocal
        db = SessionLocal()
        close_db = True

    max_marks = None
    asgn_title = None
    student_name = None
    try:
        asgn = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
        if asgn:
            asgn_title = asgn.title
        student = db.query(User).filter(User.id == submission.student_id).first()
        if student:
            student_name = student.name
        sqas = db.query(StudentQuestionAnswer).filter(StudentQuestionAnswer.submission_id == submission.id).all()
        if sqas:
            max_marks = sum(s.max_marks for s in sqas)
    finally:
        if close_db:
            db.close()

    return {
        "id": submission.id,
        "assignment_id": submission.assignment_id,
        "assignment_title": asgn_title,
        "student_id": submission.student_id,
        "student_name": student_name,
        "answer": submission.answer,
        "marks": submission.marks,
        "marks_published": bool(submission.marks_published),
        "teacher_review_note": submission.teacher_review_note,
        "review_status": "published" if submission.marks_published else ("awaiting_publication" if submission.marks is not None else "awaiting_grading"),
        "submitted_at": submission.created_at.isoformat() if submission.created_at else None,
        "max_marks": max_marks,
        "file_id": str(file_doc["_id"]) if file_doc else None,
        "file_name": file_doc.get("filename", "") if file_doc else None
    }

def build_submission_payloads(submissions: list[Submission], db: Session) -> list[dict]:
    if not submissions:
        return []

    sub_ids = [s.id for s in submissions]
    asgn_ids = list({s.assignment_id for s in submissions})
    student_ids = list({s.student_id for s in submissions})

    assignments = {a[0]: a[1] for a in db.query(Assignment.id, Assignment.title).filter(Assignment.id.in_(asgn_ids)).all()}
    students = {u[0]: u[1] for u in db.query(User.id, User.name).filter(User.id.in_(student_ids)).all()}

    from models import StudentQuestionAnswer
    sqa_sums = dict(
        db.query(StudentQuestionAnswer.submission_id, func.sum(StudentQuestionAnswer.max_marks))
        .filter(StudentQuestionAnswer.submission_id.in_(sub_ids))
        .group_by(StudentQuestionAnswer.submission_id)
        .all()
    )

    files_map = {}
    try:
        file_docs = mongo_db.submission_files.find(
            {"submission_id": {"$in": sub_ids}},
            {"_id": 1, "submission_id": 1, "filename": 1}
        )
        for f in file_docs:
            files_map[f["submission_id"]] = f
    except Exception:
        files_map = {}

    results = []
    for s in submissions:
        f_doc = files_map.get(s.id)
        max_m = sqa_sums.get(s.id)
        if max_m is not None:
            max_m = int(max_m)
        results.append({
            "id": s.id,
            "assignment_id": s.assignment_id,
            "assignment_title": assignments.get(s.assignment_id),
            "student_id": s.student_id,
            "student_name": students.get(s.student_id),
            "answer": s.answer,
            "marks": s.marks,
            "marks_published": bool(s.marks_published),
            "teacher_review_note": s.teacher_review_note,
            "review_status": "published" if s.marks_published else ("awaiting_publication" if s.marks is not None else "awaiting_grading"),
            "submitted_at": s.created_at.isoformat() if s.created_at else None,
            "max_marks": max_m,
            "file_id": str(f_doc["_id"]) if f_doc else None,
            "file_name": f_doc.get("filename", "") if f_doc else None
        })
    return results

@app.get("/my-submissions")
def my_submissions(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    subs = db.query(Submission).filter(Submission.student_id == user["id"]).order_by(Submission.id.desc()).all()
    results = build_submission_payloads(subs, db)
    for item, submission in zip(results, subs):
        if not submission.marks_published:
            item["marks"] = None
            item["teacher_review_note"] = None
            item["marks_status"] = "awaiting_publication" if submission.marks is not None else "awaiting_grading"
        else:
            item["marks_status"] = "published"
            item["percentage"] = round((submission.marks / item["max_marks"]) * 100, 1) if submission.marks is not None and item.get("max_marks") else None
    return results

@app.get("/teacher/assignments/{assignment_id}/report")
def teacher_assessment_report(
    assignment_id: int,
    response_format: str = "json",
    section: str | None = None,
    user=Depends(get_user),
    db: Session = Depends(get_db),
):
    if user["role"] not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Teacher or admin access only")
    if response_format not in {"json", "csv"}:
        raise HTTPException(status_code=400, detail="response_format must be json or csv")

    from models import AssessmentQuestion, StudentQuestionAnswer

    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if user["role"] == "teacher" and assignment.teacher_id != user["id"]:
        raise HTTPException(status_code=403, detail="You can only view reports for your own assessments")

    available_sections = [
        row[0] for row in (
            db.query(User.section)
            .join(Enrollment, Enrollment.student_id == User.id)
            .filter(Enrollment.course_id == assignment.course_id, User.role == "student")
            .distinct()
            .order_by(User.section)
            .all()
        ) if row[0]
    ]
    enrolled_query = (
        db.query(User.id, User.name, User.email, User.section)
        .join(Enrollment, Enrollment.student_id == User.id)
        .filter(Enrollment.course_id == assignment.course_id)
    )
    if section is not None:
        enrolled_query = enrolled_query.filter(User.section == section)
    enrolled = enrolled_query.order_by(User.id).all()
    submissions = db.query(Submission).filter(Submission.assignment_id == assignment.id).all()
    submission_by_student = {item.student_id: item for item in submissions}
    submission_files = {}
    try:
        file_docs = mongo_db.submission_files.find(
            {"submission_id": {"$in": [item.id for item in submissions]}},
            {"_id": 1, "submission_id": 1, "filename": 1},
        ) if submissions else []
        submission_files = {doc["submission_id"]: doc for doc in file_docs}
    except Exception:
        logger.warning("Unable to load submission file metadata for assessment report id=%s", assignment.id)
    questions = (
        db.query(AssessmentQuestion)
        .filter(AssessmentQuestion.assignment_id == assignment.id)
        .order_by(AssessmentQuestion.order_index, AssessmentQuestion.id)
        .all()
    )
    question_ids = [question.id for question in questions]
    submission_ids = [item.id for item in submissions]
    answer_rows = (
        db.query(StudentQuestionAnswer)
        .filter(
            StudentQuestionAnswer.submission_id.in_(submission_ids),
            StudentQuestionAnswer.question_id.in_(question_ids),
        )
        .all()
        if submission_ids and question_ids else []
    )
    answers_by_submission = {}
    for row in answer_rows:
        answers_by_submission.setdefault(row.submission_id, {})[row.question_id] = row

    maximum = sum(question.max_marks for question in questions) if questions else 100
    from exam_evaluation import low_score_threshold
    threshold = low_score_threshold()
    students = []
    for student_id, student_name, email, section_name in enrolled:
        submission = submission_by_student.get(student_id)
        answer_map = answers_by_submission.get(submission.id, {}) if submission else {}
        question_report = []
        for question in questions:
            row = answer_map.get(question.id)
            evaluation = None
            if row and row.rubric_evaluation:
                try:
                    evaluation = json.loads(row.rubric_evaluation)
                except (TypeError, ValueError):
                    evaluation = None
            criteria = evaluation.get("criteria", []) if isinstance(evaluation, dict) else []
            matched = sorted({
                str(term)
                for criterion in criteria if isinstance(criterion, dict)
                for term in (criterion.get("matched_concepts") or [])
                if isinstance(term, (str, int, float))
            })
            missing = sorted({
                str(term)
                for criterion in criteria if isinstance(criterion, dict)
                for term in (criterion.get("missing_concepts") or [])
                if isinstance(term, (str, int, float))
            })
            question_report.append({
                "question_id": question.id,
                "question": question.question_text,
                "reference_answer": question.reference_answer,
                "max_marks": question.max_marks,
                "student_answer": row.student_answer if row else None,
                "selected_option_id": row.selected_option_id if row else None,
                "awarded_marks": (
                    row.teacher_override_marks if row and row.teacher_override_marks is not None
                    else row.awarded_marks if row else None
                ),
                "feedback": (
                    row.teacher_review_note if row and row.teacher_review_note
                    else (evaluation.get("feedback") or evaluation.get("summary")) if isinstance(evaluation, dict)
                    else None
                ),
                "matched_concepts": matched,
                "missing_concepts": missing,
                "review_status": row.review_status if row else ("not_submitted" if not submission else "not_recorded"),
                "evaluation_status": row.evaluation_status if row else None,
            })
        rows = list(answer_map.values())
        suggested = sum(
            float(row.teacher_override_marks if row.teacher_override_marks is not None else row.awarded_marks)
            for row in rows
        ) if rows else None
        saved_marks = submission.marks if submission else None
        percentage_basis = saved_marks if saved_marks is not None else suggested
        percentage = round((percentage_basis / maximum) * 100, 1) if percentage_basis is not None and maximum > 0 else None
        teacher_has_reviewed_all = bool(rows) and all(row.review_status in {"reviewed", "published"} for row in rows)
        needs_review = bool(submission and (
            any(
                (row.review_status in {"needs_review", "evaluation_failed"} or row.evaluation_status == "evaluation_failed")
                and row.review_status not in {"reviewed", "published"}
                for row in rows
            )
            or (rows and percentage is not None and percentage < threshold and not teacher_has_reviewed_all)
        ))
        if not submission:
            review_status = "not_submitted"
        elif submission.marks_published:
            review_status = "published"
        elif needs_review:
            review_status = "needs_review"
        elif rows and all(row.review_status in {"reviewed", "published"} for row in rows):
            review_status = "teacher_reviewed"
        elif rows and any(row.review_status in {"ai_evaluated", "auto_finalized"} for row in rows):
            review_status = "ai_evaluated"
        elif saved_marks is not None:
            review_status = "awaiting_publication"
        else:
            review_status = "awaiting_grading"
        students.append({
            "student_id": student_id,
            "student_name": student_name,
            "student_email": email,
            "section": section_name or "Unassigned",
            "submission_id": submission.id if submission else None,
            "answer": submission.answer if submission else None,
            "file_id": str(submission_files[submission.id]["_id"]) if submission and submission.id in submission_files else None,
            "file_name": submission_files[submission.id].get("filename", "") if submission and submission.id in submission_files else None,
            "submission_status": "submitted" if submission else "not_submitted",
            "submitted_at": submission.created_at.isoformat() if submission and submission.created_at else None,
            "grading_status": review_status,
            "review_status": review_status,
            "marks_status": "published" if submission and submission.marks_published else ("awaiting_publication" if saved_marks is not None else ("awaiting_grading" if submission else "not_submitted")),
            "saved_marks": saved_marks,
            "suggested_marks": round(suggested, 2) if suggested is not None else None,
            "total_marks": saved_marks if submission and submission.marks_published else None,
            "max_marks": maximum,
            "percentage": percentage if submission and submission.marks_published else None,
            "needs_review": needs_review,
            "questions": question_report,
        })

    def count_status(*statuses):
        return sum(1 for item in students if item["review_status"] in statuses)
    report = {
        "assignment": {"id": assignment.id, "title": assignment.title, "course_id": assignment.course_id},
        "sections": available_sections,
        "enrolled_students": len(enrolled),
        "submitted_students": sum(1 for item in students if item["submission_status"] == "submitted"),
        "not_submitted_students": sum(1 for item in students if item["submission_status"] == "not_submitted"),
        "awaiting_grading": count_status("awaiting_grading"),
        "ai_evaluated": count_status("ai_evaluated"),
        "needs_review": count_status("needs_review"),
        "teacher_reviewed": count_status("teacher_reviewed"),
        "published": count_status("published"),
        "evaluation_failures": sum(1 for item in students if any(q["evaluation_status"] == "evaluation_failed" for q in item["questions"])),
        "low_score_threshold_percent": threshold,
        "students": students,
    }
    if response_format == "json":
        return report

    import csv
    from io import StringIO
    course_row = db.query(Course).filter(Course.id == assignment.course_id).first()
    course_title = course_row.title if course_row else str(assignment.course_id)

    def safe_csv_cell(value):
        if value is None:
            return ""
        text_value = str(value)
        if text_value.lstrip()[:1] in {"=", "+", "-", "@"}:
            return "'" + text_value
        return text_value

    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=[
        "Course", "Section", "Assessment", "Roll Number", "Student Name",
        "Submission Status", "Marks Obtained", "Maximum Marks", "Grading Status",
        "Student ID", "Assessment ID", "Submitted At",
    ], lineterminator="\r\n")
    writer.writeheader()
    for student in students:
        obtained = student["saved_marks"]
        writer.writerow({
            "Course": safe_csv_cell(course_title),
            "Section": safe_csv_cell(student["section"]),
            "Assessment": safe_csv_cell(assignment.title),
            "Roll Number": safe_csv_cell(student["student_email"]),
            "Student Name": safe_csv_cell(student["student_name"]),
            "Submission Status": student["submission_status"].replace("_", " ").title(),
            "Marks Obtained": "" if obtained is None else obtained,
            "Maximum Marks": student["max_marks"],
            "Grading Status": student["grading_status"].replace("_", " ").title(),
            "Student ID": student["student_id"],
            "Assessment ID": assignment.id,
            "Submitted At": student["submitted_at"] or "",
        })
    filename_base = re.sub(r"[^A-Za-z0-9_-]+", "_", assignment.title).strip("_") or f"assessment_{assignment.id}"
    section_suffix = f"_section_{re.sub(r'[^A-Za-z0-9_-]+', '_', section).strip('_')}" if section else ""
    filename = f"{filename_base}{section_suffix}_marks.csv"
    return StreamingResponse(
        iter(["\ufeff" + output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/teacher/submissions")
def get_submissions(pending_only: bool = False, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")
    asgn_rows = db.query(Assignment.id).filter(Assignment.teacher_id == user["id"]).all()
    asgn_ids = [a[0] for a in asgn_rows]
    if not asgn_ids:
        return []
    query = db.query(Submission).filter(Submission.assignment_id.in_(asgn_ids))
    if pending_only:
        query = query.filter(Submission.marks == None)
    subs = query.order_by(Submission.id.desc()).all()
    return build_submission_payloads(subs, db)

@app.put("/submissions/{submission_id}/marks")
def give_marks(submission_id: int, marks: float, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")
    submission = db.query(Submission).filter(Submission.id == submission_id).with_for_update().first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id, Assignment.teacher_id == user["id"]).first()
    if not assignment:
        raise HTTPException(status_code=403, detail="You can only grade your own assessments")
    from models import StudentQuestionAnswer
    rows = db.query(StudentQuestionAnswer).filter(StudentQuestionAnswer.submission_id == submission.id).all()
    maximum = sum(row.max_marks for row in rows) if rows else 100
    if marks < 0 or marks > maximum:
        raise HTTPException(status_code=400, detail=f"Marks must be between 0 and the maximum ({maximum})")
    submission.marks = round(float(marks), 2)
    submission.marks_published = False
    submission.graded_by = user["id"]
    submission.graded_at = get_now()
    db.commit()
    record_audit(db, user["id"], "grading_saved_unpublished", "submission", submission.id, {"assignment_id": assignment.id, "marks": marks, "max_marks": maximum})
    return {"message": "Marks saved. Publish the result when review is complete.", "submission_id": submission.id, "marks": marks, "marks_published": False}

@app.post("/submissions/{submission_id}/publish")
def publish_submission(submission_id: int, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="Teacher or admin access only")
    submission = db.query(Submission).filter(Submission.id == submission_id).with_for_update().first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if user["role"] == "teacher" and assignment.teacher_id != user["id"]:
        raise HTTPException(status_code=403, detail="You can only publish results for your own assessments")
    if submission.marks is None:
        raise HTTPException(status_code=409, detail="Save a final mark before publishing")
    from models import StudentQuestionAnswer
    rows = db.query(StudentQuestionAnswer).filter(StudentQuestionAnswer.submission_id == submission.id).all()
    if rows and any(row.review_status not in {"reviewed", "published"} for row in rows):
        raise HTTPException(status_code=409, detail="Review every question before publishing this result")
    if not submission.marks_published:
        submission.marks_published = True
        db.commit()
        notify_users(db, [submission.student_id], "marks_published", "Marks published", f"Marks for {assignment.title} are now available.", "assignment", assignment.id)
        record_audit(db, user["id"], "grading_published", "submission", submission.id, {"assignment_id": assignment.id, "marks": submission.marks})
    return {"message": "Marks published", "submission_id": submission.id, "marks": submission.marks, "marks_published": True}

@app.get("/my-marks")
def my_marks(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    subs = db.query(Submission).filter(Submission.student_id == user["id"]).order_by(Submission.id.desc()).all()
    results = build_submission_payloads(subs, db)
    for item, submission in zip(results, subs):
        if not submission.marks_published:
            item["marks"] = None
            item["marks_status"] = "awaiting_publication" if submission.marks is not None else "awaiting_grading"
        else:
            item["marks_status"] = "published"
            item["percentage"] = round((submission.marks / item["max_marks"]) * 100, 1) if submission.marks is not None and item.get("max_marks") else None
    return results

@app.post("/courses/{course_id}/resources/batch")
async def add_resources_batch(course_id: int, background_tasks: BackgroundTasks, files: list[UploadFile] = File(...), titles: list[str] | None = Form(None), user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "teacher": raise HTTPException(status_code=403, detail="Teacher access only")
    course=db.query(Course).filter(Course.id==course_id,Course.teacher_id==user["id"]).first()
    if not course: raise HTTPException(status_code=404,detail="Course not found")
    if not files: raise HTTPException(status_code=400,detail="Select at least one file")
    if len(files)>20: raise HTTPException(status_code=400,detail="Maximum 20 files per upload batch")
    results=[]
    for index,file in enumerate(files):
        try:
            data=await file.read(max_upload_bytes+1)
            if len(data)>max_upload_bytes: raise HTTPException(status_code=413,detail=f"File exceeds the {max_upload_mb} MB limit")
            suffix=validate_file(file.filename or "",file.content_type or "",data)
            title=titles[index] if titles and index<len(titles) else ""
            meta=build_metadata(file,data,course_id,user["id"],title)
            duplicate=duplicate_hash(course_id,meta["sha256"])
            if duplicate: raise HTTPException(status_code=409,detail=f"Duplicate file already exists: {duplicate.get('filename','file')}")
            insert=await asyncio.to_thread(mongo_db.resources.insert_one,meta)
            resource_id=str(insert.inserted_id)
            background_tasks.add_task(_process_and_notify,resource_id)
            record_audit(db, user["id"], "material_uploaded", "resource", resource_id, {"course_id": course_id, "filename": meta["filename"]})
            results.append({"id":resource_id,"filename":meta["filename"],"title":meta["title"],"status":"UPLOADED","extension":suffix})
        except HTTPException as exc:
            results.append({"filename":file.filename or "file","status":"FAILED","error":str(exc.detail)})
        except Exception as exc:
            logger.exception("Upload failed for %s",file.filename)
            results.append({"filename":file.filename or "file","status":"FAILED","error":str(exc)[:300]})
    return {"course_id":course_id,"files":results}


@app.post("/courses/{course_id}/resources")
async def add_resource(course_id:int,background_tasks:BackgroundTasks,file:UploadFile=File(...),title:str=Form(""),user=Depends(get_user),db:Session=Depends(get_db)):
    result=await add_resources_batch(course_id,background_tasks,[file],[title],user,db)
    first=result["files"][0]
    if first.get("status")=="FAILED":
        raise HTTPException(status_code=409 if "Duplicate" in str(first.get("error")) else 400,detail=first.get("error","Upload failed"))
    return {"message":"Learning material uploaded",**first}


@app.get("/my-course-resources")
def my_course_resources(user=Depends(get_user),db:Session=Depends(get_db)):
    if user["role"]=="student": cids=[e[0] for e in db.query(Enrollment.course_id).filter(Enrollment.student_id==user["id"]).all()]
    elif user["role"]=="teacher": cids=[c[0] for c in db.query(Course.id).filter(Course.teacher_id==user["id"]).all()]
    elif user["role"]=="admin": cids=[c[0] for c in db.query(Course.id).all()]
    else: raise HTTPException(status_code=403,detail="Access denied")
    if not cids:return {}
    resources=mongo_db.resources.find({"course_id":{"$in":cids},"assignment_id":{"$exists":False}}).sort("created_at",-1)
    result={}
    for r in resources:
        result.setdefault(r["course_id"],[]).append({"id":str(r["_id"]),"title":r.get("title",""),"filename":r.get("filename",""),"content_type":r.get("content_type",""),"size":r.get("size",0),"created_at":r.get("created_at"),"processing_status":r.get("processing_status","UPLOADED"),"extraction_status":r.get("extraction_status","PENDING"),"indexing_status":r.get("indexing_status","PENDING"),"error_message":r.get("error_message"),"page_count":r.get("page_count"),"slide_count":r.get("slide_count"),"ocr_status":r.get("ocr_status")})
    return result


@app.get("/courses/{course_id}/resources")
def get_resources(course_id:int,user=Depends(get_user),db:Session=Depends(get_db)):
    if user["role"] not in ["student","teacher","admin"]: raise HTTPException(status_code=403,detail="Access denied")
    if user["role"]=="student" and not db.query(Enrollment.id).filter(Enrollment.student_id==user["id"],Enrollment.course_id==course_id).first(): raise HTTPException(status_code=403,detail="You are not enrolled in this course")
    if user["role"]=="teacher" and not db.query(Course.id).filter(Course.id==course_id,Course.teacher_id==user["id"]).first(): raise HTTPException(status_code=403,detail="You can only access your own course")
    resources=mongo_db.resources.find({"course_id":course_id,"assignment_id":{"$exists":False}}).sort("created_at",-1)
    return [{"id":str(r["_id"]),"title":r.get("title",""),"filename":r.get("filename",""),"content_type":r.get("content_type",""),"size":r.get("size",0),"created_at":r.get("created_at"),"processing_status":r.get("processing_status","UPLOADED"),"extraction_status":r.get("extraction_status","PENDING"),"indexing_status":r.get("indexing_status","PENDING"),"error_message":r.get("error_message"),"page_count":r.get("page_count"),"slide_count":r.get("slide_count"),"ocr_status":r.get("ocr_status")} for r in resources]


@app.get("/resources/{resource_id}/status")
def resource_status(resource_id:str,user=Depends(get_user),db:Session=Depends(get_db)):
    try: resource=mongo_db.resources.find_one({"_id":ObjectId(resource_id)})
    except Exception: raise HTTPException(status_code=400,detail="Invalid resource id")
    if not resource: raise HTTPException(status_code=404,detail="Resource not found")
    course_id=resource.get("course_id")
    if user["role"]=="student" and not db.query(Enrollment.id).filter(Enrollment.student_id==user["id"],Enrollment.course_id==course_id).first(): raise HTTPException(status_code=403,detail="Access denied")
    if user["role"]=="teacher" and resource.get("teacher_id")!=user["id"]: raise HTTPException(status_code=403,detail="Access denied")
    return {"id":resource_id,"status":resource.get("processing_status","UPLOADED"),"extraction_status":resource.get("extraction_status","PENDING"),"indexing_status":resource.get("indexing_status","PENDING"),"error_message":resource.get("error_message")}


@app.get("/resources/{resource_id}/download")
def download_resource(resource_id:str,user=Depends(get_user),db:Session=Depends(get_db)):
    if user["role"] not in ["student","teacher","admin"]: raise HTTPException(status_code=403,detail="Access denied")
    try: resource=mongo_db.resources.find_one({"_id":ObjectId(resource_id)})
    except Exception: raise HTTPException(status_code=400,detail="Invalid resource id")
    if not resource: raise HTTPException(status_code=404,detail="Resource not found")
    course_id=resource.get("course_id")
    if user["role"]=="student" and not db.query(Enrollment.id).filter(Enrollment.student_id==user["id"],Enrollment.course_id==course_id).first(): raise HTTPException(status_code=403,detail="Access denied")
    if user["role"]=="teacher" and resource.get("teacher_id")!=user["id"]: raise HTTPException(status_code=403,detail="Access denied")
    return StreamingResponse(iter([resource["file"]]),media_type=resource.get("content_type","application/octet-stream"),headers={"Content-Disposition":f'inline; filename="{resource.get("filename","resource")}"'})


@app.get("/submissions/{submission_id}/download")
def download_submission(submission_id: int, user=Depends(get_user), db: Session = Depends(get_db)):
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if user["role"] == "student":
        if submission.student_id != user["id"]:
            raise HTTPException(status_code=403, detail="Access denied")
    elif user["role"] == "teacher":
        assignment = db.query(Assignment.id).filter(Assignment.id == submission.assignment_id, Assignment.teacher_id == user["id"]).first()
        if not assignment:
            raise HTTPException(status_code=403, detail="Access denied")
    elif user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    resource = mongo_db.submission_files.find_one({"submission_id": submission.id})
    if not resource:
        raise HTTPException(status_code=404, detail="Submission file not found")
    safe_name = os.path.basename(str(resource.get("filename", "submission.pdf"))).replace(chr(34), "") or "submission.pdf"
    return StreamingResponse(iter([resource["file"]]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{safe_name}"'})

@app.get("/admin/users")
def admin_users(page: int = 1, page_size: int = 50, search: str | None = None, role: str | None = None, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    query = db.query(User)
    if search and search.strip():
        term = "%" + search.strip().replace("%", "\\%").replace("_", "\\_") + "%"
        query = query.filter((User.name.ilike(term)) | (User.email.ilike(term)))
    if role:
        if role not in {"student", "teacher", "admin"}:
            raise HTTPException(status_code=422, detail="Invalid role filter")
        query = query.filter(User.role == role)
    total = query.count()
    rows = query.order_by(User.role, User.name, User.id).offset((page - 1) * page_size).limit(page_size).all()
    return {"users": [{"id": u.id, "name": u.name, "roll_no": u.email, "email": u.email, "role": u.role, "section": u.section or "Unassigned"} for u in rows], "total": total, "page": page, "page_size": page_size}

@app.post("/admin/users", status_code=201)
async def admin_create_user(data: AdminUserCreate, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    name = data.name.strip()
    roll_no = data.roll_no.strip()
    section = data.section.strip() or "Unassigned"
    if not name or not roll_no:
        raise HTTPException(status_code=422, detail="Name and roll number are required")
    if db.query(User.id).filter(User.email == roll_no).first():
        raise HTTPException(status_code=409, detail="A user with this roll number already exists")
    account = User(name=name, email=roll_no, password=await asyncio.to_thread(pwd.hash, data.password), role=data.role, section=section)
    db.add(account)
    db.commit()
    db.refresh(account)
    record_audit(db, user["id"], "admin_user_created", "user", account.id, {"role": account.role})
    return {"id": account.id, "name": account.name, "roll_no": account.email, "role": account.role, "section": account.section}

@app.patch("/admin/users/{user_id}/role")
def admin_update_user_role(user_id: int, data: AdminRoleUpdate, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    target = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == user["id"] and target.role != data.role:
        raise HTTPException(status_code=400, detail="You cannot change your own role")
    if target.role == "admin" and data.role != "admin" and db.query(User.id).filter(User.role == "admin").count() <= 1:
        raise HTTPException(status_code=409, detail="The last administrator cannot be demoted")
    old_role = target.role
    if old_role == data.role:
        return {"id": target.id, "role": target.role, "message": "Role unchanged"}
    target.role = data.role
    db.commit()
    record_audit(db, user["id"], "admin_user_role_changed", "user", target.id, {"from": old_role, "to": target.role})
    return {"id": target.id, "role": target.role, "message": "Role updated"}

@app.get("/admin/marks-overview")
def admin_marks_overview(
    course_id: int | None = None,
    section: str | None = None,
    assignment_id: int | None = None,
    status: str | None = None,
    user=Depends(get_user),
    db: Session = Depends(get_db),
):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    query = db.query(Assignment).join(Course, Course.id == Assignment.course_id)
    if course_id is not None:
        query = query.filter(Assignment.course_id == course_id)
    if assignment_id is not None:
        query = query.filter(Assignment.id == assignment_id)
    assignments = query.order_by(Assignment.course_id, Assignment.id).all()
    reports = []
    all_students = []
    for assignment in assignments:
        report = teacher_assessment_report(
            assignment.id, "json", section=section, user=user, db=db
        )
        course = db.query(Course).filter(Course.id == assignment.course_id).first()
        for student in report["students"]:
            row = {
                "student_id": student["student_id"],
                "student_name": student["student_name"],
                "student_email": student["student_email"],
                "section": student["section"],
                "submission_id": student["submission_id"],
                "submission_status": student["submission_status"],
                "submitted_at": student["submitted_at"],
                "grading_status": student["grading_status"],
                "review_status": student["review_status"],
                "marks_status": student["marks_status"],
                "saved_marks": student["saved_marks"],
                "suggested_marks": student["suggested_marks"],
                "total_marks": student["total_marks"],
                "max_marks": student["max_marks"],
                "percentage": student["percentage"],
                "needs_review": student["needs_review"],
                "course_id": assignment.course_id,
                "course_title": course.title if course else str(assignment.course_id),
                "assessment_id": assignment.id,
                "assessment_title": assignment.title,
            }
            if status and row["grading_status"] != status:
                continue
            all_students.append(row)
        reports.append({
            "assessment_id": assignment.id,
            "assessment_title": assignment.title,
            "course_id": assignment.course_id,
            "course_title": course.title if course else str(assignment.course_id),
            "enrolled_students": report["enrolled_students"],
            "submitted_students": report["submitted_students"],
            "not_submitted_students": report["not_submitted_students"],
            "awaiting_grading": report["awaiting_grading"],
            "ai_evaluated": report["ai_evaluated"],
            "needs_review": report["needs_review"],
            "teacher_reviewed": report["teacher_reviewed"],
            "published": report["published"],
            "evaluation_failures": report["evaluation_failures"],
        })
    all_courses = db.query(Course).order_by(Course.title).all()
    all_assignments = db.query(Assignment).order_by(Assignment.title).all()
    all_sections = [row[0] for row in db.query(User.section).filter(User.role == "student").distinct().order_by(User.section).all() if row[0]]
    return {
        "filters": {"course_id": course_id, "section": section, "assignment_id": assignment_id, "status": status},
        "courses": [{"id": item.id, "title": item.title} for item in all_courses],
        "sections": all_sections,
        "available_assessments": [{"id": item.id, "title": item.title, "course_id": item.course_id} for item in all_assignments],
        "assessments": reports,
        "students": all_students,
        "counts": {
            "enrolled": sum(row["enrolled_students"] for row in reports),
            "submitted": sum(row["submitted_students"] for row in reports),
            "not_submitted": sum(row["not_submitted_students"] for row in reports),
            "awaiting_grading": sum(row["awaiting_grading"] for row in reports),
            "ai_evaluated": sum(row["ai_evaluated"] for row in reports),
            "needs_review": sum(row["needs_review"] for row in reports),
            "teacher_reviewed": sum(row["teacher_reviewed"] for row in reports),
            "published": sum(row["published"] for row in reports),
            "evaluation_failures": sum(row["evaluation_failures"] for row in reports),
        },
    }


@app.get("/admin/submissions")
def admin_submissions(page: int = 1, page_size: int = 50, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    query = db.query(Submission).order_by(Submission.id.desc())
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"submissions": build_submission_payloads(rows, db), "total": total, "page": page, "page_size": page_size}

@app.put("/admin/teachers/{teacher_id}/section")
def assign_teacher_section(teacher_id: int, section: str, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    section = section.strip().upper()
    if section not in [f"A{i}" for i in range(1, 8)]:
        raise HTTPException(status_code=400, detail="Section must be A1 through A7")
    teacher = db.query(User).filter(User.id == teacher_id, User.role == "teacher").first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    teacher.section = section
    db.commit()
    return {"message": "Teacher section assigned", "teacher_id": teacher.id, "section": teacher.section}

@app.get("/admin/overview")
def admin_overview(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    role_counts = dict(db.query(User.role, func.count(User.id)).group_by(User.role).all())
    materials_count = 0
    try:
        materials_count = mongo_db.resources.count_documents({})
    except Exception:
        pass
    from models import AIJob, AuditLog
    return {"users": sum(role_counts.values()), "students": role_counts.get("student", 0), "teachers": role_counts.get("teacher", 0), "admins": role_counts.get("admin", 0), "courses": db.query(Course.id).count(), "enrollments": db.query(Enrollment.id).count(), "assignments": db.query(Assignment.id).count(), "submissions": db.query(Submission.id).count(), "materials": materials_count, "ai_jobs": db.query(AIJob.id).count(), "audit_events": db.query(AuditLog.id).count()}

@app.get("/admin/system-health")
def admin_system_health(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    postgres = False
    mongodb = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        postgres = True
    except Exception:
        pass
    try:
        mongo_db.command("ping")
        mongodb = True
    except Exception:
        pass
    return {"backend": "ok", "postgres": postgres, "mongodb": mongodb, "ai": {"mode": "local-grounded-retrieval", "configured": True}, "version": os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT") or "unknown", "runtime": os.getenv("RENDER_SERVICE_NAME") or "local"}

@app.get("/ai-search")
async def ai_search(q:str,user=Depends(get_user),db:Session=Depends(get_db)):
    if not q.strip(): raise HTTPException(status_code=400,detail="Search query cannot be empty")
    try:
        if user["role"]=="student": course_ids=[e.course_id for e in db.query(Enrollment).filter(Enrollment.student_id==user["id"]).all()]
        elif user["role"]=="teacher": course_ids=[c.id for c in db.query(Course.id).filter(Course.teacher_id==user["id"]).all()]
        elif user["role"]=="admin": course_ids=None
        else: raise HTTPException(status_code=403,detail="Access denied")
        started=time.perf_counter()
        from vector_store import search_resources_detailed
        results,metrics=await asyncio.wait_for(asyncio.to_thread(search_resources_detailed,q,course_ids),timeout=15)
        metrics["total_ms"]=round((time.perf_counter()-started)*1000,2)
        return {"query":q,"results":results,"metrics":metrics}
    except asyncio.TimeoutError: raise HTTPException(status_code=504,detail={"error":"AI_TIMEOUT","message":"Search took too long. Please retry."})
    except HTTPException: raise
    except Exception:
        logger.exception("Search service failed")
        raise HTTPException(status_code=503,detail={"error":"SEARCH_UNAVAILABLE","message":"Search service unavailable. Please retry."})
