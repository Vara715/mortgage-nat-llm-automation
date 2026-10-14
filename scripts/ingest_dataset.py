"""
ingest_dataset.py
=================
CLI tool for dataset-agnostic ingestion in morgage-loan-automation.
Ingests any user-provided manifest file (JSON) into the platform.

Usage:
    python scripts/ingest_dataset.py --manifest data/manifests/cfpb_reg_z_manifest.json
    python scripts/ingest_dataset.py --manifest data/manifests/hmda_2023_manifest.json
"""

import sys
import json
import argparse
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.db.session import SessionLocal, init_db
from backend.app.schemas.dataset import DatasetManifest
from backend.app.services.ingestion.manifest_loader import DatasetIngestionEngine


def main():
    parser = argparse.ArgumentParser(description="Ingest a dataset into morgage-loan-automation via manifest.")
    parser.add_argument("--manifest", required=True, help="Path to the JSON dataset manifest file")
    args = parser.parse_args()

    manifest_file = Path(args.manifest)
    if not manifest_file.exists():
        print(f"[ERROR] Manifest file not found: {manifest_file}")
        sys.exit(1)

    print(f"Loading manifest: {manifest_file}...")
    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    manifest = DatasetManifest(**manifest_data)

    print(f"Dataset ID     : {manifest.dataset_id}")
    print(f"Dataset Name   : {manifest.dataset_name}")
    print(f"Source Type    : {manifest.source_type}")
    print(f"Location       : {manifest.source_location}")
    print(f"Jurisdiction   : {manifest.jurisdiction or 'Global'}")
    print(f"File Format    : {manifest.file_format}")

    init_db()
    db = SessionLocal()
    engine = DatasetIngestionEngine(db)

    print("\nStarting ingestion pipeline...")
    result = engine.ingest_manifest(manifest)
    db.close()

    print("\n[SUCCESS] Dataset ingested successfully!")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
