"""Change detection and content hashing for deduplication."""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class ContentHasher:
    """Content hasher for requirement deduplication."""
    
    # Fields to include in hash (excludes timestamps and IDs)
    HASH_FIELDS = [
        "title",
        "summary",
        "regulation_family",
        "reference",
        "scope",
        "deadline_date",
        "severity",
        "action_required",
        "effective_date",
    ]
    
    def calculate_hash(self, requirement_data: dict) -> str:
        """
        Calculate SHA-256 hash of requirement content.
        
        Excludes: update_id, access_timestamp, created_at, updated_at
        Includes: title, summary, scope, deadline, severity, action
        """
        # Extract fields for hashing
        hash_data = {}
        for field in self.HASH_FIELDS:
            value = requirement_data.get(field)
            if value is not None:
                # Normalize value
                if isinstance(value, dict):
                    # Sort dict keys for consistent hashing
                    value = json.dumps(value, sort_keys=True)
                elif isinstance(value, list):
                    # Sort list for consistent hashing
                    value = json.dumps(sorted(value))
                elif hasattr(value, "isoformat"):
                    # Convert dates to ISO format
                    value = value.isoformat()
                else:
                    value = str(value)
                
                # Normalize whitespace
                value = self._normalize_whitespace(value)
                hash_data[field] = value
        
        # Create deterministic JSON string
        hash_string = json.dumps(hash_data, sort_keys=True)
        
        # Calculate SHA-256 hash
        hash_bytes = hashlib.sha256(hash_string.encode("utf-8")).digest()
        hash_hex = hash_bytes.hex()
        
        logger.debug(f"Calculated hash: {hash_hex[:16]}...")
        return hash_hex
    
    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace in text."""
        # Replace multiple spaces with single space
        text = " ".join(text.split())
        # Remove leading/trailing whitespace
        text = text.strip()
        return text
    
    def compare_hashes(self, hash1: str, hash2: str) -> bool:
        """Compare two hashes for equality."""
        return hash1 == hash2


class CursorTracker:
    """Tracker for cursor-based incremental fetching."""
    
    def __init__(self, db_session):
        self.db = db_session
    
    def get_last_cursor(self) -> Optional[datetime]:
        """
        Get the last successful cursor timestamp.
        
        Returns the cursor_timestamp from the most recent completed extraction run.
        """
        from database import get_last_cursor
        return get_last_cursor(self.db)
    
    def advance_cursor(self, new_cursor: datetime) -> None:
        """
        Advance cursor to new timestamp.
        
        This is done by recording it in the extraction_run record.
        The actual update happens in complete_extraction_run().
        """
        logger.info(f"Cursor advanced to: {new_cursor.isoformat()}")
    
    def get_cursor_for_batch(self, documents: list[dict]) -> Optional[datetime]:
        """
        Get the cursor timestamp for a batch of documents.
        
        Returns the latest modification timestamp from the batch.
        """
        if not documents:
            return None
        
        # Find the latest modification timestamp
        latest = None
        for doc in documents:
            modified_str = doc.get("modified")
            if modified_str:
                try:
                    # Parse ISO format timestamp
                    modified = datetime.fromisoformat(modified_str.replace("Z", "+00:00"))
                    if latest is None or modified > latest:
                        latest = modified
                except ValueError:
                    logger.warning(f"Invalid timestamp format: {modified_str}")
        
        return latest


class ChangeDetector:
    """Detector for changes in requirements."""
    
    def __init__(self, db_session):
        self.db = db_session
        self.hasher = ContentHasher()
    
    def detect_change(
        self,
        requirement_data: dict,
        content_hash: str,
    ) -> tuple[str, Optional[int]]:
        """
        Detect if requirement is new or changed.
        
        Returns tuple of (change_type, existing_id):
        - ("new", None) if requirement doesn't exist
        - ("unchanged", id) if requirement exists with same hash
        - ("changed", id) if requirement exists with different hash
        """
        from database import get_requirement_by_hash, get_requirement_by_update_id
        
        update_id = requirement_data.get("update_id")
        
        # Check if requirement with same hash exists
        existing_by_hash = get_requirement_by_hash(self.db, content_hash)
        if existing_by_hash:
            logger.debug(f"Requirement {update_id} unchanged (hash match)")
            return ("unchanged", existing_by_hash.id)
        
        # Check if requirement with same update_id exists
        existing_by_id = get_requirement_by_update_id(self.db, update_id)
        if existing_by_id:
            logger.debug(f"Requirement {update_id} changed (hash mismatch)")
            return ("changed", existing_by_id.id)
        
        # New requirement
        logger.debug(f"Requirement {update_id} is new")
        return ("new", None)
    
    def should_skip(self, requirement_data: dict) -> bool:
        """
        Check if requirement should be skipped.
        
        Skip if:
        - It corrects another requirement (duplicate)
        - It's marked as a correction
        """
        corrects = requirement_data.get("corrects")
        if corrects:
            logger.info(f"Skipping {requirement_data.get('update_id')} (corrects {corrects})")
            return True
        
        change_type = requirement_data.get("change_type")
        if change_type == "correction":
            logger.info(f"Skipping {requirement_data.get('update_id')} (correction)")
            return True
        
        return False


def deduplicate_requirements(requirements: list[dict]) -> list[dict]:
    """
    Deduplicate a list of requirements.
    
    Removes:
    - Exact duplicates (same update_id)
    - Corrections (where corrects field points to another requirement)
    """
    seen_ids = set()
    corrected_ids = set()
    deduplicated = []
    
    # First pass: collect corrected IDs
    for req in requirements:
        corrects = req.get("corrects")
        if corrects:
            corrected_ids.add(corrects)
    
    # Second pass: filter
    for req in requirements:
        update_id = req.get("update_id")
        
        # Skip if already seen
        if update_id in seen_ids:
            logger.debug(f"Skipping duplicate: {update_id}")
            continue
        
        # Skip if this requirement is corrected by another
        if update_id in corrected_ids:
            logger.debug(f"Skipping corrected requirement: {update_id}")
            continue
        
        # Skip if this is a correction
        if req.get("corrects"):
            logger.debug(f"Skipping correction: {update_id}")
            continue
        
        seen_ids.add(update_id)
        deduplicated.append(req)
    
    logger.info(f"Deduplicated: {len(requirements)} -> {len(deduplicated)} requirements")
    return deduplicated
