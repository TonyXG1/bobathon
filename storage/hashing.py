"""Canonical content hash of a Requirement, for upsert-by-hash.

The hash covers the requirement's *content* — every contract field except
``access_timestamp`` — so re-fetching an unchanged rule hashes identically and
is a no-op, while any content difference versions the row.

Note: the hash is computed over the **normalized** requirement, so a change to
``extraction_service/normalize.py`` that alters normalized output will
re-version affected rows on the next fetch. That is intended — a normalization
change *is* a content change from the store's point of view.
"""

from __future__ import annotations

import hashlib
import json

from contracts.models import Requirement


def content_hash(requirement: Requirement) -> str:
    """sha256 hex digest of the requirement's canonical JSON (sans access_timestamp)."""
    payload = requirement.model_dump(mode="json", exclude={"access_timestamp"})
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
