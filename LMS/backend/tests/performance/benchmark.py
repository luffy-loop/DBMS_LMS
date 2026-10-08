#!/usr/bin/env python3
import argparse
import concurrent.futures
import json
import statistics
import time
import urllib.error
import urllib.request


def request_once(base_url, path, token, timeout):
    url = base_url.rstrip("/") + path
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    started = time.perf_counter()
    try:
        request = urllib.request.Request(url, headers=headers)
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
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--token", default="")
    args = parser.parse_args()

    if args.requests < 1 or args.concurrency < 1:
        parser.error("--requests and --concurrency must be positive")

    started = time.perf_counter()
    paths = args.path
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [
            pool.submit(request_once, args.base_url, paths[i % len(paths)], args.token, args.timeout)
            for i in range(args.requests)
        ]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]
    elapsed = time.perf_counter() - started
    latencies = [latency for _, latency in results]
    successful = sum(200 <= status < 400 for status, _ in results)
    failed = len(results) - successful
    report = {
        "base_url": args.base_url,
        "endpoints": paths,
        "requests": len(results),
        "successful": successful,
        "failed": failed,
        "error_rate_percent": round((failed / len(results)) * 100, 2),
        "average_latency_ms": round(statistics.mean(latencies), 2) if latencies else None,
        "p50_latency_ms": percentile(latencies, 50),
        "p95_latency_ms": percentile(latencies, 95),
        "requests_per_second": round(len(results) / elapsed, 2) if elapsed else None,
        "concurrency": args.concurrency,
        "duration_seconds": round(elapsed, 3),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
