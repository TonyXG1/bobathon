"""Normalization logic: Formex parsing, scope normalization, requirement building."""

import hashlib
import json
import logging
import re
from datetime import datetime, date, timezone
from typing import Optional

from defusedxml import ElementTree as ET
from pydantic import ValidationError

from taxonomy import get_taxonomy

logger = logging.getLogger(__name__)


class FormexParser:
    """Parser for Formex XML documents from CELLAR."""
    
    # XPath namespaces (Formex uses custom namespaces)
    NAMESPACES = {
        "fmx": "http://formex.publications.europa.eu/schema/formex-05.56-20160701.xd",
    }
    
    def __init__(self):
        self.taxonomy = get_taxonomy()
    
    def parse(self, xml_content: str, celex: str) -> dict:
        """
        Parse Formex XML and extract metadata + body text.
        
        Returns dict with: celex, title, publication_date, reference, body_text, consolidation_date
        """
        try:
            # Parse with defusedxml for security
            root = ET.fromstring(xml_content.encode("utf-8"))
            
            metadata = {
                "celex": celex,
                "title": self._extract_title(root),
                "publication_date": self._extract_publication_date(root),
                "reference": self._extract_reference(root),
                "body_text": self._extract_body_text(root),
                "consolidation_date": self._extract_consolidation_date(root, celex),
            }
            
            logger.debug(f"Parsed Formex for {celex}: {metadata['title'][:50]}...")
            return metadata
            
        except ET.ParseError as e:
            logger.error(f"XML parse error for {celex}: {e}")
            raise ValueError(f"Invalid XML: {e}")
        except Exception as e:
            logger.error(f"Formex parse error for {celex}: {e}")
            raise
    
    def _extract_title(self, root) -> str:
        """Extract document title (prefer English)."""
        # Try multiple XPath patterns
        patterns = [
            ".//TI.DOC[@LANG='EN']",
            ".//TI.DOC",
            ".//TITLE[@LANG='EN']",
            ".//TITLE",
        ]
        
        for pattern in patterns:
            elem = root.find(pattern)
            if elem is not None and elem.text:
                return elem.text.strip()
        
        # Fallback: search for any element with "title" in tag name
        for elem in root.iter():
            if "title" in elem.tag.lower() and elem.text:
                return elem.text.strip()
        
        logger.warning("No title found in Formex XML")
        return "Untitled Document"
    
    def _extract_publication_date(self, root) -> Optional[date]:
        """Extract publication date."""
        patterns = [
            ".//DATE.PUB",
            ".//PUB.DATE",
            ".//DATE",
        ]
        
        for pattern in patterns:
            elem = root.find(pattern)
            if elem is not None and elem.text:
                try:
                    # Parse date (format: YYYY-MM-DD or YYYYMMDD)
                    date_str = elem.text.strip()
                    if "-" in date_str:
                        return datetime.strptime(date_str, "%Y-%m-%d").date()
                    else:
                        return datetime.strptime(date_str, "%Y%m%d").date()
                except ValueError:
                    logger.warning(f"Invalid date format: {elem.text}")
        
        return None
    
    def _extract_reference(self, root) -> Optional[str]:
        """Extract legal reference (article/annex)."""
        references = []
        
        # Look for article references
        for elem in root.iter():
            if "article" in elem.tag.lower() or "art" in elem.tag.lower():
                if elem.text:
                    references.append(f"Article {elem.text.strip()}")
        
        # Look for annex references
        for elem in root.iter():
            if "annex" in elem.tag.lower():
                if elem.text:
                    references.append(f"Annex {elem.text.strip()}")
        
        if references:
            return ", ".join(references[:3])  # Limit to first 3
        
        return None
    
    def _extract_body_text(self, root) -> str:
        """Extract body text with paragraph structure."""
        # Collect text from all paragraph-like elements
        text_parts = []
        
        for elem in root.iter():
            # Skip metadata elements
            if any(skip in elem.tag.lower() for skip in ["meta", "header", "title"]):
                continue
            
            # Collect text from paragraph-like elements
            if any(tag in elem.tag.lower() for tag in ["p", "para", "text", "content"]):
                if elem.text and elem.text.strip():
                    text_parts.append(elem.text.strip())
        
        # If no paragraphs found, get all text
        if not text_parts:
            text_parts = [elem.text.strip() for elem in root.iter() if elem.text and elem.text.strip()]
        
        body_text = "\n\n".join(text_parts)
        logger.debug(f"Extracted {len(body_text)} chars of body text")
        return body_text
    
    def _extract_consolidation_date(self, root, celex: str) -> Optional[date]:
        """Extract consolidation date for consolidated acts."""
        # Consolidated acts have CELEX starting with "0" (sector 0)
        if not celex.startswith("0"):
            return None
        
        # Try to extract date from CELEX (format: 0YYYYLNNNN-YYYYMMDD)
        match = re.search(r"-(\d{8})$", celex)
        if match:
            try:
                date_str = match.group(1)
                return datetime.strptime(date_str, "%Y%m%d").date()
            except ValueError:
                pass
        
        # Try to find consolidation date in metadata
        patterns = [
            ".//CONSOL.DATE",
            ".//DATE.CONSOL",
        ]
        
        for pattern in patterns:
            elem = root.find(pattern)
            if elem is not None and elem.text:
                try:
                    date_str = elem.text.strip()
                    if "-" in date_str:
                        return datetime.strptime(date_str, "%Y-%m-%d").date()
                    else:
                        return datetime.strptime(date_str, "%Y%m%d").date()
                except ValueError:
                    pass
        
        return None


class ScopeNormalizer:
    """Normalizer for scope fields using taxonomy keyword matching."""
    
    def __init__(self):
        self.taxonomy = get_taxonomy()
        self.category_keywords = self.taxonomy.get_category_keywords()
        self.substance_keywords = self.taxonomy.get_substance_keywords()
        self.regulation_keywords = self.taxonomy.get_regulation_family_keywords()
    
    def normalize(self, body_text: str, title: str, celex: str) -> dict:
        """
        Normalize scope from body text and metadata.
        
        Returns dict with: categories, substances, regulation_family, markets, conditions
        """
        text_lower = (body_text + " " + title).lower()
        
        scope = {
            "categories": self._match_categories(text_lower),
            "substances": self._match_substances(text_lower),
            "markets": self._extract_markets(text_lower),
            "conditions": self._extract_conditions(body_text),
        }
        
        logger.debug(
            f"Normalized scope: {len(scope['categories'])} categories, "
            f"{len(scope['substances'])} substances"
        )
        
        return scope
    
    def _match_categories(self, text: str) -> list[str]:
        """Match product categories using keyword matching."""
        matched = []
        
        for category_key, keywords in self.category_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text:
                    if category_key not in matched:
                        matched.append(category_key)
                    break
        
        # Check for "all" scope indicators
        if any(phrase in text for phrase in ["all electronic", "all electrical", "all equipment"]):
            return ["all"]
        
        if not matched:
            logger.warning("No categories matched")
        
        return matched
    
    def _match_substances(self, text: str) -> list[str]:
        """Match substances using keyword matching."""
        matched = []
        
        for substance_key, keywords in self.substance_keywords.items():
            for keyword in keywords:
                if keyword.lower() in text:
                    if substance_key not in matched:
                        matched.append(substance_key)
                    break
        
        return matched
    
    def map_regulation_family(self, celex: str, title: str) -> str:
        """Map document to regulation family."""
        # Try CELEX-based mapping first
        for family_key, keywords in self.regulation_keywords.items():
            for keyword in keywords:
                if keyword in celex or keyword.lower() in title.lower():
                    if self.taxonomy.is_valid_regulation_family(family_key):
                        return family_key
        
        # Default to "other"
        logger.warning(f"No regulation family match for {celex}, defaulting to 'other'")
        return "other"
    
    def _extract_markets(self, text: str) -> list[str]:
        """Extract applicable markets."""
        # Check for EU-wide applicability
        if any(phrase in text for phrase in ["european union", "member states", "eu-wide"]):
            return ["EU"]
        
        # Check for specific member states (simplified)
        markets = []
        eu_countries = ["DE", "FR", "IT", "ES", "NL", "BE", "AT", "PL", "SE", "DK"]
        for country in eu_countries:
            if country.lower() in text or self._country_name(country).lower() in text:
                markets.append(country)
        
        # Default to EU if no specific markets found
        return markets if markets else ["EU"]
    
    def _country_name(self, code: str) -> str:
        """Get country name from ISO code."""
        names = {
            "DE": "Germany", "FR": "France", "IT": "Italy", "ES": "Spain",
            "NL": "Netherlands", "BE": "Belgium", "AT": "Austria", "PL": "Poland",
            "SE": "Sweden", "DK": "Denmark",
        }
        return names.get(code, code)
    
    def _extract_conditions(self, text: str) -> str:
        """Extract scope conditions and exclusions."""
        conditions = []
        
        # Look for exclusion phrases
        exclusion_patterns = [
            r"except\s+([^.]+)",
            r"excluding\s+([^.]+)",
            r"does not apply to\s+([^.]+)",
            r"with the exception of\s+([^.]+)",
        ]
        
        for pattern in exclusion_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            conditions.extend(matches[:2])  # Limit to 2 per pattern
        
        return "; ".join(conditions) if conditions else ""


class RequirementBuilder:
    """Builder for Requirement Pydantic objects."""
    
    def __init__(self):
        self.taxonomy = get_taxonomy()
        self.normalizer = ScopeNormalizer()
    
    def build(
        self,
        parsed_metadata: dict,
        source_url: str,
        access_timestamp: datetime,
    ) -> dict:
        """
        Build Requirement dict from parsed metadata.
        
        Returns dict ready for Pydantic validation.
        """
        celex = parsed_metadata["celex"]
        title = parsed_metadata["title"]
        body_text = parsed_metadata["body_text"]
        
        # Normalize scope
        scope = self.normalizer.normalize(body_text, title, celex)
        
        # Map regulation family
        regulation_family = self.normalizer.map_regulation_family(celex, title)
        
        # Generate update_id (use CELEX as base)
        update_id = f"REG-{celex}"
        
        # Build requirement dict
        requirement = {
            "update_id": update_id,
            "published_date": parsed_metadata["publication_date"] or date.today(),
            "source": "EUR-Lex",
            "source_url": source_url,
            "celex": celex,
            "consolidation_date": parsed_metadata["consolidation_date"],
            "access_timestamp": access_timestamp,
            "regulation_family": regulation_family,
            "reference": parsed_metadata["reference"],
            "title": title,
            "summary": self._generate_summary(body_text),
            "change_type": "amendment",  # Default, could be inferred
            "effective_date": parsed_metadata["publication_date"],
            "deadline_date": self._infer_deadline(body_text, parsed_metadata["publication_date"]),
            "severity": self._infer_severity(body_text),
            "action_required": self._extract_action(body_text),
            "scope": scope,
            "corrects": None,
        }
        
        logger.debug(f"Built requirement: {update_id}")
        return requirement
    
    def _generate_summary(self, body_text: str) -> str:
        """Generate summary from body text."""
        # Take first 200 chars as summary
        summary = body_text[:200].strip()
        if len(body_text) > 200:
            summary += "..."
        return summary
    
    def _infer_deadline(self, text: str, publication_date: Optional[date]) -> Optional[date]:
        """Infer deadline from text."""
        # Look for deadline patterns
        patterns = [
            r"by\s+(\d{1,2}\s+\w+\s+\d{4})",
            r"before\s+(\d{1,2}\s+\w+\s+\d{4})",
            r"deadline[:\s]+(\d{1,2}\s+\w+\s+\d{4})",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(1)
                    return datetime.strptime(date_str, "%d %B %Y").date()
                except ValueError:
                    pass
        
        # Default: 1 year from publication
        if publication_date:
            return date(publication_date.year + 1, publication_date.month, publication_date.day)
        
        return None
    
    def _infer_severity(self, text: str) -> str:
        """Infer severity from text."""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ["prohibited", "banned", "mandatory", "shall"]):
            return "high"
        elif any(word in text_lower for word in ["should", "recommended", "encouraged"]):
            return "medium"
        else:
            return "low"
    
    def _extract_action(self, text: str) -> str:
        """Extract required action from text."""
        # Look for action phrases
        patterns = [
            r"shall\s+([^.]+)",
            r"must\s+([^.]+)",
            r"required to\s+([^.]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                action = match.group(1).strip()
                return action[:200]  # Limit length
        
        return "Comply with the requirements specified in the regulation"
