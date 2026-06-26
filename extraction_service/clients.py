"""HTTP clients for CELLAR and ECHA."""

import asyncio
import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

import httpx
from bs4 import BeautifulSoup
from SPARQLWrapper import SPARQLWrapper, JSON

from config import settings

logger = logging.getLogger(__name__)


class CellarClient:
    """Client for CELLAR SPARQL endpoint and REST API."""
    
    # Watchlist of CELEX numbers to monitor
    WATCHLIST = [
        "32011L0065",  # RoHS
        "32006R1907",  # REACH
        "32012L0019",  # WEEE
        "32023R1542",  # Battery Regulation
        "32025R0040",  # PPWR
        "32023R0988",  # GPSR
        "32014L0053",  # RED
        "32024R1781",  # ESPR
        "32009L0048",  # Toy Safety
        "32017R0745",  # MDR
        "32019R1021",  # POPs
    ]
    
    def __init__(self):
        self.sparql_endpoint = settings.cellar_sparql_endpoint
        self.rest_base_url = settings.cellar_rest_base_url
        self.timeout = settings.cellar_timeout
        self.page_size = settings.cellar_page_size
        self.user_agent = settings.user_agent
        self.max_retries = settings.max_retries
        self.retry_backoff = settings.retry_backoff_factor
        
        # HTTP client for REST API
        self.client = httpx.Client(
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
        )
        
        # SPARQL wrapper
        self.sparql = SPARQLWrapper(self.sparql_endpoint)
        self.sparql.setReturnFormat(JSON)
        self.sparql.addCustomHttpHeader("User-Agent", self.user_agent)
    
    def __del__(self):
        """Close HTTP client on cleanup."""
        if hasattr(self, "client"):
            self.client.close()
    
    def build_sparql_query(
        self,
        cursor: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> str:
        """Build SPARQL query for watchlist documents."""
        # Build CELEX filter
        celex_filter = " || ".join([f'?celex = "{celex}"' for celex in self.WATCHLIST])
        
        # Build cursor filter if provided
        cursor_filter = ""
        if cursor:
            cursor_str = cursor.strftime("%Y-%m-%dT%H:%M:%S")
            cursor_filter = f"FILTER(?modified > '{cursor_str}'^^xsd:dateTime)"
        
        query = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        
        SELECT DISTINCT ?celex ?modified ?title ?date
        WHERE {{
            ?work cdm:work_id_document ?celex .
            ?work cdm:work_date_document ?date .
            ?work cdm:work_title ?title .
            ?work cdm:work_date_modification ?modified .
            
            FILTER({celex_filter})
            {cursor_filter}
            
            FILTER(lang(?title) = "en" || lang(?title) = "")
        }}
        ORDER BY ?modified
        LIMIT {limit}
        OFFSET {offset}
        """
        
        return query
    
    def discover_documents(
        self,
        cursor: Optional[datetime] = None,
    ) -> list[dict]:
        """
        Discover new/changed documents using SPARQL.
        
        Returns list of dicts with: celex, modified, title, date
        """
        if not settings.enable_cellar_sparql:
            logger.info("CELLAR SPARQL discovery disabled")
            return []
        
        all_results = []
        offset = 0
        
        while True:
            query = self.build_sparql_query(cursor, self.page_size, offset)
            
            try:
                self.sparql.setQuery(query)
                results = self.sparql.query().convert()
                
                bindings = results.get("results", {}).get("bindings", [])
                if not bindings:
                    break
                
                for binding in bindings:
                    all_results.append({
                        "celex": binding.get("celex", {}).get("value", ""),
                        "modified": binding.get("modified", {}).get("value", ""),
                        "title": binding.get("title", {}).get("value", ""),
                        "date": binding.get("date", {}).get("value", ""),
                    })
                
                logger.info(f"SPARQL query returned {len(bindings)} results (offset={offset})")
                
                # If we got fewer results than page_size, we're done
                if len(bindings) < self.page_size:
                    break
                
                offset += self.page_size
                
                # Rate limiting: small delay between pages
                time.sleep(0.5)
                
            except Exception as e:
                logger.error(f"SPARQL query failed: {e}")
                break
        
        logger.info(f"Discovered {len(all_results)} documents")
        return all_results
    
    def resolve_consolidated_celex(self, celex: str) -> str:
        """
        Resolve to consolidated version if available.
        
        Consolidated versions have CELEX sector 0 (e.g., 02011L0065-YYYYMMDD).
        For now, we'll use the original CELEX and let the REST API handle it.
        """
        # TODO: Implement proper consolidated version resolution via SPARQL
        # For MVP, return original CELEX
        return celex
    
    def fetch_formex_xml(
        self,
        celex: str,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
    ) -> Optional[tuple[str, dict]]:
        """
        Fetch Formex XML for a CELEX document.
        
        Returns tuple of (xml_content, headers) or None if 304 Not Modified.
        """
        # Construct URL
        params = {"uri": f"CELEX:{celex}", "format": "formex"}
        url = f"{self.rest_base_url}?{urlencode(params)}"
        
        # Build headers for conditional GET
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        
        # Retry logic with exponential backoff
        for attempt in range(self.max_retries):
            try:
                response = self.client.get(url, headers=headers)
                
                # Handle 304 Not Modified
                if response.status_code == 304:
                    logger.info(f"Document {celex} not modified (304)")
                    return None
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited (429), waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue
                
                # Handle server errors with backoff
                if response.status_code >= 500:
                    wait_time = self.retry_backoff ** attempt
                    logger.warning(f"Server error ({response.status_code}), retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                
                # Raise for other errors
                response.raise_for_status()
                
                # Extract caching headers
                cache_headers = {
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                }
                
                logger.info(f"Fetched Formex XML for {celex} ({len(response.content)} bytes)")
                return response.text, cache_headers
                
            except httpx.HTTPError as e:
                logger.error(f"HTTP error fetching {celex}: {e}")
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(self.retry_backoff ** attempt)
        
        return None


class EchaClient:
    """Client for ECHA SVHC Candidate List."""
    
    def __init__(self):
        self.candidate_list_url = settings.echa_candidate_list_url
        self.timeout = settings.echa_timeout
        self.cache_ttl_hours = settings.echa_cache_ttl_hours
        self.user_agent = settings.user_agent
        self.max_retries = settings.max_retries
        self.retry_backoff = settings.retry_backoff_factor
        
        # HTTP client
        self.client = httpx.Client(
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
        )
        
        # Cache
        self._cache: Optional[dict] = None
        self._cache_timestamp: Optional[datetime] = None
    
    def __del__(self):
        """Close HTTP client on cleanup."""
        if hasattr(self, "client"):
            self.client.close()
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        if self._cache is None or self._cache_timestamp is None:
            return False
        
        age_hours = (datetime.now(timezone.utc) - self._cache_timestamp).total_seconds() / 3600
        return age_hours < self.cache_ttl_hours
    
    def fetch_candidate_list(self, force_refresh: bool = False) -> list[dict]:
        """
        Fetch ECHA SVHC Candidate List.
        
        Returns list of dicts with: substance_name, cas_number, date_inclusion, reason
        """
        if not settings.enable_echa_fetch:
            logger.info("ECHA fetch disabled")
            return []
        
        # Check cache
        if not force_refresh and self._is_cache_valid():
            logger.info("Using cached ECHA data")
            return self._cache
        
        # Retry logic
        for attempt in range(self.max_retries):
            try:
                response = self.client.get(self.candidate_list_url)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited (429), waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue
                
                # Handle server errors with backoff
                if response.status_code >= 500:
                    wait_time = self.retry_backoff ** attempt
                    logger.warning(f"Server error ({response.status_code}), retrying in {wait_time}s")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                
                # Parse HTML table
                substances = self._parse_candidate_list(response.text)
                
                # Update cache
                self._cache = substances
                self._cache_timestamp = datetime.now(timezone.utc)
                
                logger.info(f"Fetched {len(substances)} substances from ECHA")
                return substances
                
            except httpx.HTTPError as e:
                logger.error(f"HTTP error fetching ECHA: {e}")
                if attempt == self.max_retries - 1:
                    # Fall back to cache if available
                    if self._cache is not None:
                        logger.warning("Using stale cache due to fetch failure")
                        return self._cache
                    raise
                time.sleep(self.retry_backoff ** attempt)
        
        return []
    
    def _parse_candidate_list(self, html: str) -> list[dict]:
        """Parse ECHA Candidate List HTML table."""
        soup = BeautifulSoup(html, "lxml")
        
        # Find the table (structure may vary, this is a best-effort parse)
        table = soup.find("table")
        if not table:
            logger.warning("No table found in ECHA HTML")
            return []
        
        substances = []
        rows = table.find_all("tr")[1:]  # Skip header row
        
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 3:
                continue
            
            try:
                substance = {
                    "substance_name": cols[0].get_text(strip=True),
                    "cas_number": cols[1].get_text(strip=True) if len(cols) > 1 else "",
                    "date_inclusion": cols[2].get_text(strip=True) if len(cols) > 2 else "",
                    "reason": cols[3].get_text(strip=True) if len(cols) > 3 else "",
                }
                substances.append(substance)
            except Exception as e:
                logger.warning(f"Failed to parse row: {e}")
                continue
        
        return substances
    
    def detect_changes(self, previous_list: list[dict]) -> dict:
        """
        Detect changes between current and previous candidate list.
        
        Returns dict with: added, modified, unchanged
        """
        current_list = self.fetch_candidate_list()
        
        # Build lookup by substance name
        previous_map = {s["substance_name"]: s for s in previous_list}
        current_map = {s["substance_name"]: s for s in current_list}
        
        added = []
        modified = []
        unchanged = []
        
        for name, substance in current_map.items():
            if name not in previous_map:
                added.append(substance)
            elif substance != previous_map[name]:
                modified.append(substance)
            else:
                unchanged.append(substance)
        
        logger.info(
            f"ECHA changes: {len(added)} added, {len(modified)} modified, "
            f"{len(unchanged)} unchanged"
        )
        
        return {
            "added": added,
            "modified": modified,
            "unchanged": unchanged,
        }
