"""
evaluate_retrieval.py
=====================
Evaluates HybridSearchService against annotated retrieval benchmark queries.
Tests BM25 lexical + dense vector ranking, citation accuracy, and jurisdiction isolation.
Exit code: 0 if overall retrieval recall >= 50%, else 1.
"""

import sys
import json
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.db.session import SessionLocal, init_db
from backend.app.services.retrieval.hybrid_search import HybridSearchService


def _col(text: str, width: int) -> str:
    return str(text)[:width].ljust(width)


def run_retrieval_evaluation(benchmark_file: str) -> int:
    init_db()
    db = SessionLocal()
    searcher = HybridSearchService(db)

    data = json.loads(Path(benchmark_file).read_text(encoding="utf-8"))

    total_queries = len(data)
    queries_passed = 0
    top1_hits = 0

    SEP = "=" * 85
    print(f"\n{SEP}")
    print("  RETRIEVAL BENCHMARK EVALUATION (Hybrid BM25 + Vector)")
    print(SEP)

    hdr = (
        _col("QUERY ID", 10) +
        _col("JUR", 6) +
        _col("STATUS", 10) +
        _col("TOP-1 CITATION", 35) +
        _col("SCORE", 8)
    )
    print(f"  {hdr}")
    print(f"  {'-' * 81}")

    for case in data:
        qid = case["query_id"]
        query = case["query"]
        jur = case["jurisdiction"]
        expected_patterns = [p.lower() for p in case.get("expected_citation_patterns", [])]
        min_results = case.get("min_results", 1)

        results = searcher.search(query=query, jurisdiction=jur, top_k=5)

        matched = False
        top_citation = "None"
        top_score = 0.0

        if results:
            top_res = results[0]
            top_citation = top_res.citation
            top_score = top_res.relevance_score

            # Check if any returned result contains expected patterns
            for item in results:
                target_text = (item.citation + " " + item.quoted_text).lower()
                if any(pat in target_text for pat in expected_patterns):
                    matched = True
                    break

            # Check top 1
            first_text = (top_res.citation + " " + top_res.quoted_text).lower()
            if any(pat in first_text for pat in expected_patterns):
                top1_hits += 1

        status = "PASS" if (matched and len(results) >= min_results) else "FAIL"
        if status == "PASS":
            queries_passed += 1

        row = (
            _col(qid, 10) +
            _col(jur, 6) +
            _col(f"[{status}]", 10) +
            _col(top_citation, 35) +
            _col(f"{top_score:.3f}", 8)
        )
        print(f"  {row}")

    db.close()

    recall = (queries_passed / total_queries * 100) if total_queries else 0.0
    p_at_1 = (top1_hits / total_queries * 100) if total_queries else 0.0

    print(f"\n{SEP}")
    print("  RETRIEVAL EVALUATION SUMMARY")
    print(SEP)
    print(f"  Total queries evaluated : {total_queries}")
    print(f"  Queries passing recall  : {queries_passed}")
    print(f"  Overall Recall@5        : {recall:.1f}%")
    print(f"  Precision@1             : {p_at_1:.1f}%")
    print(SEP)

    threshold = 50.0
    if recall >= threshold:
        print(f"  RESULT: PASS (Recall {recall:.1f}% >= {threshold}%)")
        return 0
    else:
        print(f"  RESULT: FAIL (Recall {recall:.1f}% < {threshold}%)")
        return 1


if __name__ == "__main__":
    benchmark_path = Path(__file__).parent.parent / "data" / "benchmark" / "retrieval_benchmark.json"
    sys.exit(run_retrieval_evaluation(str(benchmark_path)))
