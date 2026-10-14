"""
pipeline.py
===========
End-to-end Ingestion, Extraction, Structuring, and Knowledge Base Builder
for TCS Mortgage Loan Compliance System (Slides 2, 3, 6, 7, 8).

Workflow:
1. Document Ingestion: Loads real-world regulatory PDFs & contracts from data/real_docs/
2. PDF Extraction (pdfplumber): Extracts text, tables, images, metadata, visual debugging (Slide 3)
3. Text Cleaning & Structuring: Removes headers/footers, preserves section hierarchy, splits into 500-1000 token chunks with chunking reasoning (Slide 7)
4. Structured Q&A & Instruction Generation: Formats data conforming to Slide 6 & Slide 7 schemas
5. Knowledge Storage & Indexing: Stores into SQLite B-Tree database + JSONL exports for sub-10ms lookup (Slide 8)
"""

import time
import sys
from pathlib import Path

# Ensure utf-8 output in Windows console
sys.stdout.reconfigure(encoding="utf-8")

from extraction.pdf_extractor import PDFExtractor, ExtractedDocument, ExtractedPage, VisualDebugInfo
from extraction.text_structurer import TextStructurer, DocumentChunk
from extraction.qa_generator import RegulatoryQAGenerator
from kb.storage import RegulatoryKnowledgeStore

BASE_DIR = Path(__file__).resolve().parent
REAL_DOCS_DIR = BASE_DIR / "data" / "real_docs"
RAW_DOCS_DIR = BASE_DIR / "data" / "raw_docs"
DB_PATH = BASE_DIR / "data" / "knowledge_base" / "regulatory_knowledge.db"
JSONL_OUTPUT_PATH = BASE_DIR / "data" / "clean_mortgage_data.jsonl"
QA_JSONL_PATH = BASE_DIR / "data" / "structured_qna" / "regulatory_qa_database.jsonl"


def run_pipeline():
    start_time = time.time()
    print("=" * 70)
    print("TCS MORTGAGE LOAN COMPLIANCE SYSTEM — INGESTION & KB BUILDER")
    print("=" * 70)

    extractor = PDFExtractor(enable_visual_debugging=True)
    structurer = TextStructurer()
    qa_generator = RegulatoryQAGenerator()
    store = RegulatoryKnowledgeStore(db_path=DB_PATH)

    all_chunks: list[DocumentChunk] = []
    all_qa_items: list[dict] = []

    # 1. Process PDF documents in data/real_docs/
    pdf_files = sorted(REAL_DOCS_DIR.glob("*.pdf"))
    print(f"\n[Step 1] Found {len(pdf_files)} real-world PDF documents to extract with pdfplumber:")
    for pdf_p in pdf_files:
        p_start = time.time()
        print(f"  -> Extracting {pdf_p.name} ({pdf_p.stat().st_size / 1024:.1f} KB)...")
        doc = extractor.extract(pdf_p)
        chunks = structurer.structure_and_chunk(doc)
        all_chunks.extend(chunks)
        qa_items = qa_generator.process_all_chunks(chunks)
        all_qa_items.extend(qa_items)
        elapsed = time.time() - p_start
        print(f"     Extracted {len(doc.pages)} pages -> {len(chunks)} structured chunks -> {len(qa_items)} Q&A pairs ({elapsed:.2f}s)")

    # 2. Process text-based regulatory documents in data/real_docs/
    txt_files = sorted(REAL_DOCS_DIR.glob("*.txt"))
    print(f"\n[Step 2] Processing {len(txt_files)} text-based regulatory files:")
    for txt_p in txt_files:
        text_content = txt_p.read_text(encoding="utf-8")
        doc = ExtractedDocument(
            source_file=txt_p.name,
            total_pages=1,
            metadata={"source": "regulatory_text", "file_size": txt_p.stat().st_size},
            pages=[
                ExtractedPage(
                    page_number=1,
                    text=text_content,
                    tables=[],
                    images=[],
                    visual_debug=VisualDebugInfo(
                        page_number=1,
                        char_count=len(text_content),
                        word_count=len(text_content.split()),
                        table_count=0,
                        image_count=0,
                    ),
                )
            ],
        )
        chunks = structurer.structure_and_chunk(doc)
        all_chunks.extend(chunks)
        qa_items = qa_generator.process_all_chunks(chunks)
        all_qa_items.extend(qa_items)
        print(f"  -> {txt_p.name} -> {len(chunks)} chunks -> {len(qa_items)} Q&A pairs")

    # 3. Process baseline policy docs from data/raw_docs/ if present
    if RAW_DOCS_DIR.exists():
        raw_files = sorted(RAW_DOCS_DIR.glob("*.txt"))
        print(f"\n[Step 3] Processing baseline policy & FAQ files from {RAW_DOCS_DIR.name}:")
        for raw_p in raw_files:
            text_content = raw_p.read_text(encoding="utf-8")
            doc = ExtractedDocument(
                source_file=raw_p.name,
                total_pages=1,
                metadata={"source": "policy_faq", "file_size": raw_p.stat().st_size},
                pages=[
                    ExtractedPage(
                        page_number=1,
                        text=text_content,
                        tables=[],
                        images=[],
                        visual_debug=VisualDebugInfo(
                            page_number=1,
                            char_count=len(text_content),
                            word_count=len(text_content.split()),
                            table_count=0,
                            image_count=0,
                        ),
                    )
                ],
            )
            chunks = structurer.structure_and_chunk(doc)
            all_chunks.extend(chunks)
            qa_items = qa_generator.process_all_chunks(chunks)
            all_qa_items.extend(qa_items)
            print(f"  -> {raw_p.name} -> {len(chunks)} chunks -> {len(qa_items)} Q&A pairs")

    # 4. Insert into SQLite indexed store
    print(f"\n[Step 4] Storing {len(all_chunks)} chunks and {len(all_qa_items)} Q&A pairs into SQLite database...")
    store.insert_chunks(all_chunks)
    store.insert_qa_entries(all_qa_items)

    # 5. Export JSONL files (both clean_mortgage_data.jsonl and structured QA database)
    print(f"\n[Step 5] Exporting structured JSONL outputs:")
    store.export_to_jsonl(QA_JSONL_PATH)
    print(f"  -> Wrote structured Q&A database: {QA_JSONL_PATH.resolve()}")

    # Format clean_mortgage_data.jsonl for agent tools backward compatibility
    with JSONL_OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            row = {
                "id": f"{c.source_file}_{c.chunk_id}",
                "source_file": c.source_file,
                "page": c.page_number,
                "section": c.section_id,
                "category": c.category,
                "text": f"[{c.category}] {c.section_title}: {c.text}",
            }
            import json
            f.write(json.dumps(row) + "\n")
    print(f"  -> Wrote curated agent knowledge base: {JSONL_OUTPUT_PATH.resolve()}")

    total_time = time.time() - start_time
    counts = store.count_records()
    print("\n" + "=" * 70)
    print(f"PIPELINE COMPLETED IN {total_time:.2f}s")
    print(f"Indexed Chunks : {counts['chunks']}")
    print(f"Indexed Q&As   : {counts['qa_items']}")
    print("Database       : data/knowledge_base/regulatory_knowledge.db")
    print("=" * 70)


if __name__ == "__main__":
    run_pipeline()
