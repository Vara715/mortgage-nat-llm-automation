"""
entities.py
===========
SQLAlchemy ORM models implementing the complete schema required by Section 7:
Preserves the chain:
Source -> Document Version -> Section/Page -> Chunk -> Retrieval Result -> Rule Evaluation -> Finding -> Evidence -> Human Review.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base


def utc_now():
    return datetime.now(timezone.utc)


def gen_uuid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# 1. Users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    username = Column(String(100), unique=True, nullable=False, index=True)
    full_name = Column(String(200))
    role = Column(String(50), default="analyst")  # 'analyst', 'reviewer', 'admin'
    created_at = Column(DateTime, default=utc_now)


# ---------------------------------------------------------------------------
# 2. Regulatory Sources & Documents
# ---------------------------------------------------------------------------
class RegulatorySource(Base):
    __tablename__ = "regulatory_sources"

    source_id = Column(String(100), primary_key=True)
    source_name = Column(String(255), nullable=False)
    source_url = Column(Text, nullable=False)
    source_type = Column(String(50), nullable=False)  # 'REGULATORY_STATUTE', 'CIRCULAR', etc.
    jurisdiction = Column(String(10), nullable=False, index=True)  # 'US' or 'IN'
    issuing_authority = Column(String(200), nullable=False)
    publication_date = Column(String(50))
    effective_from = Column(String(50))
    effective_until = Column(String(50), nullable=True)
    retrieved_at = Column(DateTime, default=utc_now)
    checksum = Column(String(64), nullable=False, index=True)
    document_version = Column(String(100))
    license_or_usage_notes = Column(Text)
    ingestion_status = Column(String(50), default="PENDING")  # 'PENDING', 'INDEXED', 'FAILED'
    extraction_quality = Column(Float, default=1.0)
    error_message = Column(Text, nullable=True)

    documents = relationship("RegulatoryDocument", back_populates="source", cascade="all, delete-orphan")


class RegulatoryDocument(Base):
    __tablename__ = "regulatory_documents"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    source_id = Column(String(100), ForeignKey("regulatory_sources.source_id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    jurisdiction = Column(String(10), nullable=False, index=True)
    doc_type = Column(String(50))
    file_path = Column(Text, nullable=False)
    total_pages = Column(Integer, default=1)
    created_at = Column(DateTime, default=utc_now)

    source = relationship("RegulatorySource", back_populates="documents")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    document_id = Column(String(36), ForeignKey("regulatory_documents.id"), nullable=False, index=True)
    version_tag = Column(String(100), nullable=False)
    effective_date = Column(String(50))
    change_summary = Column(Text)
    created_at = Column(DateTime, default=utc_now)

    document = relationship("RegulatoryDocument", back_populates="versions")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    document_id = Column(String(36), ForeignKey("regulatory_documents.id"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    char_count = Column(Integer, default=0)
    word_count = Column(Integer, default=0)
    extraction_quality = Column(Float, default=1.0)
    ocr_applied = Column(Boolean, default=False)

    document = relationship("RegulatoryDocument", back_populates="pages")


class RegulatorySection(Base):
    __tablename__ = "regulatory_sections"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    document_id = Column(String(36), ForeignKey("regulatory_documents.id"), nullable=False, index=True)
    section_code = Column(String(100), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    hierarchy_level = Column(Integer, default=1)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    document_id = Column(String(36), ForeignKey("regulatory_documents.id"), nullable=False, index=True)
    page_number = Column(Integer, default=1)
    section_id = Column(String(100), default="General", index=True)
    section_code = Column(String(100), default="General")
    chunk_index = Column(Integer, default=0)
    text = Column(Text, nullable=False)
    normalized_text = Column(Text, nullable=False)
    token_count = Column(Integer, default=0)
    category = Column(String(100), nullable=False, index=True)
    jurisdiction = Column(String(10), nullable=False, index=True)
    dataset_id = Column(String(100), nullable=True, index=True)
    embedding_json = Column(Text, nullable=True)  # JSON-encoded vector embedding representation
    created_at = Column(DateTime, default=utc_now)

    document = relationship("RegulatoryDocument", back_populates="chunks")


class SourceIngestionJob(Base):
    __tablename__ = "source_ingestion_jobs"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    source_id = Column(String(100), nullable=False, index=True)
    status = Column(String(50), default="Pending")  # 'Pending', 'Downloading', 'Extracting', 'Indexing', 'Completed', 'Failed'
    total_chunks = Column(Integer, default=0)
    extracted_pages = Column(Integer, default=0)
    progress_percent = Column(Float, default=0.0)
    started_at = Column(DateTime, default=utc_now)
    completed_at = Column(DateTime, nullable=True)
    error_details = Column(Text, nullable=True)


# ---------------------------------------------------------------------------
# 3. Loan Documents & Extracted Fields
# ---------------------------------------------------------------------------
class LoanDocument(Base):
    __tablename__ = "loan_documents"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), default="pdf")
    file_size = Column(Integer, default=0)
    jurisdiction = Column(String(10), default="US", index=True)  # 'US' or 'IN'
    doc_type = Column(String(100), default="Residential Mortgage Note")
    status = Column(String(50), default="UPLOADED")  # 'UPLOADED', 'PARSED', 'ANALYZED'
    upload_date = Column(DateTime, default=utc_now)
    file_path = Column(Text, nullable=False)

    extracted_fields = relationship("ExtractedLoanField", back_populates="loan_document", cascade="all, delete-orphan")
    analyses = relationship("ComplianceAnalysis", back_populates="loan_document", cascade="all, delete-orphan")


class ExtractedLoanField(Base):
    __tablename__ = "extracted_loan_fields"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    loan_document_id = Column(String(36), ForeignKey("loan_documents.id"), nullable=False, index=True)
    field_name = Column(String(100), nullable=False, index=True)
    field_value_str = Column(String(255), nullable=True)
    field_value_num = Column(Float, nullable=True)
    source_page = Column(Integer, default=1)
    source_excerpt = Column(Text, nullable=False)
    confidence = Column(Float, default=0.95)
    is_verified = Column(Boolean, default=False)
    reviewer_corrected_value = Column(String(255), nullable=True)

    loan_document = relationship("LoanDocument", back_populates="extracted_fields")


# ---------------------------------------------------------------------------
# 4. Compliance Rules & Analyses
# ---------------------------------------------------------------------------
class ComplianceRule(Base):
    __tablename__ = "compliance_rules"

    rule_id = Column(String(100), primary_key=True)
    rule_name = Column(String(255), nullable=False)
    jurisdiction = Column(String(10), nullable=False, index=True)
    citation = Column(String(255), nullable=False)
    effective_period = Column(String(100))
    applicability_conditions = Column(Text)
    severity = Column(String(20), default="HIGH")  # 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    version = Column(String(20), default="1.0")


class ComplianceAnalysis(Base):
    __tablename__ = "compliance_analyses"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    loan_document_id = Column(String(36), ForeignKey("loan_documents.id"), nullable=False, index=True)
    jurisdiction = Column(String(10), nullable=False, index=True)
    overall_status = Column(String(50), nullable=False)  # 'POTENTIAL_ISSUE', 'NO_ISSUE_IDENTIFIED', 'NEEDS_REVIEW'
    summary = Column(Text)
    generated_at = Column(DateTime, default=utc_now)

    loan_document = relationship("LoanDocument", back_populates="analyses")
    findings = relationship("ComplianceFinding", back_populates="analysis", cascade="all, delete-orphan")


class ComplianceFinding(Base):
    __tablename__ = "compliance_findings"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    analysis_id = Column(String(36), ForeignKey("compliance_analyses.id"), nullable=False, index=True)
    rule_id = Column(String(100), nullable=False, index=True)
    category = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), default="HIGH")
    status = Column(String(50), nullable=False)  # 'POTENTIAL_ISSUE', 'NO_ISSUE_IDENTIFIED', 'NEEDS_REVIEW', 'NOT_EVALUABLE'
    loan_field = Column(String(100), nullable=False)
    extracted_value = Column(String(255), nullable=True)
    reasoning = Column(Text, nullable=False)
    recommended_action = Column(Text, nullable=True)
    review_status = Column(String(50), default="PENDING")  # 'PENDING', 'ACCEPTED', 'REJECTED', 'MODIFIED'

    analysis = relationship("ComplianceAnalysis", back_populates="findings")
    evidence = relationship("FindingEvidence", back_populates="finding", cascade="all, delete-orphan")
    review_tasks = relationship("ReviewTask", back_populates="finding", cascade="all, delete-orphan")


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    finding_id = Column(String(36), ForeignKey("compliance_findings.id"), nullable=False, index=True)
    citation = Column(String(255), nullable=False)
    source_name = Column(String(255), nullable=False)
    source_url = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    quoted_text = Column(Text, nullable=False)
    score = Column(Float, default=1.0)

    finding = relationship("ComplianceFinding", back_populates="evidence")


# ---------------------------------------------------------------------------
# 5. Human-in-the-Loop Review
# ---------------------------------------------------------------------------
class ReviewTask(Base):
    __tablename__ = "review_tasks"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    finding_id = Column(String(36), ForeignKey("compliance_findings.id"), nullable=False, index=True)
    status = Column(String(50), default="PENDING", index=True)  # 'PENDING', 'RESOLVED'
    assigned_to = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    finding = relationship("ComplianceFinding", back_populates="review_tasks")
    decisions = relationship("ReviewDecision", back_populates="task", cascade="all, delete-orphan")


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    review_task_id = Column(String(36), ForeignKey("review_tasks.id"), nullable=False, index=True)
    reviewer_id = Column(String(100), nullable=False)
    decision = Column(String(50), nullable=False)  # 'ACCEPTED', 'REJECTED', 'MODIFIED'
    original_status = Column(String(50), nullable=False)
    new_status = Column(String(50), nullable=False)
    comments = Column(Text, nullable=True)
    decided_at = Column(DateTime, default=utc_now)

    task = relationship("ReviewTask", back_populates="decisions")


# ---------------------------------------------------------------------------
# 6. Immutable Audit Events
# ---------------------------------------------------------------------------
class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    event_type = Column(String(100), nullable=False, index=True)
    actor = Column(String(100), default="system")
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(String(100), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=utc_now, index=True)


# ---------------------------------------------------------------------------
# 7. HMDA Public Mortgage Records & Imports
# ---------------------------------------------------------------------------
class HMDARecord(Base):
    __tablename__ = "hmda_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    activity_year = Column(String(4), index=True)
    lei = Column(String(50), index=True)
    uli = Column(String(100), nullable=True)
    loan_type = Column(String(50), index=True)
    loan_purpose = Column(String(50), index=True)
    occupancy_type = Column(String(50))
    loan_amount = Column(Float, nullable=False)
    action_taken = Column(String(100), index=True)
    action_taken_date = Column(String(20), nullable=True)
    state_code = Column(String(10), index=True)
    county_code = Column(String(10), index=True)
    interest_rate = Column(Float, nullable=True)
    rate_spread = Column(Float, nullable=True)
    property_value = Column(Float, nullable=True)
    loan_to_value_ratio = Column(Float, nullable=True)


class HMDADatasetImport(Base):
    __tablename__ = "hmda_dataset_imports"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    filename = Column(String(255), nullable=False)
    total_records = Column(Integer, default=0)
    imported_at = Column(DateTime, default=utc_now)
    source_checksum = Column(String(64), nullable=False)


# ---------------------------------------------------------------------------
# 8. Datasets & Dataset Versions (Dataset-Agnostic Management)
# ---------------------------------------------------------------------------
class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String(100), primary_key=True)  # dataset_id
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_type = Column(String(50), nullable=False)  # 'LOCAL_FILE', 'URL', 'API', 'CSV', 'JSON', 'PARQUET'
    source_location = Column(Text, nullable=False)
    file_format = Column(String(50), nullable=False)  # 'pdf', 'csv', 'json', 'parquet', etc.
    jurisdiction = Column(String(10), nullable=True, index=True)   # 'US', 'IN', or null
    version = Column(String(50), default="1.0.0")
    created_at = Column(DateTime, default=utc_now)
    checksum = Column(String(64), nullable=True)
    manifest_config = Column(Text, nullable=True)     # JSON configuration
    status = Column(String(50), default="ACTIVE")     # 'ACTIVE', 'ARCHIVED', 'PROCESSING'

    versions = relationship("DatasetVersion", back_populates="dataset", cascade="all, delete-orphan")


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    dataset_id = Column(String(100), ForeignKey("datasets.id"), nullable=False, index=True)
    version_tag = Column(String(50), nullable=False)
    record_count = Column(Integer, default=0)
    checksum = Column(String(64), nullable=False)
    created_at = Column(DateTime, default=utc_now)
    changelog = Column(Text, nullable=True)

    dataset = relationship("Dataset", back_populates="versions")


# ---------------------------------------------------------------------------
# 9. Document Classifications
# ---------------------------------------------------------------------------
class DocumentClassification(Base):
    __tablename__ = "document_classifications"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    document_id = Column(String(100), nullable=False, index=True)
    document_type = Column(String(100), nullable=False)  # e.g. 'REGULATORY_STATUTE', 'LOAN_AGREEMENT', etc.
    confidence = Column(Float, default=1.0)
    supporting_features = Column(Text, nullable=True)    # JSON features / cues
    model_version = Column(String(50), default="heuristic-v1.0")
    classification_timestamp = Column(DateTime, default=utc_now)
    review_status = Column(String(50), default="CONFIRMED")  # 'CONFIRMED', 'NEEDS_REVIEW'


# ---------------------------------------------------------------------------
# 10. Generated Structured Q&A
# ---------------------------------------------------------------------------
class GeneratedQA(Base):
    __tablename__ = "generated_qa"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    dataset_id = Column(String(100), nullable=True, index=True)
    source_document = Column(String(255), nullable=False)
    section_identifier = Column(String(100), default="General")
    page_number = Column(Integer, default=1)
    chunk_id = Column(String(36), nullable=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    citation = Column(String(255), nullable=False)
    generation_model = Column(String(100), default="grounded-extractor-v1")
    generation_timestamp = Column(DateTime, default=utc_now)
    validation_status = Column(String(50), default="machine_generated")  # 'machine_generated', 'verified'


# ---------------------------------------------------------------------------
# 11. Generic Processing / Ingestion Jobs
# ---------------------------------------------------------------------------
class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    job_type = Column(String(50), nullable=False, index=True)  # 'INGESTION', 'EXTRACTION', 'COMPLIANCE', 'QA_GEN'
    target_id = Column(String(100), nullable=False, index=True) # dataset_id or doc_id
    status = Column(String(50), default="Pending", index=True) # 'Pending', 'Downloading', 'Extracting', 'Indexing', 'Completed', 'Failed'
    progress_percent = Column(Float, default=0.0)
    started_at = Column(DateTime, default=utc_now)
    completed_at = Column(DateTime, nullable=True)
    error_details = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)
