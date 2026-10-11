#!/usr/bin/env python3
"""Compare lexical and dense-vector ranking on an approved, labelled course corpus.

Input JSON schema:
{"documents":[{"title":"...","content":"...","course_id":1}],
 "queries":[{"query":"...","relevant_titles":["..."]}]}
"""
import argparse
import json
import math
import os
import platform
import statistics
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("ENABLE_RESOURCE_VECTOR_SEARCH", "false")
from vector_store import _lexical_search


def _cosine(left, right):
    dot = sum(a*b for a,b in zip(left,right))
    left_norm = math.sqrt(sum(a*a for a in left))
    right_norm = math.sqrt(sum(b*b for b in right))
    return dot/(left_norm*right_norm) if left_norm and right_norm else 0.0


def _metrics(ranked, relevant):
    ranks = [rank for rank, title in enumerate(ranked, 1) if title in set(relevant)]
    first = min(ranks) if ranks else None
    return {"hit_at_1": bool(first == 1), "reciprocal_rank": 1/first if first else 0.0, "relevant_rank": first}


def evaluate(corpus, use_semantic=True):
    documents = corpus["documents"]
    queries = corpus["queries"]
    lexical_rows = []
    semantic_rows = []
    embedder = None
    semantic_error = None
    if use_semantic:
        try:
            from evaluation_service import generate_embedding
            embedder = generate_embedding
        except Exception as exc:
            semantic_error = type(exc).__name__
    for case in queries:
        relevant = case.get("relevant_titles") or [case.get("relevant_title", "")]
        lexical = _lexical_search(case["query"], documents)
        lexical_titles = [row["title"] for row in lexical]
        lexical_rows.append({"query":case["query"], **_metrics(lexical_titles,relevant), "ranked_titles":lexical_titles})
        if embedder:
            query_vector = embedder(case["query"])
            scored = []
            for document in documents:
                vector = embedder((document.get("title","") + ". " + document.get("content",""))[:2000])
                scored.append((_cosine(query_vector,vector),document["title"]))
            scored.sort(reverse=True)
            titles = [title for _,title in scored]
            semantic_rows.append({"query":case["query"], **_metrics(titles,relevant), "ranked_titles":titles})
    report = {
        "generated_at_utc":datetime.now(timezone.utc).isoformat(),
        "python":platform.python_version(),
        "corpus_documents":len(documents),
        "query_count":len(queries),
        "corpus_mode":"user_supplied_approved_course_material" if corpus.get("source") else "user_supplied_corpus",
        "lexical":{"hit_at_1":round(sum(row["hit_at_1"] for row in lexical_rows)/max(1,len(lexical_rows)),3),"mean_reciprocal_rank":round(statistics.mean(row["reciprocal_rank"] for row in lexical_rows),3) if lexical_rows else 0,"cases":lexical_rows},
        "semantic":{"available":bool(embedder),"error_type":semantic_error,"hit_at_1":round(sum(row["hit_at_1"] for row in semantic_rows)/max(1,len(semantic_rows)),3) if semantic_rows else None,"mean_reciprocal_rank":round(statistics.mean(row["reciprocal_rank"] for row in semantic_rows),3) if semantic_rows else None,"cases":semantic_rows},
        "limitations":["Results depend on the supplied relevance labels and corpus.","Embedding cosine evaluation is a model comparison, not proof that the production vector index is enabled.","Do not include private student records or confidential course material."],
    }
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--corpus",required=True,help="Path to approved JSON corpus and relevance labels")
    parser.add_argument("--output",default="")
    parser.add_argument("--lexical-only",action="store_true")
    args=parser.parse_args()
    corpus=json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    if not corpus.get("documents") or not corpus.get("queries"):
        parser.error("Corpus must contain non-empty documents and queries")
    report=evaluate(corpus,not args.lexical_only)
    rendered=json.dumps(report,indent=2,sort_keys=True)
    print(rendered)
    if args.output:
        target=Path(args.output); target.parent.mkdir(parents=True,exist_ok=True); target.write_text(rendered+"\n",encoding="utf-8")
    if not report["lexical"]["cases"]:
        raise SystemExit("No search cases were evaluated")


if __name__=="__main__": main()
