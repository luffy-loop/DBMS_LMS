from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal

class Register(BaseModel):
    name: str
    roll_no: str
    password: str
    role: str
    section: str = "Unassigned"

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
    duration_minutes: int | None = None

class SubmissionCreate(BaseModel):
    assignment_id: int
    answer: str

class MCQOptionCreate(BaseModel):
    option_text: str
    is_correct: bool = False
    order_index: int = 0

class RubricCriterionCreate(BaseModel):
    id: int | None = None
    criterion_text: str
    max_marks: float
    order_index: int = 0

class QuestionCreate(BaseModel):
    question_text: str
    question_type: str  # 'mcq' or 'descriptive'
    max_marks: int = 10
    order_index: int = 0
    # For MCQ:
    options: list[MCQOptionCreate] | None = None
    # For Descriptive:
    reference_answer: str | None = None
    rubric_criteria: list[RubricCriterionCreate] | None = None

class QuestionUpdate(BaseModel):
    question_text: str | None = None
    max_marks: int | None = None
    order_index: int | None = None
    options: list[MCQOptionCreate] | None = None
    reference_answer: str | None = None
    rubric_criteria: list[RubricCriterionCreate] | None = None

class RubricSuggestionRequest(BaseModel):
    question_text: str
    reference_answer: str
    max_marks: int = 10

class QuestionAnswerSubmit(BaseModel):
    question_id: int
    selected_option_id: int | None = None
    student_answer: str | None = None

class ExamSubmissionCreate(BaseModel):
    assignment_id: int
    answers: list[QuestionAnswerSubmit]

class QuestionReviewItem(BaseModel):
    question_id: int
    override_marks: float | None = None
    review_note: str | None = None

class TeacherReviewRequest(BaseModel):
    reviews: list[QuestionReviewItem]



class CourseUpdate(BaseModel):
    title: str
    description: str


class AdminUserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    roll_no: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["student", "teacher"]
    section: str = Field(default="Unassigned", min_length=1, max_length=40)


class AdminRoleUpdate(BaseModel):
    role: Literal["student", "teacher", "admin"]
