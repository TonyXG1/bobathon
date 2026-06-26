"""Taxonomy loader and validator."""

import json
import logging
from pathlib import Path
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


class Taxonomy:
    """Taxonomy data loaded from taxonomy.json."""
    
    def __init__(self):
        self.product_categories: dict[str, str] = {}
        self.substances: dict[str, str] = {}
        self.regulation_families: dict[str, str] = {}
        self.markets_note: str = ""
        self._loaded = False
    
    def load(self, taxonomy_path: Optional[str] = None) -> None:
        """Load taxonomy from JSON file."""
        if taxonomy_path is None:
            taxonomy_path = settings.taxonomy_path
        
        path = Path(taxonomy_path)
        if not path.exists():
            raise FileNotFoundError(f"Taxonomy file not found: {taxonomy_path}")
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.product_categories = data.get("product_categories", {})
            self.substances = data.get("substances", {})
            self.regulation_families = data.get("regulation_families", {})
            self.markets_note = data.get("markets_note", "")
            
            self._loaded = True
            
            logger.info(
                f"Loaded taxonomy: {len(self.product_categories)} categories, "
                f"{len(self.substances)} substances, "
                f"{len(self.regulation_families)} regulation families"
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in taxonomy file: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load taxonomy: {e}")
    
    def validate(self) -> None:
        """Validate that taxonomy is loaded and has required data."""
        if not self._loaded:
            raise RuntimeError("Taxonomy not loaded. Call load() first.")
        
        if not self.product_categories:
            raise ValueError("Taxonomy missing product_categories")
        
        if not self.substances:
            raise ValueError("Taxonomy missing substances")
        
        if not self.regulation_families:
            raise ValueError("Taxonomy missing regulation_families")
        
        logger.info("Taxonomy validation passed")
    
    def is_valid_category(self, category: str) -> bool:
        """Check if category exists in taxonomy."""
        return category in self.product_categories
    
    def is_valid_substance(self, substance: str) -> bool:
        """Check if substance exists in taxonomy."""
        return substance in self.substances
    
    def is_valid_regulation_family(self, family: str) -> bool:
        """Check if regulation family exists in taxonomy."""
        return family in self.regulation_families
    
    def get_category_keywords(self) -> dict[str, list[str]]:
        """Get keyword mappings for categories."""
        # Build keyword mappings from category keys and descriptions
        keywords = {}
        for key, description in self.product_categories.items():
            # Use the key itself and words from description
            keyword_list = [key.replace("_", " ")]
            
            # Add common variations
            if key == "led_lighting":
                keyword_list.extend(["LED", "lighting", "lamp", "fixture"])
            elif key == "battery_pack":
                keyword_list.extend(["battery pack", "power bank", "portable battery"])
            elif key == "emobility_battery":
                keyword_list.extend(["e-bike", "e-scooter", "electric vehicle", "EV battery"])
            elif key == "toy_electronic":
                keyword_list.extend(["electronic toy", "toy", "educational kit"])
            elif key == "medical_wearable":
                keyword_list.extend(["medical device", "wearable medical"])
            elif key == "wearable":
                keyword_list.extend(["fitness tracker", "smartwatch", "wearable device"])
            elif key == "smartphone":
                keyword_list.extend(["mobile phone", "phone", "smartphone"])
            elif key == "networking":
                keyword_list.extend(["router", "switch", "access point", "network equipment"])
            elif key == "drone":
                keyword_list.extend(["UAV", "unmanned aerial vehicle", "drone"])
            elif key == "display":
                keyword_list.extend(["monitor", "screen", "display panel"])
            elif key == "audio":
                keyword_list.extend(["speaker", "headphone", "audio equipment"])
            elif key == "computing":
                keyword_list.extend(["computer", "tablet", "laptop", "PC"])
            elif key == "iot_sensor":
                keyword_list.extend(["IoT", "sensor", "smart home"])
            elif key == "camera":
                keyword_list.extend(["camera", "imaging device"])
            elif key == "gaming":
                keyword_list.extend(["gaming console", "game", "gaming accessory"])
            elif key == "industrial_equipment":
                keyword_list.extend(["industrial", "machinery", "equipment"])
            elif key == "charging_equipment":
                keyword_list.extend(["charger", "charging station"])
            
            keywords[key] = keyword_list
        
        return keywords
    
    def get_substance_keywords(self) -> dict[str, list[str]]:
        """Get keyword mappings for substances."""
        keywords = {}
        for key, description in self.substances.items():
            keyword_list = [key]
            
            # Add chemical names and formulas
            if key == "lead":
                keyword_list.extend(["Pb", "Lead", "7439-92-1"])
            elif key == "cadmium":
                keyword_list.extend(["Cd", "Cadmium", "7440-43-9"])
            elif key == "mercury":
                keyword_list.extend(["Hg", "Mercury", "7439-97-6"])
            elif key == "DEHP":
                keyword_list.extend(["Di(2-ethylhexyl) phthalate", "117-81-7"])
            elif key == "BPA":
                keyword_list.extend(["Bisphenol A", "80-05-7"])
            elif key == "decaBDE":
                keyword_list.extend(["Decabromodiphenyl ether", "1163-19-5"])
            elif key == "TBBPA":
                keyword_list.extend(["Tetrabromobisphenol A", "79-94-7"])
            elif key == "MCCP":
                keyword_list.extend(["Medium-chain chlorinated paraffins"])
            elif key == "PFAS_PFHxA":
                keyword_list.extend(["PFHxA", "Perfluorohexanoic acid", "PFAS"])
            elif key == "dioxane":
                keyword_list.extend(["1,4-Dioxane", "123-91-1"])
            elif key == "chromium_vi":
                keyword_list.extend(["Hexavalent chromium", "Cr(VI)", "Chromium VI"])
            elif key == "PBB":
                keyword_list.extend(["Polybrominated biphenyls"])
            elif key == "PBDE":
                keyword_list.extend(["Polybrominated diphenyl ethers"])
            
            keywords[key] = keyword_list
        
        return keywords
    
    def get_regulation_family_keywords(self) -> dict[str, list[str]]:
        """Get keyword mappings for regulation families."""
        keywords = {}
        for key, description in self.regulation_families.items():
            keyword_list = [key]
            
            # Add regulation names and common abbreviations
            if key == "rohs":
                keyword_list.extend(["RoHS", "2011/65/EU", "Restriction of Hazardous Substances"])
            elif key == "reach":
                keyword_list.extend(["REACH", "1907/2006", "Registration, Evaluation, Authorisation"])
            elif key == "weee":
                keyword_list.extend(["WEEE", "2012/19/EU", "Waste Electrical"])
            elif key == "battery":
                keyword_list.extend(["Battery", "2023/1542", "Batteries and Waste Batteries"])
            elif key == "ppwr":
                keyword_list.extend(["PPWR", "2025/40", "Packaging and Packaging Waste"])
            elif key == "gpsr":
                keyword_list.extend(["GPSR", "2023/988", "General Product Safety"])
            elif key == "red":
                keyword_list.extend(["RED", "2014/53/EU", "Radio Equipment"])
            elif key == "espr":
                keyword_list.extend(["ESPR", "2024/1781", "Ecodesign"])
            elif key == "toy_safety":
                keyword_list.extend(["Toy Safety", "2009/48/EC", "Safety of Toys"])
            elif key == "mdr":
                keyword_list.extend(["MDR", "2017/745", "Medical Devices"])
            elif key == "pops":
                keyword_list.extend(["POPs", "2019/1021", "Persistent Organic Pollutants"])
            
            keywords[key] = keyword_list
        
        return keywords


# Global taxonomy instance
_taxonomy: Optional[Taxonomy] = None


def get_taxonomy() -> Taxonomy:
    """Get the global taxonomy instance."""
    global _taxonomy
    if _taxonomy is None:
        _taxonomy = Taxonomy()
        _taxonomy.load()
        _taxonomy.validate()
    return _taxonomy


def load_taxonomy() -> Taxonomy:
    """Load and validate taxonomy at startup."""
    return get_taxonomy()
