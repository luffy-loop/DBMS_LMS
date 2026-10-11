#!/usr/bin/env python3
import argparse
import concurrent.futures
import json
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
import urllib.error
import urllib.request


def request_once(base_url, path, method, body, token, timeout):
    url = base_url.rstrip("/") + path
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = body.encode() if body is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    started = time.perf_counter()
    try:
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            status = response.status
        return status, (time.perf_counter() - started) * 1000
    except urllib.error.HTTPError as exc:
        try:
            exc.read()
        except Exception:
            pass
        return exc.code, (time.perf_counter() - started) * 1000
    except Exception:
        return 0, (time.perf_counter() - started) * 1000


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    index = min(len(values) - 1, round((p / 100) * (len(values) - 1)))
    return round(values[index], 2)


def main():
    parser = argparse.ArgumentParser(description="Repeatable LMS HTTP performance benchmark")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--path", action="append", required=True)
    parser.add_argument("--method", default="GET", choices=["GET", "POST", "PUT", "PATCH"])
    parser.add_argument("--body", default=None)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--token", default="")
    parser.add_argument("--output", default="", help="Optional path to save the measured JSON report")
    args = parser.parse_args()
    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests and --concurrency must be positive")

    started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [
            pool.submit(request_once, args.base_url, args.path[i % len(args.path)], args.method, args.body, args.token, args.timeout)
            for i in range(args.requests)
        ]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    elapsed = time.perf_counter() - started
    latencies = [latency for _, latency in results]
    successful = sum(200 <= status < 400 for status, _ in results)
    failed = len(results) - successful
    status_counts = {}
    for status, _ in results:
        label = str(status) if status else "transport_error"
        status_counts[label] = status_counts.get(label, 0) + 1
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "runtime": platform.python_version(),
            "platform": platform.platform(),
            "host": __import__("urllib.parse", fromlist=["urlparse"]).urlparse(args.base_url).hostname,
        },
        "base_url": args.base_url,
        "endpoints": args.path,
        "method": args.method,
        "authenticated": bool(args.token),
        "requests": len(results),
        "successful": successful,
        "failed": failed,
        "status_counts": status_counts,
        "error_rate_percent": round((failed / len(results)) * 100, 2),
        "average_latency_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "min_latency_ms": round(min(latencies), 2) if latencies else None,
        "max_latency_ms": round(max(latencies), 2) if latencies else None,
        "p50_latency_ms": percentile(latencies, 50),
        "p95_latency_ms": percentile(latencies, 95),
        "requests_per_second": round(len(results) / elapsed, 2) if elapsed else None,
        "concurrency": args.concurrency,
        "duration_seconds": round(elapsed, 3),
        "notes": "Measured HTTP requests; success is a 2xx/3xx response. Health-only runs do not verify authenticated workflows.",
    }
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
