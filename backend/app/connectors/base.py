"""
base.py
=======
Abstract base class for dataset and regulatory source connectors in morgage-loan-automation.
Ensures uniform interface for acquisition, checksum computation, validation, and provenance.
"""

from abc import ABC, abstractmethod
import hashlib
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


class BaseSourceConnector(ABC):
    """
    Abstract source connector establishing contracts for acquiring,
    validating, and recording provenance for diverse data sources.
    """

    def __init__(self, source_id: str, name: str, jurisdiction: Optional[str] = None):
        self.source_id = source_id
        self.name = name
        self.jurisdiction = jurisdiction
        self.created_at = datetime.now(timezone.utc)

    @abstractmethod
    def fetch(self) -> bytes:
        """Fetch raw content from the underlying source."""
        pass

    @abstractmethod
    def validate(self) -> bool:
        """Validate accessibility, format integrity, and constraints."""
        pass

    def compute_checksum(self, data: bytes) -> str:
        """Compute cryptographic SHA-256 checksum for provenance tracking."""
        return hashlib.sha256(data).hexdigest()

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """Return structured source metadata for audit registration."""
        pass
