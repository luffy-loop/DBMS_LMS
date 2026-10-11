#!/usr/bin/env python3
"""Opt-in authenticated end-to-end latency smoke test for a dedicated test deployment."""
import json, os, platform, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

BASE=os.getenv("LMS_BENCHMARK_BASE_URL","").rstrip("/")
TEACHER=os.getenv("LMS_BENCHMARK_TEACHER_ROLL_NO","")
TEACHER_PASSWORD=os.getenv("LMS_BENCHMARK_TEACHER_PASSWORD","")
STUDENT=os.getenv("LMS_BENCHMARK_STUDENT_ROLL_NO","")
STUDENT_PASSWORD=os.getenv("LMS_BENCHMARK_STUDENT_PASSWORD","")
TIMEOUT=max(5,int(os.getenv("LMS_BENCHMARK_TIMEOUT_SECONDS","30")))
OUTPUT=os.getenv("LMS_BENCHMARK_OUTPUT","")
RESULTS=[]


def request_step(name,path,method="GET",token=None,body=None,fields=None,file_part=None,expected=(200,),extra_headers=None):
    headers={"Accept":"application/json",**(extra_headers or {})}
    if token: headers["Authorization"]="Bearer "+token
    data=None
    if file_part:
        boundary="----LMSBenchmarkBoundary7MA4YWxkTrZu0gW"
        chunks=[]
        for key,value in (fields or {}).items():
            chunks.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n").encode())
        filename,payload,content_type=file_part
        chunks.append((f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n").encode()+payload+b"\r\n")
        chunks.append(f"--{boundary}--\r\n".encode())
        data=b"".join(chunks); headers["Content-Type"]="multipart/form-data; boundary="+boundary
    elif fields is not None:
        data=urllib.parse.urlencode(fields).encode(); headers["Content-Type"]="application/x-www-form-urlencoded"
    elif body is not None:
        data=json.dumps(body).encode(); headers["Content-Type"]="application/json"
    started=time.perf_counter(); status=0; text=""
    try:
        req=urllib.request.Request(BASE+path,data=data,headers=headers,method=method)
        with urllib.request.urlopen(req,timeout=TIMEOUT) as response: status=response.status; text=response.read().decode("utf-8","replace")
    except urllib.error.HTTPError as exc: status=exc.code; text=exc.read().decode("utf-8","replace")
    except Exception as exc: text=type(exc).__name__
    elapsed=round((time.perf_counter()-started)*1000,2)
    RESULTS.append({"step":name,"method":method,"path":path,"status":status,"expected_statuses":list(expected),"duration_ms":elapsed,"ok":status in expected})
    try: parsed=json.loads(text)
    except Exception: parsed={"detail":text[:300]}
    if status not in expected: raise RuntimeError(f"{name} failed HTTP {status}: {str(parsed)[:300]}")
    return parsed


def login(roll,password):
    response=request_step("login_"+("teacher" if roll==TEACHER else "student"),"/login","POST",body={"roll_no":roll,"password":password})
    token=response.get("token")
    if not token: raise RuntimeError("Login did not return token")
    return token


def main():
    if not all((BASE,TEACHER,TEACHER_PASSWORD,STUDENT,STUDENT_PASSWORD)):
        raise SystemExit("Set LMS_BENCHMARK_BASE_URL and dedicated teacher/student roll number + password variables.")
    started=time.perf_counter()
    teacher_token=login(TEACHER,TEACHER_PASSWORD)
    student_token=login(STUDENT,STUDENT_PASSWORD)
    request_step("teacher_course_list","/my-courses",token=teacher_token)
    created=request_step("create_course","/courses","POST",teacher_token,body={"title":"Benchmark "+datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),"description":"Disposable workflow benchmark course"})
    course_id=created.get("id")
    if not course_id: raise RuntimeError("Course create response missing id")
    request_step("enroll_student","/enroll","POST",student_token,body={"course_id":course_id})
    payload=b"Database indexes organize keys and improve lookup speed. A B-tree supports efficient search, insertion, and deletion."
    uploaded=request_step("upload_material",f"/courses/{course_id}/resources","POST",teacher_token,fields={"title":"Benchmark indexing material"},file_part=("benchmark.txt",payload,"text/plain"),extra_headers={"Idempotency-Key":"workflow-benchmark-"+str(time.time_ns())})
    resource_id=uploaded.get("id")
    if not resource_id: raise RuntimeError("Upload response missing resource id")
    deadline=time.monotonic()+TIMEOUT
    while time.monotonic()<deadline:
        status=request_step("material_status",f"/resources/{resource_id}/status",token=teacher_token)
        if status.get("status")=="READY": break
        if status.get("status")=="FAILED": raise RuntimeError("Material processing failed")
        time.sleep(1)
    else: raise RuntimeError("Material did not become READY before timeout")
    request_step("semantic_search","/ai-search?q="+urllib.parse.quote("B-tree index lookup speed"),token=student_token)
    now=datetime.now(timezone.utc)
    assignment=request_step("create_assignment","/assignments","POST",teacher_token,fields={"course_id":str(course_id),"title":"Benchmark assignment","description":"Synthetic answer","type":"assignment","start_time":now.isoformat(),"end_time":(now+timedelta(days=1)).isoformat(),"max_marks":"10"})
    assignment_id=assignment.get("id")
    if not assignment_id: raise RuntimeError("Assignment response missing id")
    submission=request_step("submit_answer","/submissions","POST",student_token,fields={"assignment_id":str(assignment_id),"answer":"A B-tree index improves database lookup speed."})
    submission_id=submission.get("id")
    if not submission_id: raise RuntimeError("Submission response missing id")
    request_step("grade_submission",f"/submissions/{submission_id}/marks?marks=8&feedback=Benchmark%20review", "PUT",teacher_token)
    request_step("publish_marks",f"/submissions/{submission_id}/publish","POST",teacher_token)
    request_step("student_marks","/my-marks",token=student_token)
    report={"generated_at_utc":datetime.now(timezone.utc).isoformat(),"environment":{"base_url":BASE,"python":platform.python_version()},"steps":RESULTS,"step_count":len(RESULTS),"failures":sum(not row["ok"] for row in RESULTS),"total_duration_ms":round((time.perf_counter()-started)*1000,2),"notes":"Dedicated test accounts and disposable course only. This is one workflow latency sample, not a load/capacity test. Delete benchmark course/data after review."}
    rendered=json.dumps(report,indent=2)
    if OUTPUT:
        with open(OUTPUT,"w",encoding="utf-8") as handle: handle.write(rendered+"\n")
    print(rendered)


if __name__=="__main__": main()
