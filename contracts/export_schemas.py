"""
Export JSON schemas from Pydantic models.

This script generates requirement.schema.json and finding.schema.json from the
Pydantic models in contracts/models.py. CI validates that committed schemas
match the models (drift = build failure).

Usage:
    uv run python contracts/export_schemas.py
"""

import json
from pathlib import Path

from contracts.models import Finding, Requirement


def export_schemas():
    """Export JSON schemas from Pydantic models."""
    
    # Get the contracts directory
    contracts_dir = Path(__file__).parent
    
    # Export Requirement schema
    requirement_schema = Requirement.model_json_schema()
    requirement_schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    requirement_schema["$id"] = "https://regulatory-radar.example.com/schemas/requirement.schema.json"
    
    requirement_path = contracts_dir / "requirement.schema.json"
    with open(requirement_path, "w", encoding="utf-8") as f:
        json.dump(requirement_schema, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Exported requirement.schema.json ({requirement_path})")
    
    # Export Finding schema
    finding_schema = Finding.model_json_schema()
    finding_schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    finding_schema["$id"] = "https://regulatory-radar.example.com/schemas/finding.schema.json"
    
    finding_path = contracts_dir / "finding.schema.json"
    with open(finding_path, "w", encoding="utf-8") as f:
        json.dump(finding_schema, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Exported finding.schema.json ({finding_path})")
    
    print("\n✅ Schema export complete!")
    print("\nNext steps:")
    print("1. Review the generated schemas")
    print("2. Update fixtures in contracts/fixtures/ to match")
    print("3. Commit all changes together")


if __name__ == "__main__":
    export_schemas()
