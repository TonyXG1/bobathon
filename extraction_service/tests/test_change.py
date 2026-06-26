"""Tests for change module."""

import pytest
from datetime import datetime, timezone

from extraction_service.change import ContentHasher, CursorTracker, ChangeDetector, deduplicate_requirements


class TestContentHasher:
    """Tests for ContentHasher."""
    
    def test_calculate_hash_deterministic(self):
        """Test that hash calculation is deterministic."""
        hasher = ContentHasher()
        
        requirement = {
            "title": "Test Requirement",
            "summary": "Test summary",
            "regulation_family": "rohs",
            "scope": {"categories": ["led_lighting"], "substances": ["lead"]},
            "deadline_date": "2024-12-31",
            "severity": "high",
            "action_required": "Comply",
        }
        
        hash1 = hasher.calculate_hash(requirement)
        hash2 = hasher.calculate_hash(requirement)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length
    
    def test_calculate_hash_different_content(self):
        """Test that different content produces different hashes."""
        hasher = ContentHasher()
        
        req1 = {
            "title": "Requirement 1",
            "summary": "Summary 1",
            "regulation_family": "rohs",
            "scope": {},
            "severity": "high",
        }
        
        req2 = {
            "title": "Requirement 2",
            "summary": "Summary 2",
            "regulation_family": "reach",
            "scope": {},
            "severity": "medium",
        }
        
        hash1 = hasher.calculate_hash(req1)
        hash2 = hasher.calculate_hash(req2)
        
        assert hash1 != hash2
    
    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        hasher = ContentHasher()
        
        text1 = "Test   with   multiple   spaces"
        text2 = "Test with multiple spaces"
        
        norm1 = hasher._normalize_whitespace(text1)
        norm2 = hasher._normalize_whitespace(text2)
        
        assert norm1 == norm2
    
    def test_compare_hashes(self):
        """Test hash comparison."""
        hasher = ContentHasher()
        
        hash1 = "abc123"
        hash2 = "abc123"
        hash3 = "def456"
        
        assert hasher.compare_hashes(hash1, hash2)
        assert not hasher.compare_hashes(hash1, hash3)


class TestChangeDetector:
    """Tests for ChangeDetector."""
    
    def test_should_skip_corrects(self):
        """Test skipping requirements that correct others."""
        detector = ChangeDetector(None)
        
        requirement = {
            "update_id": "REG-001",
            "corrects": "REG-000",
        }
        
        assert detector.should_skip(requirement)
    
    def test_should_skip_correction(self):
        """Test skipping correction type."""
        detector = ChangeDetector(None)
        
        requirement = {
            "update_id": "REG-001",
            "change_type": "correction",
        }
        
        assert detector.should_skip(requirement)
    
    def test_should_not_skip_normal(self):
        """Test not skipping normal requirements."""
        detector = ChangeDetector(None)
        
        requirement = {
            "update_id": "REG-001",
            "change_type": "amendment",
        }
        
        assert not detector.should_skip(requirement)


def test_deduplicate_requirements():
    """Test requirement deduplication."""
    requirements = [
        {"update_id": "REG-001", "title": "First"},
        {"update_id": "REG-001", "title": "Duplicate"},  # Duplicate ID
        {"update_id": "REG-002", "title": "Second"},
        {"update_id": "REG-003", "title": "Third", "corrects": "REG-002"},  # Correction
        {"update_id": "REG-004", "title": "Fourth"},
    ]
    
    deduplicated = deduplicate_requirements(requirements)
    
    # Should keep: REG-001 (first occurrence), REG-004
    # Should skip: REG-001 (duplicate), REG-002 (corrected), REG-003 (correction)
    assert len(deduplicated) == 2
    assert deduplicated[0]["update_id"] == "REG-001"
    assert deduplicated[1]["update_id"] == "REG-004"
