# n8n Automation Workflows Architecture — morgage-loan-automation

The **morgage-loan-automation** platform integrates **n8n** as its orchestration layer. The workflow automation coordinates asynchronous jobs, long-running document processing, human-in-the-loop review queues, and failure notifications.

---

## 1. Visual Topology of the 5 Workflows

```
┌────────────────────────────────────────────────────────────────────────┐
│                        n8n WORKFLOW TOPOLOGY                           │
└────────────────────────────────────────────────────────────────────────┘

[Workflow A: Ingestion]
  Webhook / Cron (2 AM) ───► Validate Dataset ───► POST /api/datasets/{id}/ingest
                                                         │
                                               Wait 3s & Poll /api/jobs/{id}
                                                         │
                                        ┌────────────────┴───────────────┐
                                        ▼                                ▼
                                  [Completed]                        [Failed]
                               Record Success                   Notify Admin

[Workflow B: Loan Processing]
  Webhook /loan-process ───► Validate Doc ID ───► POST /api/documents/{id}/extract
                                                         │
                                              Wait 2s & GET /extraction
                                                         │
                                        ┌────────────────┴───────────────┐
                                        ▼                                ▼
                                  [Fields >= 1]                     [Fields == 0]
                            Forward to Workflow C                Flag for Manual OCR

[Workflow C: Compliance Analysis]
  Webhook /compliance-analyze ──► Validate ───► POST /api/compliance/analyze/{id}
                                                         │
                                        ┌────────────────┴───────────────┐
                                        ▼                                ▼
                           [POTENTIAL_ISSUE / REVIEW]           [NO_ISSUE_IDENTIFIED]
                              Trigger Workflow D                 Record Clean Finding

[Workflow D: Human Review (HITL)]
  Webhook /human-review ───► Format Task ───► Fetch /api/reviews/queue
                                                         │
                                             Dispatch Reviewer Alert
                                                         │
                                            Wait & Poll Analysis Decision
                                                         │
                                                 Log Audit Event

[Workflow E: Global Error Handling]
  Global Error Trigger ───► Sanitize / Redact PII ───► POST /api/audit/event ───► Admin Incident Alert
```

---

## 2. Detailed Node Mapping

### Workflow A: Dataset and Regulatory Source Ingestion (`workflow_a_ingestion.json`)
- **Node 1: Webhook Trigger** — Listens on `POST /webhook/dataset-ingest`.
- **Node 2: Schedule Trigger** — Automatically triggers daily at 2:00 AM UTC (`0 2 * * *`).
- **Node 3: Validate Dataset Identifier** — Validates `dataset_id` against configured manifest repository.
- **Node 4: Trigger Backend Ingestion API** — Calls `POST /api/datasets/{{dataset_id}}/ingest`.
- **Node 5: Wait for Processing** — Non-blocking 3-second wait for worker execution.
- **Node 6: Poll Ingestion Job Status** — Calls `GET /api/jobs/{{job_id}}`.
- **Node 7: Is Job Completed?** — Evaluates whether `status === "Completed"`.
- **Node 8/9: Record Success / Notify Admin** — Logs outcome to audit ledger or emits incident.

### Workflow B: Loan Document Processing (`workflow_b_loan_processing.json`)
- **Node 1: Loan Upload Webhook** — Receives document ID from upload service.
- **Node 2: Validate Document Request** — Checks file presence and jurisdiction.
- **Node 3: Trigger Loan Term Extraction** — Calls `POST /api/documents/{id}/extract`.
- **Node 4: Wait for Extractor** — 2-second worker execution delay.
- **Node 5: Retrieve Structured Terms** — Calls `GET /api/documents/{id}/extraction`.
- **Node 6: Fields Extracted Successfully?** — Validates that at least 1 critical term was parsed.
- **Node 7: Forward to Compliance Analysis** — Dispatches webhook to Workflow C.

### Workflow C: Compliance Analysis (`workflow_c_compliance_analysis.json`)
- **Node 1: Analysis Webhook Trigger** — Listens on `POST /webhook/compliance-analyze`.
- **Node 2: Validate Analysis Request** — Validates request payload.
- **Node 3: Execute Compliance Analysis** — Calls `POST /api/compliance/analyze/{id}`.
- **Node 4: Route by Compliance Finding** — Switch node routing by `overall_status`:
  - `POTENTIAL_ISSUE` -> Triggers Workflow D.
  - `NEEDS_REVIEW` -> Triggers Workflow D.
  - `NO_ISSUE_IDENTIFIED` -> Logs clean finding with mandatory legal disclaimer.

### Workflow D: Human Review & Notifications (`workflow_d_human_review.json`)
- **Node 1: Review Required Trigger** — Listens on `POST /webhook/human-review`.
- **Node 2: Format Review Task Details** — Formats finding summary, citation, and evidence.
- **Node 3: Fetch Review Queue** — Calls `GET /api/reviews/tasks?status=PENDING`.
- **Node 4: Prepare Reviewer Notification** — Prepares alert message.
- **Node 5: Wait for Analyst Assessment** — Bounded status polling loop.
- **Node 6: Check Analysis Decision Status** — Verifies analyst decision recorded via API.
- **Node 7: Log HITL Audit Event** — Writes event to immutable audit log.

### Workflow E: Error Handling & Circuit Breaker (`workflow_e_error_handling.json`)
- **Node 1: Global Workflow Error Trigger** — Standard n8n Error Trigger.
- **Node 2: Sanitize Error & Redact PII** — Uses regex to strip SSN (`\d{3}-\d{2}-\d{4}`) and PAN (`[A-Z]{5}[0-9]{4}[A-Z]{1}`).
- **Node 3: Log to Backend Audit Ledger** — Calls `POST /api/audit/event`.
- **Node 4: Emit Sanitized Admin Incident** — Alerts administrator with zero private borrower data exposure.
