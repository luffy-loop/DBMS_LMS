# LMS HTTP Performance Benchmark

Run from LMS/backend:

    python tests/performance/benchmark.py --base-url https://dbms-lms-hwvp.onrender.com --path /health --requests 30 --concurrency 3

Repeat --path to mix endpoints. Authenticated endpoints can be measured with --token from a safe environment.

The report contains total requests, successes, failures, average/min/max latency, p50, p95, error rate, requests/second, concurrency, and duration.

Use small controlled concurrency for the Render deployment. Never add benchmark numbers to documentation unless the command was actually executed. If execution is unavailable, record: Not measured — reason.


To save a portable report, pass `--output verification-results/live-health-benchmark.json`. The JSON captures generation time, runtime/platform, actual status-code counts, latency percentiles, error rate, concurrency and throughput. A `/health` benchmark measures only the public health endpoint, not complete authenticated workflows.
