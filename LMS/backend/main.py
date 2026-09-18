from datetime import datetime, timedelta
from io import BytesIO
from pypdf import PdfReader
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
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

Base.metadata.create_all(bind=engine)

with engine.begin() as conn:
    conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS type VARCHAR DEFAULT 'assignment'"))
    conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS start_time TIMESTAMP"))
    conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS end_time TIMESTAMP"))
    conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS duration_minutes INTEGER"))

app = FastAPI(title="LMS")
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

pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

@app.get("/")
def home():
    return {"message": "LMS Backend Running"}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/register")
def register(data: Register, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.roll_no).first()
    if user:
        raise HTTPException(status_code=400, detail="Roll number already registered")
    if data.role not in ["student", "teacher", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    user = User(name=data.name, email=data.roll_no, password=pwd.hash(data.password), role=data.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User registered successfully", "id": user.id, "role": user.role}

@app.post("/login")
def login(data: Login, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.roll_no).first()
    if not user or not pwd.verify(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid roll number or password")
    token = jwt.encode({"id": user.id, "role": user.role}, key, algorithm=alg)
    return {"message": "Login successful", "token": token, "id": user.id, "name": user.name, "role": user.role}

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
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    enrollments = db.query(Enrollment).filter(Enrollment.student_id == user["id"]).all()
    return [course for e in enrollments if (course := db.query(Course).filter(Course.id == e.course_id).first())]

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
    if type not in ["assignment", "test"]:
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
        start_time=start_time,
        end_time=end_time,
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

def assessment_deadline(assignment):
    deadlines = []
    if assignment.end_time:
        deadlines.append(assignment.end_time)
    if assignment.start_time and assignment.duration_minutes:
        deadlines.append(assignment.start_time + timedelta(minutes=assignment.duration_minutes))
    return min(deadlines) if deadlines else None

def assessment_status(assignment):
    now = datetime.now()
    if assignment.start_time and now < assignment.start_time:
        return "upcoming"
    deadline = assessment_deadline(assignment)
    if deadline and now >= deadline:
        return "closed"
    return "open"

def db_submission_exists(assignment_id, student_id):
    from database import SessionLocal
    db = SessionLocal()
    try:
        return db.query(Submission.id).filter(Submission.assignment_id == assignment_id, Submission.student_id == student_id).first() is not None
    finally:
        db.close()

def assessment_payload(assignment, student_id=None):
    handout = mongo_db.resources.find_one(
        {"assignment_id": assignment.id},
        {"_id": 1, "title": 1, "filename": 1}
    )
    return {
        "id": assignment.id,
        "title": assignment.title,
        "description": assignment.description,
        "course_id": assignment.course_id,
        "teacher_id": assignment.teacher_id,
        "type": assignment.type,
        "start_time": assignment.start_time,
        "end_time": assignment.end_time,
        "duration_minutes": assignment.duration_minutes,
        "deadline": assessment_deadline(assignment),
        "status": assessment_status(assignment),
        "submitted": bool(student_id and db_submission_exists(assignment.id, student_id)),
        "handout": {
            "id": str(handout["_id"]),
            "title": handout.get("title", ""),
            "filename": handout.get("filename", "")
        } if handout else None
    }

@app.get("/assignments/{course_id}")
def get_assignments(course_id: int, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in ["student", "teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return [assessment_payload(a, user["id"] if user["role"] == "student" else None) for a in db.query(Assignment).filter(Assignment.course_id == course_id).all()]

@app.post("/submissions")
async def submit_assignment(
    assignment_id: int = Form(...),
    answer: str = Form(""),
    file: UploadFile | None = File(None),
    user=Depends(get_user),
    db: Session = Depends(get_db)
):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")

    now = datetime.now()
    if assignment.start_time and now < assignment.start_time:
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

    if not answer.strip() and not file_data:
        raise HTTPException(status_code=400, detail="Write an answer or upload a PDF")

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

    return {"message": "Submission successful", "id": submission.id}

def submission_payload(submission):
    file_doc = mongo_db.submission_files.find_one(
        {"submission_id": submission.id},
        {"_id": 1, "filename": 1}
    )
    return {
        "id": submission.id,
        "assignment_id": submission.assignment_id,
        "student_id": submission.student_id,
        "answer": submission.answer,
        "marks": submission.marks,
        "file_id": str(file_doc["_id"]) if file_doc else None,
        "file_name": file_doc.get("filename", "") if file_doc else None
    }

@app.get("/my-submissions")
def my_submissions(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    return [submission_payload(s) for s in db.query(Submission).filter(Submission.student_id == user["id"]).all()]

@app.get("/teacher/submissions")
def get_submissions(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")
    ids = db.query(Assignment.id).filter(Assignment.teacher_id == user["id"])
    return [submission_payload(s) for s in db.query(Submission).filter(
        Submission.marks == None,
        Submission.assignment_id.in_(ids)
    ).all()]

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
    return db.query(Submission).filter(Submission.student_id == user["id"]).all()

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

@app.get("/courses/{course_id}/resources")
def get_resources(course_id: int, user=Depends(get_user)):
    if user["role"] not in ["student", "teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    resources = mongo_db.resources.find(
        {"course_id": course_id, "assignment_id": {"$exists": False}},
        {"_id": 1, "title": 1, "filename": 1, "created_at": 1}
    )
    return [{"id": str(r["_id"]), "title": r.get("title", ""), "filename": r.get("filename", ""), "created_at": r.get("created_at")} for r in resources]

@app.get("/resources/{resource_id}/download")
def download_resource(resource_id: str, user=Depends(get_user)):
    if user["role"] not in ["student", "teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    try:
        resource = mongo_db.resources.find_one({"_id": ObjectId(resource_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid resource id")
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
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
        assignment = db.query(Assignment).filter(Assignment.id == submission.assignment_id, Assignment.teacher_id == user["id"]).first()
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
    return [{"id": u.id, "name": u.name, "roll_no": u.email, "role": u.role} for u in db.query(User).all()]

@app.get("/admin/overview")
def admin_overview(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access only")
    return {"users": db.query(User).count(), "students": db.query(User).filter(User.role == "student").count(), "teachers": db.query(User).filter(User.role == "teacher").count(), "admins": db.query(User).filter(User.role == "admin").count(), "courses": db.query(Course).count(), "assignments": db.query(Assignment).count(), "submissions": db.query(Submission).count()}

@app.get("/ai-search")
def ai_search(q: str, user=Depends(get_user)):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")
    try:
        return {"query": q, "results": search_resources(q)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search service unavailable: {exc}")
