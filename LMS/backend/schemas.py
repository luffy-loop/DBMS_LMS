from pydantic import BaseModel, EmailStr

class Register(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str

class Login(BaseModel):
    email: EmailStr
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


class SubmissionCreate(BaseModel):
    assignment_id: int
    answer: str