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
elif url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql://", 1)

if url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

if environment == "production" and url.startswith("postgresql+psycopg2://") and "sslmode=" not in url:
    url += ("&" if "?" in url else "?") + "sslmode=require"

engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1200")),
    "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "8")),
}

if url.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update({
        "pool_size": max(1, int(os.getenv("DB_POOL_SIZE", "3"))),
        "max_overflow": max(0, int(os.getenv("DB_MAX_OVERFLOW", "2"))),
        "pool_use_lifo": True,
        "connect_args": {
            "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "5")),
        },
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
