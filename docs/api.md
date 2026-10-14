# REST API Reference

The **morgage-loan-automation** backend provides a comprehensive, documented RESTful API with automated OpenAPI specifications accessible at `/docs` and `/redoc`.

Base URL: `http://localhost:8000/api`

---

## 1. System Health & Readiness

### `GET /api/health`
Checks service status, database connectivity, and supported jurisdictions.
```json
{
  "status": "healthy",
  "service": "morgage-loan-automation",
  "version": "1.0.0",
  "timestamp": "2026-10-14T08:00:00Z",
  "database": "connected",
  "jurisdictions_supported": ["US (CFPB)", "IN (RBI)"]
}
```

### `GET /api/health/ready`
Kubernetes/Docker readiness probe. Verifies database connectivity and returns the total number of indexed searchable regulatory chunks.
```json
{
  "status": "ready",
  "database": "connected",
  "indexed_chunks": 141
}
```

---

## 2. Authentication & Authorization

### `POST /api/auth/token`
Authenticates user credentials and returns a signed JWT Bearer token.
- **Request (OAuth2 Form Data):** `username`, `password`
- **Default Dev Accounts:**
  - `analyst` / `analyst123` (Role: `analyst`)
  - `reviewer` / `reviewer123` (Role: `reviewer`)
  - `admin` / `admin123` (Role: `admin`)
- **Response:**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "role": "analyst"
  }
  ```

### `GET /api/auth/me`
Retrieves information about the currently authenticated user.
- **Headers:** `Authorization: Bearer <token>`

---

## 3. Dataset-Agnostic Ingestion & Job Management

### `POST /api/datasets`
Registers a new dataset manifest in the system.
- **Request Body (JSON):**
  ```json
  {
    "name": "CFPB Regulation Z Statutory Corpus",
    "jurisdiction": "US",
    "data_type": "REGULATORY_STATUTE",
    "source_connector": {
      "connector_type": "local",
      "config": {"file_path": "data/raw/ecfr_title12_part1026.xml"}
    },
    "chunking_config": {"chunk_size": 800, "chunk_overlap": 100}
  }
  ```

### `GET /api/datasets`
Lists all registered datasets, version history, and ingestion counts.

### `POST /api/datasets/{id}/ingest`
Triggers synchronous or asynchronous ingestion for a registered dataset.
- **Query Params:** `async_mode` (boolean, default: `true`)
- **Response:**
  ```json
  {
    "job_id": "job_948f2a1b",
    "status": "PENDING",
    "dataset_id": "ds_cfpb_regz",
    "message": "Ingestion job queued"
  }
  ```

### `GET /api/jobs/{job_id}`
Checks the lifecycle status of a background processing or ingestion job.
- **Response:**
  ```json
  {
    "job_id": "job_948f2a1b",
    "status": "COMPLETED",
    "progress_percent": 100.0,
    "records_processed": 141,
    "error_message": null
  }
  ```

---

## 4. Regulatory Chunks & Hybrid Retrieval

### `POST /api/retrieval/search`
Executes hybrid lexical (BM25) and dense vector search with strict jurisdiction isolation.
- **Request Body:**
  ```json
  {
    "query": "points and fees limitation for qualified mortgages",
    "jurisdiction": "US",
    "dataset_id": null,
    "top_k": 5
  }
  ```
- **Response:**
  ```json
  {
    "query": "points and fees limitation for qualified mortgages",
    "jurisdiction": "US",
    "total_results": 5,
    "results": [
      {
        "chunk_id": "chk_1026_43_001",
        "citation": "12 CFR Sec. 1026.43(e)(3)",
        "content": "For a qualified mortgage, total points and fees must not exceed...",
        "score": 11.195,
        "bm25_score": 14.82,
        "dense_score": 0.82
      }
    ]
  }
  ```

### `GET /api/regulations/search`
Query-parameter variant of regulatory search.

### `GET /api/regulations/chunks`
Lists indexed structure-aware regulatory chunks.

### `GET /api/regulations/stats`
Returns total indexed chunks and clause breakdown by jurisdiction.

---

## 5. Loan Documents & Term Extraction

### `POST /api/documents/upload`
Uploads a loan agreement (PDF or TXT) and triggers digital text extraction, table parsing, document classification, and structured loan term extraction.
- **Form Data:**
  - `file`: Multipart file stream
  - `jurisdiction_override`: (optional) `US` or `IN`

### `GET /api/documents`
Lists uploaded mortgage loan documents.

### `GET /api/documents/{id}`
Retrieves document metadata and extracted terms.

### `GET /api/documents/{id}/extraction`
Retrieves detailed loan term extraction with verbatim source excerpts, confidence scores, and page provenance.

### `POST /api/documents/{id}/extract`
Forces re-extraction and document classification on an existing document.

### `PATCH /api/documents/{id}/fields/{field_id}`
Enables an analyst to submit a manual correction for an extracted loan term, logging the edit to `audit_events`.

---

## 6. Compliance Analysis

### `POST /api/compliance/analyze/{doc_id}`
Triggers end-to-end compliance analysis for an uploaded document ID.

### `POST /api/compliance/analyze`
Directly analyzes extracted terms passed in JSON payload.
- **Request Body:**
  ```json
  {
    "document_id": "doc_12345",
    "loan_terms": {
      "loan_amount": 350000.0,
      "interest_rate": 6.375,
      "rate_type": "fixed",
      "points_and_fees_percent": 1.2,
      "prepayment_penalty_exists": false
    },
    "jurisdiction": "US"
  }
  ```

### `GET /api/compliance/analyses`
Lists recent compliance audit reports.

### `GET /api/compliance/analyses/{id}`
Retrieves full compliance report including deterministic rule results, grounded reasoning, and statutory citations.

### `GET /api/compliance/analyses/{id}/findings`
Returns structured list of rule findings with severity, status (`NO_ISSUE_IDENTIFIED`, `POTENTIAL_ISSUE`, `NEEDS_REVIEW`), and statutory citations.

---

## 7. Human Review Queue (HITL)

### `GET /api/reviews/tasks` or `GET /api/reviews/queue`
Retrieves pending or resolved human review tasks.
- **Query Params:** `status` (`PENDING` | `RESOLVED`), `limit`, `offset`

### `POST /api/reviews/tasks/{task_id}/decision`
Records a compliance officer adjudication for a flagged finding.
- **Request Body:**
  ```json
  {
    "decision": "ACCEPTED",
    "new_status": "POTENTIAL_ISSUE",
    "comments": "Confirmed points and fees exceed 3.00% cap under 12 CFR 1026.43(e)(3)."
  }
  ```

---

## 8. Grounded Synthetic Q&A Generation

### `POST /api/qa/generate`
Generates verifiable, citation-backed Question-Answer pairs from regulatory chunks.
- **Request Body:**
  ```json
  {
    "jurisdiction": "US",
    "dataset_id": null,
    "limit": 5
  }
  ```

### `GET /api/qa`
Lists generated Q&A pairs with source citations.

---

## 9. Public Lending Intelligence (HMDA 2023)

### `GET /api/hmda/analytics`
Returns aggregate statistics from authentic CFPB HMDA Loan Application Register records.
- **Query Params:** `state_code`, `loan_purpose`, `loan_type`

### `GET /api/hmda/records`
Queries individual HMDA loan records with pagination.

---

## 10. Audit Ledger & PDF Reports

### `GET /api/audit/events`
Queries chronological events from the append-only `audit_events` ledger.

### `POST /api/audit/events`
Records a system or external workflow event into the audit trail.

### `GET /api/reports/{analysis_id}/pdf`
Generates and streams a formal compliance certificate PDF using ReportLab Platypus.
