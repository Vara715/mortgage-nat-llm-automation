"""
chat_compliance_llm.py
=======================
Interactive RAG (Retrieval-Augmented Generation) query and chat CLI.
Connects your configured LLM (Groq, OpenAI, NIM, Ollama) directly to the
authoritative mortgage compliance knowledge base and hybrid search engine.

Usage:
    # 1. Ask a one-off question:
    python scripts/chat_compliance_llm.py --query "Can a lender charge a prepayment penalty on an adjustable rate mortgage in the US?"

    # 2. Ask a question regarding Indian banking regulations:
    python scripts/chat_compliance_llm.py --query "What is the RBI directive on foreclosure charges for floating rate home loans?" --jurisdiction IN

    # 3. Enter interactive conversation mode:
    python scripts/chat_compliance_llm.py
"""

import os
import sys
import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.services.retrieval.hybrid_search import HybridSearchService
from backend.app.services.compliance.llm_explainer import LLMExplainerService


def run_rag_query(query: str, jurisdiction: str = "US", top_k: int = 4):
    print(f"\n[1/3] Searching statutory knowledge base for: \"{query}\" (Jurisdiction: {jurisdiction})...")
    db = SessionLocal()
    retriever = HybridSearchService(db)
    results = retriever.search(query=query, jurisdiction=jurisdiction, top_k=top_k)
    db.close()

    evidence_texts = []
    print(f"[2/3] Retrieved {len(results)} relevant statutory clauses:")
    for i, item in enumerate(results, 1):
        score = getattr(item, "relevance_score", 1.0)
        print(f"      [{i}] {item.citation} (Score: {score:.2f}, Page: {item.page_number})")
        evidence_texts.append(f"Source [{item.citation}]:\n\"{item.quoted_text[:400]}\"")

    combined_evidence = "\n\n".join(evidence_texts) if evidence_texts else "No specific statutory chunks found."

    print(f"[3/3] Querying configured LLM ({settings.LLM_PROVIDER} / {settings.DEFAULT_LLM_MODEL})...\n")

    explainer = LLMExplainerService()
    if not explainer.client:
        print("[WARNING] No live LLM client could be initialized. Please check API keys in .env.")
        return

    system_prompt = (
        "You are an expert AI mortgage regulatory compliance officer for 'morgage-loan-automation'. "
        "Answer the user's question accurately, citing specific regulations, statutes, or circulars. "
        "Base your answer strictly on the provided statutory evidence when available. "
        "Be clear, precise, and professional. Always include a brief reminder that this is for decision support."
    )

    user_prompt = (
        f"STATUTORY EVIDENCE RETRIEVED FROM KNOWLEDGE BASE:\n"
        f"{combined_evidence}\n\n"
        f"USER QUESTION:\n{query}\n\n"
        f"Please provide a grounded, comprehensive regulatory compliance answer citing the relevant sections."
    )

    try:
        completion = explainer.client.chat.completions.create(
            model=explainer.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=600,
        )

        answer = completion.choices[0].message.content.strip()
        print("=" * 80)
        print("  LLM COMPLIANCE REASONING RESPONSE")
        print("=" * 80)
        print(answer)
        print("=" * 80 + "\n")
    except Exception as e:
        print(f"[ERROR] LLM query failed: {e}")


def interactive_loop():
    print("\n" + "=" * 80)
    print("  MortgageGuard AI — Interactive LLM Compliance Assistant")
    print(f"  Connected Provider: {settings.LLM_PROVIDER} | Model: {settings.DEFAULT_LLM_MODEL}")
    print("  Type your question below (or 'exit' / 'quit' to end):")
    print("=" * 80 + "\n")

    while True:
        try:
            query = input("Ask Compliance LLM > ").strip()
            if not query:
                continue
            if query.lower() in ["exit", "quit", "q"]:
                print("Exiting compliance chat. Goodbye!")
                break
            # Detect jurisdiction hint
            jur = "IN" if any(w in query.lower() for w in ["rbi", "india", "lakh", "foreclosure"]) else "US"
            run_rag_query(query, jurisdiction=jur)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break


def main():
    parser = argparse.ArgumentParser(description="Query the LLM with grounded regulatory evidence.")
    parser.add_argument("--query", "-q", type=str, help="Question to ask the compliance LLM")
    parser.add_argument("--jurisdiction", "-j", choices=["US", "IN"], default="US", help="Jurisdiction (US or IN)")
    parser.add_argument("--top-k", type=int, default=4, help="Number of statutory evidence chunks to retrieve")

    args = parser.parse_args()

    if args.query:
        run_rag_query(args.query, jurisdiction=args.jurisdiction, top_k=args.top_k)
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
