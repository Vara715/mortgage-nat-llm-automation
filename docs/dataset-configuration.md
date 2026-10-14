# Dataset Configuration Guide — morgage-loan-automation

The **morgage-loan-automation** engine is designed to be **dataset-agnostic**. It allows compliance analysts and data engineers to ingest arbitrary regulatory statutes, circulars, loan document collections, and tabular mortgage registries without modifying core code.

---

## 1. The Dataset Manifest

Every dataset is declared using a JSON manifest file placed in `data/manifests/` or submitted via `POST /api/datasets`.

### Manifest Schema & Field Reference

```json
{
  "dataset_id": "unique_dataset_slug",
  "dataset_name": "Human-Readable Name",
  "description": "Scope, source, and legal context",
  "source_type": "LOCAL_FILE | URL | API | CSV | JSON | JSONL | PARQUET",
  "source_location": "path/to/file or https://...",
  "file_format": "pdf | csv | json | jsonl | txt | parquet",
  "jurisdiction": "US | IN | null",
  "version": "1.0.0",
  "collection_date": "YYYY-MM-DD",
  "license_notes": "Public Domain / Proprietary",
  "selected_columns": ["col_a", "col_b"],
  "parser_config": {
    "ocr_enabled": false,
    "extract_tables": true,
    "clean_headers_footers": true
  },
  "chunking_config": {
    "chunk_size_tokens": 600,
    "chunk_overlap_tokens": 100,
    "structure_aware": true
  },
  "embedding_config": {
    "provider": "tfidf_dense",
    "model": "tfidf_dense_v1",
    "dimension": 128
  },
  "enable_qa_generation": true,
  "access_retention": "PERMANENT"
}
```

---

## 2. Ingestion Paths: Documents vs Tabular

The engine distinguishes between two fundamental data modalities:

### A. Document Ingestion Path (PDF / TXT)
- Used for regulatory statutes (e.g. 12 CFR Part 1026), RBI circulars, policy manuals, and loan agreements.
- Text, tables, and page boundaries are extracted using `PDFExtractionService` (with OCR fallback for scanned pages).
- The text is chunked using `RegulatoryChunker` (structure-aware, preserving section codes and token ceilings).
- Chunks are stored in PostgreSQL/SQLite `document_chunks` table tagged with `dataset_id` and indexed for hybrid BM25 + cosine vector retrieval.
- Optionally triggers `QAGenerator` to synthesize verifiable, source-grounded Q&A pairs.

### B. Tabular Ingestion Path (CSV / JSON / Parquet)
- Used for public mortgage loan registries (e.g. HMDA 2023 dataset with 200 authentic loan records).
- Bypasses text chunking. Records are validated against column schemas and loaded into `hmda_records`.
- Calculates statistical analytics: approval/denial distributions, median interest rates, and loan-to-value distributions.

---

## 3. How to Ingest a New Dataset

### Via CLI:
```bash
python scripts/ingest_dataset.py --manifest data/manifests/cfpb_reg_z_manifest.json
python scripts/ingest_dataset.py --manifest data/manifests/hmda_2023_manifest.json
```

### Via REST API:
```bash
# 1. Register Manifest
curl -X POST http://localhost:8000/api/datasets \
  -H "Content-Type: application/json" \
  -d @data/manifests/cfpb_reg_z_manifest.json

# 2. Trigger Ingestion
curl -X POST http://localhost:8000/api/datasets/cfpb_reg_z_2024/ingest
```

### Via n8n Automation:
- Trigger Workflow A by sending a webhook:
```bash
curl -X POST http://localhost:5678/webhook/dataset-ingest \
  -H "Content-Type: application/json" \
  -d '{"dataset_id": "cfpb_reg_z_2024"}'
```
