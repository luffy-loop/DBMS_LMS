# LMS HTTP Performance Benchmark

Run from LMS/backend:

    python tests/performance/benchmark.py --base-url https://dbms-lms-hwvp.onrender.com --path /health --requests 30 --concurrency 3

Repeat --path to mix endpoints. Authenticated endpoints can be measured with --token from a safe environment.

The report contains total requests, successes, failures, average/min/max latency, p50, p95, error rate, requests/second, concurrency, and duration.

Use small controlled concurrency for the Render deployment. Never add benchmark numbers to documentation unless the command was actually executed. If execution is unavailable, record: Not measured — reason.
