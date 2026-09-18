from datetime import datetime
from pydantic import BaseModel

class Register(BaseModel):
    name: str
    roll_no: str
    password: str
    role: str

class Login(BaseModel):
    roll_no: str
    password: str

class CourseCreate(BaseModel):
    title: str
    description: str

class EnrollmentCreate(BaseModel):
    course_id: int

class AssignmentCreate(BaseModel):
    title: str
    description: str
    course_id: int
    type: str = "assignment"
    start_time: datetime | None = None
    end_time: datetime | None = None

class SubmissionCreate(BaseModel):
    assignment_id: int
    answer: str
