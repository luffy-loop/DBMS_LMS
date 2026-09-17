from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt
from database import Base, engine, get_db
from models import User, Course, Enrollment, Assignment, Submission
from schemas import Register, Login, CourseCreate, EnrollmentCreate
from auth import get_user
from schemas import Register, Login, CourseCreate, EnrollmentCreate, AssignmentCreate, SubmissionCreate
from mongodb import mongo_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="LMS")

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
    user = db.query(User).filter(User.email == data.email).first()

    if user:
        raise HTTPException(status_code=400, detail="Email already registered")

    if data.role not in ["student", "teacher", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    user = User(
        name=data.name,
        email=data.email,
        password=pwd.hash(data.password),
        role=data.role
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "User registered successfully",
        "id": user.id,
        "role": user.role
    }

@app.post("/login")
def login(data: Login, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()

    if not user or not pwd.verify(data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = jwt.encode(
        {
            "id": user.id,
            "role": user.role
        },
        key,
        algorithm=alg
    )

    return {
        "message": "Login successful",
        "token": token,
        "id": user.id,
        "name": user.name,
        "role": user.role
    }
    
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
def create_course(
    data: CourseCreate,
    user=Depends(get_user),
    db: Session = Depends(get_db)
):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")

    course = Course(
        title=data.title,
        description=data.description,
        teacher_id=user["id"]
    )

    db.add(course)
    db.commit()
    db.refresh(course)

    return {
        "message": "Course created",
        "id": course.id,
        "title": course.title
    }

@app.get("/courses")
def get_courses(db: Session = Depends(get_db)):
    return db.query(Course).all()

@app.post("/enroll")
def enroll(
    data: EnrollmentCreate,
    user=Depends(get_user),
    db: Session = Depends(get_db)
):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")

    course = db.query(Course).filter(Course.id == data.course_id).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    old = db.query(Enrollment).filter(
        Enrollment.student_id == user["id"],
        Enrollment.course_id == data.course_id
    ).first()

    if old:
        raise HTTPException(status_code=400, detail="Already enrolled")

    enrollment = Enrollment(
        student_id=user["id"],
        course_id=data.course_id
    )

    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    return {
        "message": "Enrolled successfully",
        "course_id": course.id
    }

@app.get("/my-courses")
def my_courses(
    user=Depends(get_user),
    db: Session = Depends(get_db)
):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")

    enrollments = db.query(Enrollment).filter(
        Enrollment.student_id == user["id"]
    ).all()

    courses = []

    for e in enrollments:
        course = db.query(Course).filter(Course.id == e.course_id).first()
        if course:
            courses.append(course)

    return courses


@app.post("/assignments")
def create_assignment(
    data: AssignmentCreate,
    user=Depends(get_user),
    db: Session = Depends(get_db)
):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")

    course = db.query(Course).filter(Course.id == data.course_id).first()

    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    assignment = Assignment(
        title=data.title,
        description=data.description,
        course_id=data.course_id,
        teacher_id=user["id"]
    )

    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    return {
        "message": "Assignment created",
        "id": assignment.id,
        "title": assignment.title
    }


@app.get("/assignments/{course_id}")
def get_assignments(
    course_id: int,
    db: Session = Depends(get_db)
):
    return db.query(Assignment).filter(
        Assignment.course_id == course_id
    ).all()


@app.post("/submissions")
def submit_assignment(
    data: SubmissionCreate,
    user=Depends(get_user),
    db: Session = Depends(get_db)
):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")

    assignment = db.query(Assignment).filter(
        Assignment.id == data.assignment_id
    ).first()

    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    submission = Submission(
        assignment_id=data.assignment_id,
        student_id=user["id"],
        answer=data.answer
    )

    db.add(submission)
    db.commit()
    db.refresh(submission)

    return {
        "message": "Submission successful",
        "id": submission.id
    }


@app.get("/my-submissions")
def my_submissions(
    user=Depends(get_user),
    db: Session = Depends(get_db)
):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")

    return db.query(Submission).filter(
        Submission.student_id == user["id"]
    ).all()
    
@app.get("/teacher/submissions")
def get_submissions(
    user=Depends(get_user),
    db: Session = Depends(get_db)
):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")

    return db.query(Submission).filter(
        Submission.marks == None
    ).all()


@app.put("/submissions/{submission_id}/marks")
def give_marks(
    submission_id: int,
    marks: int,
    user=Depends(get_user),
    db: Session = Depends(get_db)
):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")

    submission = db.query(Submission).filter(
        Submission.id == submission_id
    ).first()

    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    submission.marks = marks
    db.commit()

    return {
        "message": "Marks updated",
        "submission_id": submission.id,
        "marks": marks
    }


@app.get("/my-marks")
def my_marks(
    user=Depends(get_user),
    db: Session = Depends(get_db)
):
    if user["role"] != "student":
        raise HTTPException(status_code=403, detail="Student access only")

    return db.query(Submission).filter(
        Submission.student_id == user["id"]
    ).all()
    
@app.post("/courses/{course_id}/resources")
def add_resource(
    course_id: int,
    title: str,
    content: str,
    user=Depends(get_user)
):
    if user["role"] != "teacher":
        raise HTTPException(status_code=403, detail="Teacher access only")

    resource = {
        "course_id": course_id,
        "title": title,
        "content": content,
        "teacher_id": user["id"]
    }

    result = mongo_db.resources.insert_one(resource)

    return {
        "message": "Resource added",
        "id": str(result.inserted_id)
    }


@app.get("/courses/{course_id}/resources")
def get_resources(course_id: int):
    resources = list(
        mongo_db.resources.find(
            {"course_id": course_id},
            {"_id": 0}
        )
    )

    return resources