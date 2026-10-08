import asyncio
import os
import time
import logging
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pypdf import PdfReader
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from passlib.context import CryptContext
from jose import jwt
from bson import ObjectId
from database import Base, engine, get_db
from models import User, Course, Enrollment, Assignment, Submission
from schemas import Register, Login, CourseCreate, EnrollmentCreate, AssignmentCreate, SubmissionCreate
from auth import get_user, key, alg
from mongodb import mongo_db
from vector_store import search_resources
from learning_insights import router as learning_router
from study_copilot import router as copilot_router
from quiz_generator import router as quiz_router
from teacher_insights import router as teacher_insights_router
from analytics import router as analytics_router
from exam_evaluation import router as exam_router, evaluate_and_record_exam

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lms.api")

app = FastAPI(title="LMS")

@app.on_event("startup")
async def startup():
    if os.getenv("RUN_DB_SETUP", "false").lower() != "true":
        return
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        for stmt in (
            "CREATE INDEX IF NOT EXISTS ix_courses_teacher_id ON courses(teacher_id)",
            "CREATE INDEX IF NOT EXISTS ix_assignments_course_id ON assignments(course_id)",
            "CREATE INDEX IF NOT EXISTS ix_assignments_teacher_id ON assignments(teacher_id)",
            "CREATE INDEX IF NOT EXISTS ix_submissions_assignment_id ON submissions(assignment_id)",
            "CREATE INDEX IF NOT EXISTS ix_submissions_student_id ON submissions(student_id)",
            "CREATE INDEX IF NOT EXISTS ix_enrollments_student_course ON enrollments(student_id, course_id)",
            "CREATE INDEX IF NOT EXISTS ix_assessment_questions_assignment ON assessment_questions(assignment_id)",
            "CREATE INDEX IF NOT EXISTS ix_assessment_options_question ON assessment_question_options(question_id)",
            "CREATE INDEX IF NOT EXISTS ix_assessment_rubrics_question ON assessment_question_rubrics(question_id)",
            "CREATE INDEX IF NOT EXISTS ix_sqa_submission ON student_question_answers(submission_id)",
            "CREATE INDEX IF NOT EXISTS ix_sqa_student ON student_question_answers(student_id)",
        ):
            conn.execute(text(stmt))
        for stmt in (
            "ALTER TABLE assignments ADD COLUMN IF NOT EXISTS type VARCHAR DEFAULT 'assignment'",
            "ALTER TABLE assignments ADD COLUMN IF NOT EXISTS start_time TIMESTAMP",
            "ALTER TABLE assignments ADD COLUMN IF NOT EXISTS end_time TIMESTAMP",
            "ALTER TABLE assignments ADD COLUMN IF NOT EXISTS duration_minutes INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS section VARCHAR DEFAULT 'Unassigned'",
            "ALTER TABLE student_question_answers ADD COLUMN IF NOT EXISTS evaluator_confidence DOUBLE PRECISION",
            "ALTER TABLE student_question_answers ADD COLUMN IF NOT EXISTS review_status VARCHAR(30) DEFAULT 'auto_finalized'",
            "ALTER TABLE student_question_answers ADD COLUMN IF NOT EXISTS teacher_override_marks DOUBLE PRECISION",
            "ALTER TABLE student_question_answers ADD COLUMN IF NOT EXISTS teacher_review_note TEXT",
            "ALTER TABLE student_question_answers ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP",
            "ALTER TABLE student_question_answers ADD COLUMN IF NOT EXISTS reviewed_by INTEGER REFERENCES users(id) ON DELETE SET NULL",
        ):
            conn.execute(text(stmt))
    try:
        mongo_db.resources.create_index("assignment_id")
        mongo_db.resources.create_index("course_id")
        mongo_db.submission_files.create_index("submission_id")
    except Exception as exc:
        logger.warning("Optional MongoDB indexes unavailable: %s", exc)

Base.metadata.create_all(bind=engine)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = f"{process_time * 1000:.2f}ms"
    if process_time > 0.15:
        logger.info(f"Slow request: {request.method} {request.url.path} took {process_time*1000:.2f}ms")
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
LOGIN_DUMMY_HASH = pwd.hash(os.getenv("AUTH_DUMMY_PASSWORD", "lms-dummy-password"))

@app.get("/")
def home():
    return {"message": "LMS Backend Running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/register")
async def register(data: Register, db: Session = Depends(get_db)):
    t0 = time.perf_counter()
    user = db.query(User).filter(User.email == data.roll_no).first()
    if user:
        raise HTTPException(status_code=400, detail="Roll number already registered")
    if data.role not in ["student", "teacher", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
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
async def login(data: Login, db: Session = Depends(get_db)):
    t0 = time.perf_counter()
    user = db.query(User).filter(User.email == data.roll_no).first()
    stored_hash = user.password if user else LOGIN_DUMMY_HASH
    valid = await asyncio.to_thread(pwd.verify, data.password, stored_hash)
    if not user or not valid:
        raise HTTPException(status_code=401, detail="Invalid roll number or password")
    token = jwt.encode({"id": user.id, "role": user.role}, key, algorithm=alg)
    dur = (time.perf_counter() - t0) * 1000
    logger.info(f"[AUTH] Login for user={user.id} ({user.role}) took {dur:.2f}ms")
    return {"message": "Login successful", "token": token, "id": user.id, "name": user.name, "role": user.role}

@app.get("/profile")
def profile(user=Depends(get_user), db: Session = Depends(get_db)):
    t0 = time.perf_counter()
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
    return {"message": "Course created", "id": course.id, "title": course.title}

@app.get("/courses")
def get_courses(db: Session = Depends(get_db)):
    return db.query(Course).all()

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
    file: UploadFile | None = File(None),
    user=Depends(get_user),
    db: Session = Depends(get_db)
):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")
    if type not in ["assignment", "test", "exam"]:
        raise HTTPException(status_code=400, detail="Invalid assessment type")
    if start_time and end_time and end_time <= start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")
    if duration_minutes is not None and duration_minutes <= 0:
        raise HTTPException(status_code=400, detail="Duration must be greater than zero")
    if duration_minutes and not start_time:
        raise HTTPException(status_code=400, detail="Start time is required when duration is set")

    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == user["id"]).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    file_data = None
    if file:
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        file_data = await file.read()
        if not file_data:
            raise HTTPException(status_code=400, detail="Empty PDF file")
        try:
            PdfReader(BytesIO(file_data))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid PDF file")

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
    db.commit()
    db.refresh(assignment)

    if file_data:
        try:
            reader = PdfReader(BytesIO(file_data))
            content = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
        except Exception:
            content = ""
        mongo_db.resources.insert_one({
            "course_id": course.id,
            "assignment_id": assignment.id,
            "title": file.filename or "Assignment Handout",
            "filename": file.filename or "handout.pdf",
            "content_type": "application/pdf",
            "content": content,
            "teacher_id": user["id"],
            "file": file_data,
            "created_at": datetime.utcnow()
        })

    return {"message": "Assessment created", "id": assignment.id, "title": assignment.title}

def normalize_datetime(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone().replace(tzinfo=None)
    return dt

def get_now() -> datetime:
    return datetime.now()

get_utc_now = get_now

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
    if start and assignment.duration_minutes:
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
async def submit_assignment(
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
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        file_data = await file.read()
        if not file_data:
            raise HTTPException(status_code=400, detail="Empty PDF file")
        try:
            PdfReader(BytesIO(file_data))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid PDF file")

    if not answer.strip() and not file_data and not answers_json:
        raise HTTPException(status_code=400, detail="Write an answer, select options, or upload a PDF")

    from models import AssessmentQuestion
    has_questions = db.query(AssessmentQuestion).filter(AssessmentQuestion.assignment_id == assignment.id).first() is not None

    if answers_json or has_questions:
        import json
        answers_list = []
        if answers_json:
            try:
                answers_list = json.loads(answers_json)
            except Exception:
                answers_list = []
        answers_map = {
            item.get("question_id"): {
                "selected_option_id": item.get("selected_option_id"),
                "student_answer": item.get("student_answer")
            }
            for item in answers_list if isinstance(item, dict) and item.get("question_id")
        }
        submission, recorded = evaluate_and_record_exam(assignment, user["id"], answers_map, db)
        if answer.strip():
            submission.answer = f"{answer.strip()} | {submission.answer}"
            db.commit()
    else:
        submission = Submission(
            assignment_id=assignment.id,
            student_id=user["id"],
            answer=answer.strip()
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)

    if file_data:
        mongo_db.submission_files.insert_one({
            "submission_id": submission.id,
            "assignment_id": assignment.id,
            "student_id": user["id"],
            "filename": file.filename or "submission.pdf",
            "content_type": "application/pdf",
            "file": file_data,
            "created_at": datetime.utcnow()
        })

    return {"message": "Submission successful", "id": submission.id, "marks": submission.marks}

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
    return build_submission_payloads(subs, db)

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
def give_marks(submission_id: int, marks: int, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id, Assignment.teacher_id == user["id"]).first()
    if not assignment:
        raise HTTPException(status_code=403, detail="You can only grade your own assessments")
    if marks < 0:
        raise HTTPException(status_code=400, detail="Marks cannot be negative")
    submission.marks = marks
    db.commit()
    return {"message": "Marks updated", "submission_id": submission.id, "marks": marks}

@app.get("/my-marks")
def my_marks(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    subs = db.query(Submission).filter(Submission.student_id == user["id"]).order_by(Submission.id.desc()).all()
    return build_submission_payloads(subs, db)

@app.post("/courses/{course_id}/resources")
async def add_resource(course_id: int, file: UploadFile = File(...), title: str = Form(...), user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")
    course = db.query(Course).filter(Course.id == course_id, Course.teacher_id == user["id"]).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty PDF file")

    try:
        reader = PdfReader(BytesIO(data))
        content = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    except Exception:
        content = ""

    result = mongo_db.resources.insert_one({"course_id": course_id, "title": title, "filename": file.filename, "content_type": file.content_type, "content": content, "teacher_id": user["id"], "file": data, "created_at": datetime.utcnow()})
    return {"message": "PDF uploaded", "id": str(result.inserted_id), "title": title}

@app.get("/my-course-resources")
def my_course_resources(user=Depends(get_user), db: Session = Depends(get_db)):
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
        return {}

    resources = mongo_db.resources.find(
        {"course_id": {"$in": cids}, "assignment_id": {"$exists": False}},
        {"_id": 1, "course_id": 1, "title": 1, "filename": 1, "created_at": 1}
    )
    res_map = {}
    for r in resources:
        cid = r.get("course_id")
        if cid:
            res_map.setdefault(cid, []).append({
                "id": str(r["_id"]),
                "title": r.get("title", ""),
                "filename": r.get("filename", ""),
                "created_at": r.get("created_at")
            })
    dur = (time.perf_counter() - t0) * 1000
    logger.info(f"[RESOURCES] my_course_resources for user={user['id']} ({len(cids)} courses) took {dur:.2f}ms")
    return res_map

@app.get("/courses/{course_id}/resources")
def get_resources(course_id: int, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in ["student", "teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    if user["role"] == "student":
        if not db.query(Enrollment.id).filter(Enrollment.student_id == user["id"], Enrollment.course_id == course_id).first():
            raise HTTPException(status_code=403, detail="You are not enrolled in this course")
    elif user["role"] == "teacher":
        if not db.query(Course.id).filter(Course.id == course_id, Course.teacher_id == user["id"]).first():
            raise HTTPException(status_code=403, detail="You can only access your own course")
    resources = mongo_db.resources.find(
        {"course_id": course_id, "assignment_id": {"$exists": False}},
        {"_id": 1, "title": 1, "filename": 1, "created_at": 1}
    )
    return [{"id": str(r["_id"]), "title": r.get("title", ""), "filename": r.get("filename", ""), "created_at": r.get("created_at")} for r in resources]

@app.get("/resources/{resource_id}/download")
def download_resource(resource_id: str, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in ["student", "teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        resource = mongo_db.resources.find_one({"_id": ObjectId(resource_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid resource id")
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    course_id = resource.get("course_id")
    if user["role"] == "student":
        if not db.query(Enrollment.id).filter(Enrollment.student_id == user["id"], Enrollment.course_id == course_id).first():
            raise HTTPException(status_code=403, detail="You are not enrolled in this course")
    elif user["role"] == "teacher" and resource.get("teacher_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return StreamingResponse(iter([resource["file"]]), media_type=resource.get("content_type", "application/pdf"), headers={"Content-Disposition": f'inline; filename="{resource.get("filename", "resource.pdf")}"'})

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
    return StreamingResponse(iter([resource["file"]]), media_type=resource.get("content_type", "application/pdf"), headers={"Content-Disposition": f'inline; filename="{resource.get("filename", "submission.pdf")}"'})

@app.get("/admin/users")
def admin_users(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    rows = db.query(User.id, User.name, User.email, User.role, User.section).order_by(User.role, User.name).all()
    return [{"id": u[0], "name": u[1], "roll_no": u[2], "role": u[3], "section": u[4] or "Unassigned"} for u in rows]

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
    total_users = sum(role_counts.values())
    students_count = role_counts.get("student", 0)
    teachers_count = role_counts.get("teacher", 0)
    admins_count = role_counts.get("admin", 0)
    courses_count = db.query(Course.id).count()
    assignments_count = db.query(Assignment.id).count()
    submissions_count = db.query(Submission.id).count()
    return {
        "users": total_users,
        "students": students_count,
        "teachers": teachers_count,
        "admins": admins_count,
        "courses": courses_count,
        "assignments": assignments_count,
        "submissions": submissions_count
    }

@app.get("/ai-search")
def ai_search(q: str, user=Depends(get_user), db: Session = Depends(get_db)):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")
    try:
        course_ids = None
        if user["role"] == "student":
            course_ids = [e.course_id for e in db.query(Enrollment).filter(Enrollment.student_id == user["id"]).all()]
        return {"query": q, "results": search_resources(q, course_ids)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search service unavailable: {exc}")
