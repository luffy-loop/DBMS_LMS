from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("DATABASE_URL")
environment = os.getenv("ENVIRONMENT", "development").lower()
if not url:
    if environment == "production":
        raise RuntimeError("DATABASE_URL must be configured in production")
    url = "postgresql+psycopg2://admin@localhost:5432/postgres"
elif url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 1800,
    "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "10")),
}
if url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update({
        "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
    })

engine = create_engine(url, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()