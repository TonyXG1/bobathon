"""Tests for normalize module."""

import pytest
from datetime import date, datetime, timezone

from extraction_service.normalize import FormexParser, ScopeNormalizer, RequirementBuilder


class TestFormexParser:
    """Tests for FormexParser."""
    
    def test_parse_simple_xml(self):
        """Test parsing simple Formex XML."""
        xml = """<?xml version="1.0"?>
        <document>
            <TI.DOC LANG="EN">Test Directive</TI.DOC>
            <DATE.PUB>2024-01-01</DATE.PUB>
            <p>This is the body text.</p>
        </document>
        """
        
        parser = FormexParser()
        result = parser.parse(xml, "32024L0001")
        
        assert result["celex"] == "32024L0001"
        assert result["title"] == "Test Directive"
        assert result["publication_date"] == date(2024, 1, 1)
        assert "body text" in result["body_text"]
    
    def test_extract_title_fallback(self):
        """Test title extraction with fallback."""
        xml = """<?xml version="1.0"?>
        <document>
            <TITLE>Fallback Title</TITLE>
        </document>
        """
        
        parser = FormexParser()
        result = parser.parse(xml, "32024L0001")
        
        assert result["title"] == "Fallback Title"
    
    def test_extract_consolidation_date(self):
        """Test consolidation date extraction."""
        xml = """<?xml version="1.0"?>
        <document>
            <TI.DOC>Consolidated Act</TI.DOC>
        </document>
        """
        
        parser = FormexParser()
        # Consolidated CELEX with date suffix
        result = parser.parse(xml, "02011L0065-20240101")
        
        assert result["consolidation_date"] == date(2024, 1, 1)


class TestScopeNormalizer:
    """Tests for ScopeNormalizer."""
    
    def test_match_categories(self):
        """Test category keyword matching."""
        normalizer = ScopeNormalizer()
        
        text = "This regulation applies to LED lighting products and battery packs."
        scope = normalizer.normalize(text, "LED Regulation", "32024L0001")
        
        assert "led_lighting" in scope["categories"]
        assert "battery_pack" in scope["categories"]
    
    def test_match_substances(self):
        """Test substance keyword matching."""
        normalizer = ScopeNormalizer()
        
        text = "Restriction of lead (Pb) and cadmium (Cd) in electronic equipment."
        scope = normalizer.normalize(text, "RoHS", "32011L0065")
        
        assert "lead" in scope["substances"]
        assert "cadmium" in scope["substances"]
    
    def test_map_regulation_family(self):
        """Test regulation family mapping."""
        normalizer = ScopeNormalizer()
        
        # CELEX-based mapping
        family = normalizer.map_regulation_family("32011L0065", "RoHS Directive")
        assert family == "rohs"
        
        # Title-based mapping
        family = normalizer.map_regulation_family("32024L0001", "Battery Regulation")
        assert family == "battery"
    
    def test_extract_markets_eu_wide(self):
        """Test EU-wide market extraction."""
        normalizer = ScopeNormalizer()
        
        text = "This regulation applies to all member states of the European Union."
        scope = normalizer.normalize(text, "Test", "32024L0001")
        
        assert scope["markets"] == ["EU"]
    
    def test_extract_conditions(self):
        """Test conditions extraction."""
        normalizer = ScopeNormalizer()
        
        text = "Applies to all products except medical devices and industrial equipment."
        scope = normalizer.normalize(text, "Test", "32024L0001")
        
        # Conditions should capture the exclusion text
        assert scope["conditions"]
        assert "medical" in scope["conditions"].lower() or "industrial" in scope["conditions"].lower()


class TestRequirementBuilder:
    """Tests for RequirementBuilder."""
    
    def test_build_requirement(self):
        """Test requirement building."""
        builder = RequirementBuilder()
        
        parsed_metadata = {
            "celex": "32011L0065",
            "title": "RoHS Directive",
            "publication_date": date(2011, 6, 8),
            "reference": "Article 4",
            "body_text": "Restriction of lead and cadmium in electronic equipment.",
            "consolidation_date": None,
        }
        
        source_url = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0065"
        access_timestamp = datetime.now(timezone.utc)
        
        requirement = builder.build(parsed_metadata, source_url, access_timestamp)
        
        assert requirement["update_id"] == "REG-32011L0065"
        assert requirement["source_url"] == source_url
        assert requirement["celex"] == "32011L0065"
        assert requirement["title"] == "RoHS Directive"
        assert requirement["regulation_family"] == "rohs"
        assert "lead" in requirement["scope"]["substances"]
    
    def test_infer_severity(self):
        """Test severity inference."""
        builder = RequirementBuilder()
        
        # High severity
        text = "Products shall be prohibited from containing lead."
        severity = builder._infer_severity(text)
        assert severity == "high"
        
        # Medium severity
        text = "Manufacturers should comply with the requirements."
        severity = builder._infer_severity(text)
        assert severity == "medium"
        
        # Low severity
        text = "This is a general guideline."
        severity = builder._infer_severity(text)
        assert severity == "low"
    
    def test_generate_summary(self):
        """Test summary generation."""
        builder = RequirementBuilder()
        
        long_text = "A" * 300
        summary = builder._generate_summary(long_text)
        
        assert len(summary) <= 203  # 200 chars + "..."
        assert summary.endswith("...")
