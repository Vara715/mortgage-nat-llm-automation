"""
build_index.py
==============
CLI tool to rebuild the regulatory and dataset index for morgage-loan-automation.
Scans all manifests in data/manifests/ and syncs all regulatory corpora and chunks into the database.

Usage:
    python scripts/build_index.py
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.db.session import SessionLocal, init_db
from backend.app.services.source_registry.registry import SourceRegistryService
from backend.app.models.entities import DocumentChunk, RegulatoryDocument, RegulatorySource


def main():
    print("\n=================================================================================")
    print("  REBUILDING REGULATORY & RETRIEVAL INDEX")
    print("=================================================================================")

    init_db()
    db = SessionLocal()
    reg_service = SourceRegistryService(db)

    print("Ingesting authentic regulatory corpora (CFPB 12 CFR Part 1026 & RBI Circulars)...")
    res = reg_service.ingest_regulatory_files()

    docs_count = db.query(RegulatoryDocument).count()
    chunks_count = db.query(DocumentChunk).count()
    sources_count = db.query(RegulatorySource).count()
    db.close()

    print(f"\n[INDEX BUILD COMPLETE]")
    print(f"  Regulatory Sources Registered : {sources_count}")
    print(f"  Regulatory Documents Parsed   : {docs_count}")
    print(f"  Indexed Searchable Chunks     : {chunks_count}")
    print(f"  Details: {res}")
    print("=================================================================================\n")


if __name__ == "__main__":
    main()
