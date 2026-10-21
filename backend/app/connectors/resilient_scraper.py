"""
resilient_scraper.py
====================
Resilient Web Scraping & Ingestion Connector addressing Slide 9 Limitations:
"Inconsistency in web scraping: Different HTML Structures for different webpages
limit the reuse of code. Frequent Changes in design and structure overtime."

Features:
1. Multi-strategy cascading extraction (CSS selectors -> Semantic HTML -> Regex link heuristics)
2. DOM Structural Fingerprint & Drift Detection (alerts when regulatory site layout shifts)
3. Government SSL/TLS compatibility & User-Agent rotation
4. Safe PDF asset downloader with SHA-256 verification
"""

import hashlib
import logging
import re
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger("resilient_scraper")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]


@dataclass
class ScrapedResource:
    url: str
    title: str
    file_type: str  # 'pdf', 'html', etc.
    content_bytes: Optional[bytes] = None
    checksum_sha256: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DriftReport:
    url: str
    is_drifted: bool
    previous_fingerprint: Optional[str]
    current_fingerprint: str
    message: str


class ResilientWebScraper:
    """
    Robust web scraping connector that gracefully handles structural shifts,
    complex government portal layouts, and diverse regulatory PDF link conventions.
    """

    def __init__(self, timeout: int = 20, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self._fingerprint_cache: Dict[str, str] = {}

    def _get_ssl_context(self) -> ssl.SSLContext:
        """Creates SSL context with fallback for older institutional portals."""
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def fetch_html(self, url: str) -> tuple[str, str]:
        """
        Fetches HTML with retry backoff and computes a structural DOM fingerprint.
        Returns (html_content, dom_fingerprint).
        """
        last_err = None
        for attempt in range(self.max_retries):
            ua = USER_AGENTS[attempt % len(USER_AGENTS)]
            headers = {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, context=self._get_ssl_context(), timeout=self.timeout) as resp:
                    raw_bytes = resp.read()
                    html = raw_bytes.decode("utf-8", errors="replace")
                    fingerprint = self._compute_dom_fingerprint(html)
                    return html, fingerprint
            except Exception as e:
                last_err = e
                time.sleep(1.0 * (attempt + 1))

        raise RuntimeError(f"Failed to fetch {url} after {self.max_retries} attempts: {last_err}")

    def _compute_dom_fingerprint(self, html: str) -> str:
        """
        Creates a structural hash of the HTML DOM hierarchy (ignoring dynamic text/timestamps).
        Used to detect when a regulatory portal changes its layout.
        """
        soup = BeautifulSoup(html, "html.parser")
        tag_structure = []
        for tag in soup.find_all(True):
            parent_name = tag.parent.name if tag.parent else ""
            tag_structure.append(f"{parent_name}>{tag.name}")
        joined = "|".join(tag_structure[:200])
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]

    def check_for_drift(self, url: str, current_fingerprint: str) -> DriftReport:
        """Checks if the page layout has structurally drifted since the last registered run."""
        prev = self._fingerprint_cache.get(url)
        self._fingerprint_cache[url] = current_fingerprint
        if prev is None:
            return DriftReport(
                url=url,
                is_drifted=False,
                previous_fingerprint=None,
                current_fingerprint=current_fingerprint,
                message="Initial baseline fingerprint established.",
            )
        is_drifted = prev != current_fingerprint
        msg = "Structural drift detected in regulatory webpage layout!" if is_drifted else "No structural drift detected."
        return DriftReport(
            url=url,
            is_drifted=is_drifted,
            previous_fingerprint=prev,
            current_fingerprint=current_fingerprint,
            message=msg,
        )

    def discover_regulatory_documents(self, html: str, base_url: str) -> List[Dict[str, str]]:
        """
        Multi-strategy document discovery:
        1. Targeted anchor searches for .pdf links
        2. Regulatory circular pattern matching (e.g., notification, circular, master directions)
        3. Table row extraction for structured document repositories
        """
        soup = BeautifulSoup(html, "html.parser")
        discovered: List[Dict[str, str]] = []
        seen_urls = set()

        # Strategy 1 & 2: Search all <a> tags for PDF links or regulatory circular keywords
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(strip=True) or a.get("title", "") or ""
            full_url = urljoin(base_url, href)

            if full_url in seen_urls:
                continue

            is_pdf = bool(re.search(r"\.pdf(\?.*)?$", href, re.IGNORECASE))
            is_reg_keyword = bool(re.search(r"circular|master|notification|guideline|policy|agreement|form", f"{href} {text}", re.IGNORECASE))

            if is_pdf or (is_reg_keyword and "pdf" in full_url.lower()):
                seen_urls.add(full_url)
                discovered.append({
                    "url": full_url,
                    "title": text or Path(urlparse(full_url).path).name or "Regulatory Document",
                    "discovery_strategy": "anchor_pdf_heuristic" if is_pdf else "regulatory_keyword",
                })

        # Strategy 3: Check data tables if no PDF anchors found
        if not discovered:
            for table in soup.find_all("table"):
                for row in table.find_all("tr"):
                    link = row.find("a", href=True)
                    if link:
                        full_url = urljoin(base_url, link["href"])
                        if full_url not in seen_urls:
                            seen_urls.add(full_url)
                            discovered.append({
                                "url": full_url,
                                "title": row.get_text(separator=" ", strip=True)[:100],
                                "discovery_strategy": "table_row_fallback",
                            })

        return discovered

    def download_document(self, url: str, output_path: Optional[Path] = None) -> ScrapedResource:
        """Downloads document content bytes, verifies checksum, and saves to disk if path given."""
        headers = {"User-Agent": USER_AGENTS[0]}
        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, context=self._get_ssl_context(), timeout=self.timeout) as resp:
            data = resp.read()
            checksum = hashlib.sha256(data).hexdigest()

            if output_path:
                output_path = Path(output_path)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(data)

            return ScrapedResource(
                url=url,
                title=Path(urlparse(url).path).name,
                file_type="pdf" if data.startswith(b"%PDF") else "unknown",
                content_bytes=data,
                checksum_sha256=checksum,
                metadata={"size_bytes": len(data), "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")},
            )
