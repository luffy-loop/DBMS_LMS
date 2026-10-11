# Deploy the durable LMS worker

The API service and durable worker are different processes. The current worker polls PostgreSQL AI jobs and MongoDB material jobs; it must remain running, so do not configure it as a cron job or a public web service.

## Before deployment

1. Open the existing **DBMS_LMS** web service in Render and note the exact values for `DATABASE_URL`, `MONGO_URL`, `MONGODB_DATABASE`, and `JWT_SECRET`. Do not paste their values into Git or an issue.
2. Confirm the intended Render workspace has billing enabled for background workers. Render's Free plan does not support workers; the Blueprint currently uses the legacy `starter` paid worker plan.
3. In Render, create/sync a Blueprint from the repository's root `render.yaml`. It defines only `dbms-lms-durable-worker` and points it at `LMS/backend`; it does not recreate the existing API.
4. Supply the exact existing API values for the four `sync: false` variables when prompted. `DATABASE_URL`, `MONGO_URL`, and `JWT_SECRET` must point to the same database/secret used by the API. Keep `RUN_DB_SETUP=false` so the worker does not run migrations, and keep vector search disabled in this low-memory worker unless measured capacity supports it.

## Verify deployment

- In worker logs, confirm the line `Durable LMS worker started`.
- Create a quiz job through the app and confirm the job transitions from `QUEUED` through processing to `COMPLETED` (or a useful `FAILED` error).
- Upload a teacher-owned test file and confirm processing reaches `READY`; check a malformed file returns a client error and is never stored.
- Restart the API after queuing a test job and confirm the worker continues polling/completes it.
- Check Render metrics and restart/OOM events while uploads and searches are exercised.

The GitHub test suite cannot verify this live queue without the Render worker, database, MongoDB, and authenticated test accounts. Do not mark the worker as deployed until the log and queued-job checks above pass.
