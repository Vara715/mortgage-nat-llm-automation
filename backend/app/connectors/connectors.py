"""
connectors.py
=============
Concrete implementations of source connectors for morgage-loan-automation:
- LocalFileConnector: Reads from filesystem
- URLSourceConnector: Downloads remote files/statutes safely via HTTP
- APISourceConnector: Interacts with REST/JSON APIs
- CSVSourceConnector: Ingests tabular CSV datasets (e.g. HMDA records)
- JSONSourceConnector: Parses structured JSON schemas and documents
- JSONLSourceConnector: Parses newline-delimited JSON streaming datasets
- ParquetSourceConnector: Parses Apache Parquet columnar datasets
"""

import os
import json
import csv
import io
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Generator

from backend.app.connectors.base import BaseSourceConnector


class LocalFileConnector(BaseSourceConnector):
    """Acquires documents and datasets from the local filesystem."""

    def __init__(self, source_id: str, file_path: str, name: Optional[str] = None, jurisdiction: Optional[str] = None):
        super().__init__(source_id, name or Path(file_path).name, jurisdiction)
        self.file_path = Path(file_path)

    def validate(self) -> bool:
        return self.file_path.exists() and (self.file_path.is_file() or self.file_path.is_dir())

    def fetch(self) -> bytes:
        if not self.validate():
            raise FileNotFoundError(f"Source file or directory not found at: {self.file_path}")
        if self.file_path.is_dir():
            combined = []
            for p in sorted(self.file_path.glob("*.*")):
                if p.is_file() and p.suffix.lower() in [".txt", ".json", ".csv"]:
                    combined.append(p.read_bytes())
                elif p.is_file() and p.suffix.lower() == ".pdf":
                    try:
                        import pypdf
                        reader = pypdf.PdfReader(str(p))
                        pdf_text = "\n".join([page.extract_text() or "" for page in reader.pages])
                        combined.append(pdf_text.encode("utf-8", errors="replace"))
                    except Exception:
                        pass
            return b"\n\n--- NEXT DOCUMENT ---\n\n".join(combined) if combined else b""
        return self.file_path.read_bytes()

    def get_metadata(self) -> Dict[str, Any]:
        stat = self.file_path.stat() if self.validate() else None
        return {
            "source_id": self.source_id,
            "source_type": "LOCAL_FILE",
            "file_path": str(self.file_path),
            "file_size": stat.st_size if stat else 0,
            "last_modified": stat.st_mtime if stat else None,
            "jurisdiction": self.jurisdiction,
        }


class URLSourceConnector(BaseSourceConnector):
    """Acquires authoritative regulatory documents directly from public URLs."""

    def __init__(self, source_id: str, url: str, name: Optional[str] = None, jurisdiction: Optional[str] = None, timeout: int = 30):
        super().__init__(source_id, name or url, jurisdiction)
        self.url = url
        self.timeout = timeout

    def validate(self) -> bool:
        return self.url.startswith("http://") or self.url.startswith("https://")

    def fetch(self) -> bytes:
        if not self.validate():
            raise ValueError(f"Invalid URL protocol: {self.url}")
        req = urllib.request.Request(
            self.url,
            headers={"User-Agent": "morgage-loan-automation/1.0 ComplianceFetcher"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.URLError as e:
            raise ConnectionError(f"Failed to fetch content from {self.url}: {e}")

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": "URL",
            "url": self.url,
            "jurisdiction": self.jurisdiction,
        }


class APISourceConnector(BaseSourceConnector):
    """Interacts with regulatory or mortgage data REST APIs."""

    def __init__(self, source_id: str, endpoint: str, headers: Optional[Dict[str, str]] = None, name: Optional[str] = None, jurisdiction: Optional[str] = None):
        super().__init__(source_id, name or endpoint, jurisdiction)
        self.endpoint = endpoint
        self.headers = headers or {"Accept": "application/json"}

    def validate(self) -> bool:
        return self.endpoint.startswith("http://") or self.endpoint.startswith("https://")

    def fetch(self) -> bytes:
        req = urllib.request.Request(self.endpoint, headers=self.headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()

    def fetch_json(self) -> Any:
        raw = self.fetch()
        return json.loads(raw.decode("utf-8"))

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": "API",
            "endpoint": self.endpoint,
            "jurisdiction": self.jurisdiction,
        }


class CSVSourceConnector(BaseSourceConnector):
    """Parses tabular CSV datasets such as HMDA loan registries and census data."""

    def __init__(self, source_id: str, file_path_or_url: str, name: Optional[str] = None, delimiter: str = ",", jurisdiction: Optional[str] = None):
        super().__init__(source_id, name or "CSV Dataset", jurisdiction)
        self.location = file_path_or_url
        self.delimiter = delimiter

    def validate(self) -> bool:
        if self.location.startswith("http://") or self.location.startswith("https://"):
            return True
        return Path(self.location).exists()

    def fetch(self) -> bytes:
        if self.location.startswith("http"):
            conn = URLSourceConnector(self.source_id, self.location)
            return conn.fetch()
        return Path(self.location).read_bytes()

    def read_records(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        raw = self.fetch().decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(raw), delimiter=self.delimiter)
        records = []
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            records.append(row)
        return records

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": "CSV",
            "location": self.location,
            "delimiter": self.delimiter,
            "jurisdiction": self.jurisdiction,
        }


class JSONSourceConnector(BaseSourceConnector):
    """Parses structured JSON datasets and schemas."""

    def __init__(self, source_id: str, file_path_or_url: str, name: Optional[str] = None, jurisdiction: Optional[str] = None):
        super().__init__(source_id, name or "JSON Dataset", jurisdiction)
        self.location = file_path_or_url

    def validate(self) -> bool:
        if self.location.startswith("http"):
            return True
        return Path(self.location).exists()

    def fetch(self) -> bytes:
        if self.location.startswith("http"):
            return URLSourceConnector(self.source_id, self.location).fetch()
        return Path(self.location).read_bytes()

    def read_json(self) -> Any:
        raw = self.fetch()
        return json.loads(raw.decode("utf-8"))

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": "JSON",
            "location": self.location,
            "jurisdiction": self.jurisdiction,
        }


class JSONLSourceConnector(BaseSourceConnector):
    """Parses line-delimited JSON datasets (streaming / large scale)."""

    def __init__(self, source_id: str, file_path: str, name: Optional[str] = None, jurisdiction: Optional[str] = None):
        super().__init__(source_id, name or Path(file_path).name, jurisdiction)
        self.file_path = Path(file_path)

    def validate(self) -> bool:
        return self.file_path.exists() and self.file_path.is_file()

    def fetch(self) -> bytes:
        return self.file_path.read_bytes()

    def iter_records(self) -> Generator[Dict[str, Any], None, None]:
        with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def read_records(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        results = []
        for i, rec in enumerate(self.iter_records()):
            if limit and i >= limit:
                break
            results.append(rec)
        return results

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": "JSONL",
            "file_path": str(self.file_path),
            "jurisdiction": self.jurisdiction,
        }


class ParquetSourceConnector(BaseSourceConnector):
    """Parses Apache Parquet columnar datasets with fallback handling."""

    def __init__(self, source_id: str, file_path: str, name: Optional[str] = None, jurisdiction: Optional[str] = None):
        super().__init__(source_id, name or Path(file_path).name, jurisdiction)
        self.file_path = Path(file_path)

    def validate(self) -> bool:
        return self.file_path.exists() and self.file_path.is_file()

    def fetch(self) -> bytes:
        return self.file_path.read_bytes()

    def read_records(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        try:
            import pyarrow.parquet as pq
            table = pq.read_table(str(self.file_path))
            df = table.to_pandas()
            if limit:
                df = df.head(limit)
            return df.to_dict(orient="records")
        except ImportError:
            # Fallback if pyarrow is not installed: note the schema
            return [{"warning": "pyarrow not installed. Raw binary preserved.", "path": str(self.file_path)}]

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": "PARQUET",
            "file_path": str(self.file_path),
            "jurisdiction": self.jurisdiction,
        }
