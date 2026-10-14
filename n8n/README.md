# n8n Automation Workflows — morgage-loan-automation

This directory contains the five version-controlled, production-ready n8n workflow exports orchestrating the **morgage-loan-automation** engine:

1. **Workflow A: Dataset and Regulatory Source Ingestion** (`workflow_a_ingestion.json`)
2. **Workflow B: Loan Document Processing** (`workflow_b_loan_processing.json`)
3. **Workflow C: Compliance Analysis** (`workflow_c_compliance_analysis.json`)
4. **Workflow D: Human Review & Notifications** (`workflow_d_human_review.json`)
5. **Workflow E: Error Handling & Circuit Breaker** (`workflow_e_error_handling.json`)

---

## 1. Quickstart with Docker Compose

The n8n editor runs locally on port `5678` alongside the FastAPI backend, PostgreSQL (pgvector), and Redis:

```bash
docker-compose up -d
```

Access the visual workflow editor in your browser:
**URL:** [http://localhost:5678](http://localhost:5678)

---

## 2. Environment Variables

| Variable | Default Value | Purpose |
|---|---|---|
| `N8N_PORT` | `5678` | n8n web editor listening port |
| `N8N_BASIC_AUTH_ACTIVE` | `false` | Disabled for local dev; set to `true` in production |
| `BACKEND_API_BASE` | `http://backend:8000/api` | Internal Docker network URL to FastAPI backend |
| `GENERIC_TIMEZONE` | `UTC` | Standard UTC timestamp handling |

---

## 3. How to Import the Workflows into n8n

### Option A: Import via the n8n UI (Recommended)
1. Open [http://localhost:5678](http://localhost:5678).
2. Click **Workflows** in the left sidebar, then click the **Add workflow** button (or **+**).
3. Click the three dots (`...`) in the top right corner of the canvas and select **Import from File**.
4. Select any file from `n8n/workflows/` (e.g. `workflow_a_ingestion.json`).
5. Click **Save** (Ctrl+S / Cmd+S).
6. Repeat for Workflows B, C, D, and E.

### Option B: Automatic CLI Import (Inside Docker container)
```bash
docker exec -it morgage-loan-automation-n8n n8n import:workflow --input=/data/workflows/workflow_a_ingestion.json
docker exec -it morgage-loan-automation-n8n n8n import:workflow --input=/data/workflows/workflow_b_loan_processing.json
docker exec -it morgage-loan-automation-n8n n8n import:workflow --input=/data/workflows/workflow_c_compliance_analysis.json
docker exec -it morgage-loan-automation-n8n n8n import:workflow --input=/data/workflows/workflow_d_human_review.json
docker exec -it morgage-loan-automation-n8n n8n import:workflow --input=/data/workflows/workflow_e_error_handling.json
```

---

## 4. Workflow Descriptions & Trigger Points

### Workflow A: Dataset and Regulatory Source Ingestion
- **Triggers:**
  - `POST http://localhost:5678/webhook/dataset-ingest`
  - Cron Schedule: Daily at 2:00 AM UTC (`0 2 * * *`)
- **Action:** Validates dataset ID, calls `/api/datasets/{dataset_id}/ingest`, waits 3 seconds, polls job status, and logs success or routes to failure notification.

### Workflow B: Loan Document Processing
- **Trigger:** `POST http://localhost:5678/webhook/loan-process` with body `{"document_id": "<uuid>", "jurisdiction": "US"}`
- **Action:** Validates document reference, triggers `/api/documents/{id}/extract`, retrieves structured terms, verifies extraction quality, and forwards to Workflow C.

### Workflow C: Compliance Analysis
- **Trigger:** `POST http://localhost:5678/webhook/compliance-analyze`
- **Action:** Triggers `/api/compliance/analyze/{id}`, routes finding through Switch node:
  - If `POTENTIAL_ISSUE` or `NEEDS_REVIEW`: dispatches to Workflow D.
  - If `NO_ISSUE_IDENTIFIED`: records clean compliance finding with statutory disclaimer.

### Workflow D: Human Review & Notifications
- **Trigger:** `POST http://localhost:5678/webhook/human-review`
- **Action:** Fetches pending tasks from `/api/reviews/tasks?status=PENDING`, prepares structured reviewer notification alert, polls for human analyst decision, and logs audit event.

### Workflow E: Error Handling & Circuit Breaker
- **Trigger:** n8n `Global Error Trigger` (catches node failures across all workflows).
- **Action:** Extracts error details, sanitizes sensitive data (redacts SSN and PAN numbers), writes incident to backend immutable audit ledger (`POST /api/audit/event`), and alerts administrator.
