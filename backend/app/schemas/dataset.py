"""
dataset.py
==========
Pydantic schemas for dataset-agnostic manifests, dataset registration, and ingestion jobs.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ParserConfig(BaseModel):
    ocr_enabled: bool = False
    ocr_language: str = "eng"
    extract_tables: bool = True
    clean_headers_footers: bool = True


class ChunkingConfig(BaseModel):
    chunk_size_tokens: int = 600
    chunk_overlap_tokens: int = 100
    structure_aware: bool = True


class EmbeddingConfig(BaseModel):
    provider: str = "tfidf_dense"
    model: str = "tfidf_dense_v1"
    dimension: int = 128


class DatasetManifest(BaseModel):
    """
    Configurable dataset manifest per Section 4.
    Enables pluggable acquisition, parsing, chunking, and indexing
    for arbitrary user-provided regulatory or loan datasets.
    """
    dataset_id: str = Field(..., description="Unique dataset identifier")
    dataset_name: str = Field(..., description="Human-readable name")
    description: Optional[str] = Field(None, description="Detailed description")
    source_type: str = Field(..., description="'LOCAL_FILE', 'URL', 'API', 'CSV', 'JSON', 'JSONL', 'PARQUET'")
    source_location: str = Field(..., description="File path, directory path, URL, or API endpoint")
    file_format: str = Field(..., description="'pdf', 'csv', 'json', 'jsonl', 'txt', 'parquet'")
    jurisdiction: Optional[str] = Field(None, description="'US', 'IN', or null for multi-jurisdiction")
    version: str = Field("1.0.0", description="Dataset version tag")
    collection_date: Optional[str] = Field(None, description="Date data was acquired or published")
    license_notes: Optional[str] = Field(None, description="Usage constraints, public domain, or proprietary")
    selected_columns: Optional[List[str]] = Field(None, description="For tabular datasets, columns to ingest")
    classification_options: Optional[Dict[str, Any]] = Field(None, description="Document classifier options")
    parser_config: ParserConfig = Field(default_factory=ParserConfig)
    embedding_config: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    chunking_config: ChunkingConfig = Field(default_factory=ChunkingConfig)
    metadata_mapping: Optional[Dict[str, str]] = Field(None, description="Column or key name mappings")
    enable_qa_generation: bool = Field(False, description="Optionally generate structured Q&A pairs")
    access_retention: Optional[str] = Field("INDEFINITE", description="Retention policy for the dataset")


class DatasetCreate(BaseModel):
    manifest: DatasetManifest


class DatasetResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    source_type: str
    source_location: str
    file_format: str
    jurisdiction: Optional[str]
    version: str
    status: str
    checksum: Optional[str]
    created_at: Any


class ProcessingJobResponse(BaseModel):
    id: str
    job_type: str
    target_id: str
    status: str
    progress_percent: float
    started_at: Any
    completed_at: Optional[Any] = None
    error_details: Optional[str] = None
