# Data Dictionary

This document details the schema definitions, relational entities, field data types, and constraints across **morgage-loan-automation**.

---

## 1. Regulatory & Document Sources

### 1.1 `regulatory_sources`
Tracks authentic source provenance and idempotent ingestion status.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `source_id` | String(100) | Primary Key | Unique source identifier (e.g., `US-CFPB-REGZ`) |
| `source_name` | String(255) | Not Null | Descriptive title of regulatory corpus |
| `source_url` | Text | Not Null | Official public URL |
| `source_type` | String(50) | Not Null | `regulation`, `circular`, `statute`, `public_dataset` |
| `jurisdiction` | String(10) | Index, Not Null | `US` or `IN` |
| `issuing_authority` | String(100) | Not Null | Issuing regulatory body (`CFPB`, `RBI`, `FFIEC`) |
| `publication_date` | String(50) | Nullable | Official publication date |
| `effective_from` | String(50) | Nullable | Effective start date |
| `effective_until` | String(50) | Nullable | Sunset or amendment date |
| `retrieved_at` | DateTime | Default UTC | Acquisition timestamp |
| `checksum` | String(64) | Not Null | SHA-256 cryptographic hash of source file |
| `document_version`| String(50) | Nullable | Official version tag |
| `license_or_usage_notes` | Text | Nullable | Public domain or government work license notes |
| `ingestion_status`| String(50) | Default 'INDEXED'| `INDEXED`, `PENDING`, `FAILED` |
| `extraction_quality` | Float | Default 1.0 | Extraction confidence score [0.0 - 1.0] |

---

### 1.2 `regulatory_documents`
Represents parsed documents belonging to a registered source.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | String(36) | Primary Key | Unique document UUID |
| `source_id` | String(100) | Foreign Key (`regulatory_sources.source_id`) | Associated parent source |
| `title` | String(255) | Not Null | Document or section title |
| `jurisdiction` | String(10) | Index, Not Null | `US` or `IN` |
| `doc_type` | String(100) | Not Null | Section type |
| `file_path` | Text | Not Null | Path on persistent disk |
| `total_pages` | Integer | Default 1 | Page count |
| `created_at` | DateTime | Default UTC | Ingestion timestamp |

---

### 1.3 `document_chunks`
Stores structure-aware text chunks (500–1,000 tokens) with section codes and dataset associations.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | String(36) | Primary Key | Chunk UUID |
| `document_id` | String(36) | Foreign Key (`regulatory_documents.id`) | Parent document |
| `dataset_id` | String(100) | Index, Nullable | Associated dataset identifier |
| `page_number` | Integer | Default 1 | Provenance page number |
| `section_id` | String(100) | Index | Internal section code |
| `section_code`| String(100) | Not Null | Legal citation string (e.g., `12 CFR Sec. 1026.43(e)(3)`) |
| `chunk_index` | Integer | Default 0 | Sequence index |
| `text` | Text | Not Null | Verbatim regulatory text |
| `normalized_text` | Text | Not Null | Cleaned search tokens |
| `token_count` | Integer | Default 0 | Token length |
| `category` | String(100) | Index, Not Null | Regulatory category |
| `jurisdiction`| String(10) | Index, Not Null | `US` or `IN` |
| `embedding_json` | Text | Nullable | Serialized embedding vector representation |

---

## 2. Dataset-Agnostic Management

### 2.1 `datasets`
Declarative catalog of user-provided datasets and statutory corpora.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | String(100) | Primary Key | Dataset identifier (e.g., `ds_cfpb_regz`) |
| `name` | String(255) | Not Null | Human-readable dataset name |
| `description` | Text | Nullable | Dataset description |
| `source_type` | String(50) | Not Null | `LOCAL_FILE`, `URL`, `API`, `CSV`, `JSON`, `PARQUET` |
| `source_location` | Text | Not Null | File path or remote URI |
| `file_format` | String(50) | Not Null | Format (`pdf`, `csv`, `json`, `parquet`) |
| `jurisdiction` | String(10) | Index, Nullable | `US`, `IN`, or null |
| `version` | String(50) | Default '1.0.0' | Version string |
| `checksum` | String(64) | Nullable | SHA-256 source checksum |
| `manifest_config` | Text | Nullable | Serialized JSON manifest configuration |
| `status` | String(50) | Default 'ACTIVE' | `ACTIVE`, `ARCHIVED`, `PROCESSING` |
| `created_at` | DateTime | Default UTC | Creation timestamp |

---

### 2.2 `dataset_versions`
Tracks versions, changelogs, and checksums for updated datasets.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | String(36) | Primary Key | Version record UUID |
| `dataset_id` | String(100) | Foreign Key (`datasets.id`) | Parent dataset |
| `version_tag` | String(50) | Not Null | Semantic version tag |
| `record_count` | Integer | Default 0 | Total records or chunks |
| `checksum` | String(64) | Not Null | SHA-256 hash of this version |
| `changelog` | Text | Nullable | Description of updates |
| `created_at` | DateTime | Default UTC | Release timestamp |

---

### 2.3 `processing_jobs`
Lifecycle tracking for asynchronous ingestion, extraction, and compliance jobs.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | String(36) | Primary Key | Job UUID |
| `job_type` | String(50) | Index, Not Null | `INGESTION`, `EXTRACTION`, `COMPLIANCE`, `QA_GEN` |
| `target_id` | String(100) | Index, Not Null | Subject `dataset_id` or `document_id` |
| `status` | String(50) | Index | `Pending`, `Downloading`, `Extracting`, `Indexing`, `Completed`, `Failed` |
| `progress_percent` | Float | Default 0.0 | Job progress percentage [0.0 - 100.0] |
| `started_at` | DateTime | Default UTC | Job start timestamp |
| `completed_at` | DateTime | Nullable | Completion timestamp |
| `error_details` | Text | Nullable | Error trace or message |
| `metadata_json` | Text | Nullable | Extra job statistics |

---

## 3. Classification & Structured Q&A

### 3.1 `document_classifications`
Stores model or rule classification of incoming loan agreements and regulatory files.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | String(36) | Primary Key | Classification UUID |
| `document_id` | String(100) | Index, Not Null | Subject document ID |
| `document_type` | String(100) | Not Null | 1 of 7 categories or `NEEDS_REVIEW` |
| `confidence` | Float | Default 1.0 | Classification confidence [0.0 - 1.0] |
| `supporting_features` | Text | Nullable | JSON serialized cue keywords |
| `model_version` | String(50) | Default 'heuristic-v1.0' | Classifier version |
| `classification_timestamp` | DateTime | Default UTC | Execution timestamp |
| `review_status` | String(50) | Default 'CONFIRMED' | `CONFIRMED` or `NEEDS_REVIEW` |

---

### 3.2 `generated_qa`
Verifiable question-answer pairs synthesized from regulatory chunks.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | String(36) | Primary Key | Q&A UUID |
| `dataset_id` | String(100) | Index, Nullable | Associated dataset |
| `source_document` | String(255) | Not Null | Source document filename |
| `section_identifier` | String(100) | Default 'General' | Section code |
| `page_number` | Integer | Default 1 | Source page number |
| `chunk_id` | String(36) | Index, Nullable | Foreign key to `document_chunks.id` |
| `question` | Text | Not Null | Grounded question text |
| `answer` | Text | Not Null | Verifiable answer text |
| `citation` | String(255) | Not Null | Exact statutory citation |
| `generation_model` | String(100) | Default 'grounded-extractor-v1' | Synthesizing model |
| `generation_timestamp` | DateTime | Default UTC | Generation timestamp |
| `validation_status` | String(50) | Default 'machine_generated' | `machine_generated`, `verified` |

---

## 4. Loan Documents & Term Extraction

### 4.1 `loan_documents`
User-uploaded or sample mortgage loan agreements and disclosures.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | String(36) | Primary Key | Loan document UUID |
| `filename` | String(255) | Not Null | File name |
| `file_type` | String(50) | Default 'pdf' | `pdf` or `txt` |
| `file_size` | Integer | Not Null | Byte length |
| `jurisdiction` | String(10) | Index, Default 'US' | `US` or `IN` |
| `doc_type` | String(100) | Not Null | Classification type |
| `status` | String(50) | Default 'UPLOADED'| `UPLOADED`, `PARSED`, `ANALYZED` |
| `upload_date` | DateTime | Default UTC | Upload timestamp |
| `file_path` | Text | Not Null | Disk location |

---

### 4.2 `extracted_loan_fields`
Structured loan terms extracted from loan contracts with page provenance.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | String(36) | Primary Key | Extracted field UUID |
| `loan_document_id` | String(36) | Foreign Key (`loan_documents.id`) | Associated loan |
| `field_name` | String(100) | Index, Not Null | Standardized term identifier |
| `field_value_str` | String(255) | Nullable | String value |
| `field_value_num` | Float | Nullable | Numeric value for rule comparison |
| `source_page` | Integer | Default 1 | Contract page where term appears |
| `source_excerpt` | Text | Not Null | Verbatim sentence or clause from contract |
| `confidence` | Float | Default 0.95 | Extraction confidence [0.0 - 1.0] |
| `is_verified` | Boolean | Default False | Human reviewer verification flag |
| `reviewer_corrected_value` | String(255) | Nullable | Overridden value if corrected by reviewer |

---

## 5. Compliance Auditing & Human Review

### 5.1 `compliance_analyses`
High-level summary of an automated audit evaluation.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | String(36) | Primary Key | Analysis UUID |
| `loan_document_id` | String(36) | Foreign Key (`loan_documents.id`) | Subject loan document |
| `jurisdiction` | String(10) | Index, Not Null | `US` or `IN` |
| `overall_status` | String(50) | Not Null | `POTENTIAL_ISSUE`, `NO_ISSUE_IDENTIFIED`, `NEEDS_REVIEW` |
| `summary` | Text | Not Null | Executive narrative synthesis |
| `generated_at` | DateTime | Default UTC | Completion timestamp |

---

### 5.2 `compliance_findings`
Granular findings mapped to individual statutory rules.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | String(36) | Primary Key | Finding UUID |
| `analysis_id` | String(36) | Foreign Key (`compliance_analyses.id`) | Parent analysis |
| `rule_id` | String(100) | Index, Not Null | e.g. `US-REGZ-ATR-001` |
| `category` | String(100) | Index, Not Null | Statutory domain |
| `severity` | String(20) | Default 'HIGH' | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` |
| `status` | String(50) | Not Null | `POTENTIAL_ISSUE`, `NO_ISSUE_IDENTIFIED`, `NEEDS_REVIEW` |
| `loan_field` | String(100) | Not Null | Evaluated contract term |
| `extracted_value` | String(255) | Nullable | Evaluated contract value |
| `reasoning` | Text | Not Null | Grounded explanatory reasoning |
| `recommended_action`| Text | Nullable | Corrective action advice |
| `review_status` | String(50) | Default 'PENDING' | `PENDING`, `ACCEPTED`, `REJECTED`, `MODIFIED` |

---

### 5.3 `review_tasks` & `review_decisions`
Supports the Human-in-the-Loop review queue.

| Table | Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- | :--- |
| `review_tasks` | `id` | String(36) | Primary Key | Review task UUID |
| `review_tasks` | `finding_id` | String(36) | Foreign Key (`compliance_findings.id`) | Flagged finding |
| `review_tasks` | `status` | String(50) | Index, Default 'PENDING' | `PENDING`, `RESOLVED` |
| `review_tasks` | `assigned_to` | String(100) | Nullable | Assigned compliance analyst |
| `review_decisions` | `id` | String(36) | Primary Key | Decision UUID |
| `review_decisions` | `review_task_id` | String(36) | Foreign Key (`review_tasks.id`) | Associated review task |
| `review_decisions` | `decision` | String(50) | Not Null | `ACCEPTED`, `REJECTED`, `MODIFIED` |
| `review_decisions` | `comments` | Text | Nullable | Reviewer justification rationale |

---

## 6. Audit & Public Lending Records

### 6.1 `audit_events`
Immutable SOC 2 compliant audit log.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | String(36) | Primary Key | Audit event UUID |
| `event_type` | String(100) | Index, Not Null | Event type name |
| `actor` | String(100) | Default 'system' | User or system agent |
| `entity_type` | String(100) | Not Null | Target entity table |
| `entity_id` | String(100) | Index, Not Null | Target entity ID |
| `payload` | Text | Not Null | Serialized JSON diff / payload |
| `timestamp` | DateTime | Index, Default UTC | Immutable timestamp |

---

### 6.2 `hmda_records`
Authentic CFPB Home Mortgage Disclosure Act (HMDA) Loan Application Register (LAR) records.

| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | Integer | Primary Key, Autoincrement | Record ID |
| `activity_year` | String(4) | Index | Disclosure year (`2023`) |
| `lei` | String(50) | Index | Legal Entity Identifier |
| `loan_type` | String(50) | Index | Conventional, FHA, VA, USDA |
| `loan_purpose` | String(50) | Index | Home purchase, Refinancing |
| `loan_amount` | Float | Not Null | Approved / requested principal |
| `action_taken` | String(100) | Index | Loan originated, Application denied |
| `interest_rate` | Float | Nullable | Contract interest rate |
| `rate_spread` | Float | Nullable | Spread over APOR benchmark |
| `property_value`| Float | Nullable | Assessed collateral value |
| `loan_to_value_ratio` | Float | Nullable | LTV ratio |
