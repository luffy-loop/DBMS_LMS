import json
import os
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("RUN_DB_SETUP", "false")
os.environ.setdefault("DATABASE_URL", "sqlite:///./login-benchmark-unused.db")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import get_db
from main import app, pwd
from models import AuditLog, Assignment, Course, Enrollment, Submission, User

ACCOUNT = "LOGIN_BENCH_001"
PASSWORD = "benchmark-only-password"
REQUESTS = 20
CONCURRENCY = 4


def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, int((len(ordered) * fraction + 0.999999) - 1)))]


def stats(values, failures=0):
    return {
        "requests": len(values),
        "failures": failures,
        "failure_rate_percent": round(failures * 100 / max(1, len(values)), 2),
        "average_ms": round(statistics.mean(values), 2) if values else None,
        "median_ms": round(statistics.median(values), 2) if values else None,
        "p95_ms": round(percentile(values, 0.95), 2) if values else None,
    }


def sample(client, method, path, expected_status, count=REQUESTS, **kwargs):
    values = []
    failures = 0
    response_body = None
    for _ in range(count):
        started = time.perf_counter()
        response = getattr(client, method)(path, **kwargs)
        elapsed = (time.perf_counter() - started) * 1000
        values.append(elapsed)
        if response.status_code != expected_status:
            failures += 1
        if response.status_code == expected_status:
            response_body = response.json()
    return values, failures, response_body


def main():
    with tempfile.TemporaryDirectory(prefix="lms-login-bench-") as directory:
        db_path = Path(directory) / "benchmark.sqlite3"
        engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False, "timeout": 15},
        )
        TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        for table in (User.__table__, Course.__table__, Enrollment.__table__, Assignment.__table__, Submission.__table__, AuditLog.__table__):
            table.create(engine)

        seed = TestingSession()
        student = User(
            name="Synthetic Login Benchmark",
            email=ACCOUNT,
            password=pwd.hash(PASSWORD),
            role="student",
            section="BENCH",
        )
        seed.add(student)
        seed.commit()
        course = Course(title="Benchmark Course", description="Isolated benchmark fixture", teacher_id=student.id)
        seed.add(course)
        seed.commit()
        seed.add(Enrollment(student_id=student.id, course_id=course.id))
        seed.add(Assignment(
            title="Benchmark Assignment",
            description="Isolated benchmark fixture",
            course_id=course.id,
            teacher_id=student.id,
            type="assignment",
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow() + timedelta(days=1),
        ))
        seed.commit()
        seed.close()

        def override_db():
            db = TestingSession()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        result = {
            "environment": "isolated temporary SQLite database + FastAPI TestClient",
            "account": "synthetic test account; no production credentials",
            "requests_per_sequential_case": REQUESTS,
            "controlled_concurrency": CONCURRENCY,
        }
        try:
            with TestClient(app) as client:
                health, health_failures, _ = sample(client, "get", "/health", 200)
                valid, valid_failures, login_body = sample(
                    client, "post", "/login", 200,
                    json={"roll_no": ACCOUNT, "password": PASSWORD},
                )
                invalid, invalid_failures, invalid_body = sample(
                    client, "post", "/login", 401,
                    json={"roll_no": ACCOUNT, "password": "intentionally-wrong-password"},
                )
                missing, missing_failures, missing_body = sample(
                    client, "post", "/login", 401,
                    json={"roll_no": "MISSING_BENCH_USER", "password": "intentionally-wrong-password"},
                )

                token = login_body["token"] if login_body else ""
                headers = {"Authorization": "Bearer " + token}
                session, session_failures, _ = sample(client, "get", "/auth/session", 200, headers=headers)
                profile, profile_failures, _ = sample(client, "get", "/profile", 200, headers=headers)

                parallel_values = []
                parallel_failures = 0
                total_started = time.perf_counter()

                def concurrent_login(_):
                    started = time.perf_counter()
                    response = client.post("/login", json={"roll_no": ACCOUNT, "password": PASSWORD})
                    return (time.perf_counter() - started) * 1000, response.status_code

                with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
                    for duration, status in executor.map(concurrent_login, range(REQUESTS)):
                        parallel_values.append(duration)
                        if status != 200:
                            parallel_failures += 1
                parallel_total_ms = (time.perf_counter() - total_started) * 1000

            result["cold_first_valid_login_ms"] = round(valid[0], 2) if valid else None
            result["warm_valid_login_ms"] = stats(valid[1:], valid_failures)
            result["all_valid_login_ms"] = stats(valid, valid_failures)
            result["invalid_existing_user_ms"] = stats(invalid, invalid_failures)
            result["missing_user_ms"] = stats(missing, missing_failures)
            result["health_ms"] = stats(health, health_failures)
            result["auth_session_ms"] = stats(session, session_failures)
            result["profile_ms"] = stats(profile, profile_failures)
            result["controlled_concurrency_login_ms"] = stats(parallel_values, parallel_failures)
            result["controlled_concurrency_wall_ms"] = round(parallel_total_ms, 2)
            result["valid_login_jwt_response"] = bool(login_body and token)
            result["invalid_login_generic_response"] = bool(
                invalid_body and invalid_body.get("detail") == "Invalid roll number or password"
            )
            result["missing_user_generic_response"] = bool(
                missing_body and missing_body.get("detail") == "Invalid roll number or password"
            )
            print("LOGIN_LATENCY_BENCHMARK " + json.dumps(result, sort_keys=True))
            if any([
                health_failures, valid_failures, invalid_failures, missing_failures,
                session_failures, profile_failures, parallel_failures,
                not result["valid_login_jwt_response"],
                not result["invalid_login_generic_response"],
                not result["missing_user_generic_response"],
            ]):
                raise SystemExit("Isolated login benchmark encountered a failed request or response contract")
        finally:
            app.dependency_overrides.pop(get_db, None)
            engine.dispose()


if __name__ == "__main__":
    main()
