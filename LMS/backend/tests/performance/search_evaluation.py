#!/usr/bin/env python3
"""Deterministic offline evaluation of LMS lexical resource retrieval.

Uses a small synthetic corpus with known relevant titles. This is not a live-content or
semantic-embedding quality claim.
"""
import argparse
import json
import os
import platform
import statistics
from datetime import datetime, timezone
from pathlib import Path

os.environ["ENABLE_RESOURCE_VECTOR_SEARCH"] = "false"

from vector_store import _lexical_search

CORPUS = [
    {"id": "normalization", "title": "Database Normalization",
     "content": "Database normalization reduces redundant data and update insertion deletion anomalies in relational tables.",
     "type": "resource", "course_id": 101},
    {"id": "indexing", "title": "B-tree Indexing",
     "content": "A B-tree database index speeds up query lookups by organizing keys and reducing disk reads.",
     "type": "resource", "course_id": 101},
    {"id": "operating-systems", "title": "Process Synchronization",
     "content": "Mutex locks and semaphores coordinate concurrent processes and threads, protecting critical sections from race conditions.",
     "type": "resource", "course_id": 102},
    {"id": "networking", "title": "TCP Networking",
     "content": "TCP uses a handshake to establish a connection and congestion control to manage network traffic.",
     "type": "resource", "course_id": 103},
    {"id": "deadlocks", "title": "Operating System Deadlocks",
     "content": "Deadlock occurs when processes wait for resources in a cycle; mutual exclusion, hold and wait, no preemption and circular wait are conditions.",
     "type": "resource", "course_id": 102},
]
QUERIES = [
    {"query": "database normalization redundancy anomalies", "relevant": "Database Normalization"},
    {"query": "B-tree index speeds query lookups", "relevant": "B-tree Indexing"},
    {"query": "mutex semaphore critical section race conditions", "relevant": "Process Synchronization"},
    {"query": "TCP handshake congestion control network traffic", "relevant": "TCP Networking"},
    {"query": "deadlock processes circular wait resources", "relevant": "Operating System Deadlocks"},
]


def evaluate():
    cases = []
    reciprocal_ranks = []
    hits_at_1 = 0
    for case in QUERIES:
        results = _lexical_search(case["query"], CORPUS)
        ranked = [row["title"] for row in results]
        rank = ranked.index(case["relevant"]) + 1 if case["relevant"] in ranked else None
        if rank == 1:
            hits_at_1 += 1
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        cases.append({
            "query": case["query"],
            "expected_relevant_title": case["relevant"],
            "ranked_titles": ranked,
            "relevant_rank": rank,
            "hit_at_1": rank == 1,
        })
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": platform.python_version(),
        "mode": "lexical_keyword_matching",
        "semantic_vector_search_used": False,
        "corpus": "five fixed synthetic academic resources",
        "query_count": len(cases),
        "hit_at_1": round(hits_at_1 / len(cases), 3),
        "mean_reciprocal_rank": round(statistics.mean(reciprocal_ranks), 3),
        "cases": cases,
        "limitations": [
            "Synthetic corpus only; does not measure live course materials.",
            "Evaluates lexical matching, not semantic retrieval or AI answer correctness.",
            "Render production defaults to lexical retrieval unless ENABLE_RESOURCE_VECTOR_SEARCH is explicitly enabled.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="", help="Optional path to save the JSON report")
    args = parser.parse_args()
    report = evaluate()
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    if report["hit_at_1"] < 0.8 or report["mean_reciprocal_rank"] < 0.8:
        raise SystemExit("Lexical retrieval evaluation fell below the fixed regression threshold")


if __name__ == "__main__":
    main()
