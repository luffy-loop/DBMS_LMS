from fastapi import FastAPI
from database import Base, engine
import models

Base.metadata.create_all(bind=engine)

app = FastAPI(title="LMS")

@app.get("/")
def home():
    return {"message": "LMS Backend Running"}

@app.get("/health")
def health():
    return {"status": "ok"}