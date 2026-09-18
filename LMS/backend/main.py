from datetime import datetime
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
from auth import get_user
from mongodb import mongo_db
from vector_store import search_resources

Base.metadata.create_all(bind=engine)

with engine.begin() as conn:
    conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS type VARCHAR DEFAULT 'assignment'"))
    conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS start_time TIMESTAMP"))
    conn.execute(text("ALTER TABLE assignments ADD COLUMN IF NOT EXISTS end_time TIMESTAMP"))

app = FastAPI(title="LMS")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
key = "lms-secret-key"
alg = "HS256"

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
def create_assignment(data: AssignmentCreate, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")
    if data.type not in ["assignment", "test"]:
        raise HTTPException(status_code=400, detail="Invalid assessment type")
    if data.start_time and data.end_time and data.end_time <= data.start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")
    course = db.query(Course).filter(Course.id == data.course_id, Course.teacher_id == user["id"]).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    assignment = Assignment(title=data.title, description=data.description, course_id=course.id, teacher_id=user["id"], type=data.type, start_time=data.start_time, end_time=data.end_time)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return {"message": "Assessment created", "id": assignment.id, "title": assignment.title}

@app.get("/assignments/{course_id}")
def get_assignments(course_id: int, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] not in ["student", "teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return db.query(Assignment).filter(Assignment.course_id == course_id).all()

@app.post("/submissions")
def submit_assignment(data: SubmissionCreate, user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    assignment = db.query(Assignment).filter(Assignment.id == data.assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    now = datetime.now()
    if assignment.start_time and now < assignment.start_time:
        raise HTTPException(status_code=400, detail="This assessment is not open yet")
    if assignment.end_time and now > assignment.end_time:
        raise HTTPException(status_code=400, detail="Submission deadline has passed")
    old = db.query(Submission).filter(Submission.assignment_id == assignment.id, Submission.student_id == user["id"]).first()
    if old:
        raise HTTPException(status_code=400, detail="You have already submitted this assessment")
    submission = Submission(assignment_id=assignment.id, student_id=user["id"], answer=data.answer)
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return {"message": "Submission successful", "id": submission.id}

@app.get("/my-submissions")
def my_submissions(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")
    return db.query(Submission).filter(Submission.student_id == user["id"]).all()

@app.get("/teacher/submissions")
def get_submissions(user=Depends(get_user), db: Session = Depends(get_db)):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")
    ids = db.query(Assignment.id).filter(Assignment.teacher_id == user["id"])
    return db.query(Submission).filter(Submission.marks == None, Submission.assignment_id.in_(ids)).all()

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
    result = mongo_db.resources.insert_one({"course_id": course_id, "title": title, "filename": file.filename, "content_type": file.content_type, "content": "", "teacher_id": user["id"], "file": data, "created_at": datetime.utcnow()})
    return {"message": "PDF uploaded", "id": str(result.inserted_id), "title": title}

@app.get("/courses/{course_id}/resources")
def get_resources(course_id: int, user=Depends(get_user)):
    if user["role"] not in ["student", "teacher", "admin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    resources = mongo_db.resources.find({"course_id": course_id}, {"_id": 1, "title": 1, "filename": 1, "created_at": 1})
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
