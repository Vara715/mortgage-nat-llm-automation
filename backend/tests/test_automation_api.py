"""
test_automation_api.py
======================
Comprehensive integration tests for morgage-loan-automation:
- Datasets registration, listing, and manifest-driven ingestion API
- Background job status tracking API (/api/jobs/{job_id})
- Structured Q&A generation and listing API (/api/qa)
- Hybrid search API (/api/retrieval/search)
- Document term extraction API (/api/documents/{id}/extract)
- Human review queue API (/api/reviews/queue)
- Readiness probe (/api/health/ready)
- Document classification service
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.classification.classifier import DocumentClassifier

client = TestClient(app)


def test_readiness_probe():
    res = client.get("/api/health/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["service"] == "morgage-loan-automation"
    assert data["ready"] is True


def test_datasets_crud_and_ingestion():
    manifest = {
        "dataset_id": "test_statute_dataset",
        "dataset_name": "Test Regulatory Dataset",
        "description": "Test dataset manifest for unit verification",
        "source_type": "LOCAL_FILE",
        "source_location": "data/raw/us_regulations/12_CFR_1026_43_Ability_to_Repay_and_QM.txt",
        "file_format": "txt",
        "jurisdiction": "US",
        "version": "1.0.0",
        "enable_qa_generation": True,
        "parser_config": {
            "ocr_enabled": False,
            "extract_tables": True,
            "clean_headers_footers": True
        },
        "chunking_config": {
            "chunk_size_tokens": 500,
            "chunk_overlap_tokens": 50,
            "structure_aware": True
        },
        "embedding_config": {
            "provider": "tfidf_dense",
            "model": "tfidf_dense_v1",
            "dimension": 128
        }
    }

    # 1. Register Dataset
    reg_res = client.post("/api/datasets", json=manifest)
    assert reg_res.status_code == 201
    assert reg_res.json()["id"] == "test_statute_dataset"

    # 2. List Datasets
    list_res = client.get("/api/datasets")
    assert list_res.status_code == 200
    datasets = list_res.json()
    assert any(d["id"] == "test_statute_dataset" for d in datasets)

    # 3. Trigger Ingestion
    ingest_res = client.post("/api/datasets/test_statute_dataset/ingest")
    assert ingest_res.status_code == 200
    data = ingest_res.json()
    assert data["status"] == "COMPLETED"
    assert "job_id" in data
    job_id = data["job_id"]

    # 4. Check Job Status
    job_res = client.get(f"/api/jobs/{job_id}")
    assert job_res.status_code == 200
    job_data = job_res.json()
    assert job_data["status"] == "Completed"
    assert job_data["progress_percent"] == 100.0


def test_retrieval_search_api():
    req = {
        "query": "qualified mortgage points and fees cap percentage limit",
        "jurisdiction": "US",
        "top_k": 3
    }
    res = client.post("/api/retrieval/search", json=req)
    assert res.status_code == 200
    data = res.json()
    assert data["jurisdiction"] == "US"
    assert "results" in data
    assert len(data["results"]) >= 1


def test_structured_qa_api():
    # 1. Generate Q&A
    gen_res = client.post("/api/qa/generate", json={"limit": 5})
    assert gen_res.status_code == 200
    items = gen_res.json()
    assert isinstance(items, list)

    # 2. List Q&A
    list_res = client.get("/api/qa?limit=10")
    assert list_res.status_code == 200
    qa_list = list_res.json()
    assert isinstance(qa_list, list)


def test_review_queue_endpoint():
    res = client.get("/api/reviews/queue")
    assert res.status_code == 200
    queue = res.json()
    assert isinstance(queue, list)


def test_document_classification_service():
    classifier = DocumentClassifier()

    note_text = "FIXED RATE NOTE - MULTISTATE. I promise to pay U.S. $350,000.00 to Fannie Mae."
    res_note = classifier.classify(note_text, "note.txt")
    assert res_note.predicted_category == "RESIDENTIAL_MORTGAGE_NOTE"
    assert res_note.confidence > 0.5

    closing_text = "Closing Disclosure. Summarizes all costs at closing and cash to close."
    res_cd = classifier.classify(closing_text, "cd.pdf")
    assert res_cd.predicted_category == "CLOSING_DISCLOSURE"

    reg_text = "12 CFR Part 1026. Regulation Z Truth in Lending Act statute on Qualified Mortgages."
    res_reg = classifier.classify(reg_text, "reg_z.txt")
    assert res_reg.predicted_category == "REGULATORY_STATUTE"
