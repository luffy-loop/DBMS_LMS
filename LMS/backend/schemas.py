from pydantic import BaseModel, EmailStr

class Register(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str

class Login(BaseModel):
    email: EmailStr
    password: str