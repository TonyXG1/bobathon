# Taxonomy Consistency Rule

**Use taxonomy.json enums exclusively.**

## Why This Matters

The assessment engine relies on **exact string matching** between:
- Requirements (extracted from live sources)
- Portfolio products (from partners.json)
- Taxonomy definitions (from taxonomy.json)

Any mismatch breaks the matching logic and creates false negatives (missed gaps).

## The Authoritative Source

`dataset/taxonomy.json` defines three critical enums:

1. **`product_categories`** - 17 categories (e.g., `led_lighting`, `battery_pack`, `toy_electronic`)
2. **`substances`** - 13 substances (e.g., `lead`, `cadmium`, `DEHP`, `PFAS_PFHxA`)
3. **`regulation_families`** - 20 families (e.g., `rohs`, `reach`, `battery`, `gpsr`)

## Normalization Requirements

### Part 1 (Extraction Service)

When normalizing raw data from EUR-Lex/CELLAR/ECHA into `Requirement` objects:

```python
# WRONG - using arbitrary strings
requirement = Requirement(
    regulation_family="Battery Regulation",  # ❌ Not in taxonomy
    scope={
        "categories": ["e-bike batteries"],  # ❌ Not in taxonomy
        "substances": ["lithium"]  # ❌ Not in taxonomy
    }
)

# RIGHT - using taxonomy keys
requirement = Requirement(
    regulation_family="battery",  # ✅ From taxonomy.regulation_families
    scope={
        "categories": ["emobility_battery"],  # ✅ From taxonomy.product_categories
        "substances": []  # ✅ Battery Reg doesn't restrict substances
    }
)
```

### Part 2 (Assessment Service)

The matcher must use the **same keys** when indexing and comparing:

```python
# Load taxonomy at startup
with open("dataset/taxonomy.json") as f:
    taxonomy = json.load(f)

# Index portfolio by category
portfolio_by_category = defaultdict(list)
for partner in partners:
    for product in partner["products"]:
        category = product["category"]  # Already uses taxonomy keys
        portfolio_by_category[category].append(product)

# Match requirement against portfolio
for category in requirement.scope["categories"]:
    if category in portfolio_by_category:
        # Match found - these products are in scope
        products = portfolio_by_category[category]
```

## Mapping Guidelines

### Categories

Map extracted text to taxonomy keys:

| Extracted Text | Taxonomy Key |
|---|---|
| "LED lighting", "LED lamps" | `led_lighting` |
| "Battery packs", "Power banks" | `battery_pack` |
| "E-bike batteries", "E-scooter batteries" | `emobility_battery` |
| "Electronic toys" | `toy_electronic` |
| "Wearable medical devices" | `medical_wearable` |

### Substances

Map chemical names/CAS numbers to taxonomy keys:

| Extracted Text | Taxonomy Key |
|---|---|
| "Lead (Pb)", "CAS 7439-92-1" | `lead` |
| "Cadmium (Cd)", "CAS 7440-43-9" | `cadmium` |
| "Mercury (Hg)", "CAS 7439-97-6" | `mercury` |
| "DEHP", "Di(2-ethylhexyl) phthalate" | `DEHP` |
| "PFAS", "PFHxA", "Perfluorohexanoic acid" | `PFAS_PFHxA` |

### Regulation Families

Map legal instruments to taxonomy keys:

| Extracted Text | Taxonomy Key |
|---|---|
| "Directive 2011/65/EU", "RoHS" | `rohs` |
| "Regulation (EC) 1907/2006", "REACH" | `reach` |
| "Regulation (EU) 2023/1542" | `battery` |
| "Regulation (EU) 2023/988", "GPSR" | `gpsr` |
| "Directive 2014/53/EU", "RED" | `red` |

## Adding New Entries

If you encounter a category/substance/family that **doesn't exist** in taxonomy.json:

### ❌ DON'T:
- Use the new string directly in your code
- Create ad-hoc mappings in service code
- Assume it will match

### ✅ DO:
1. **Discuss with the team** - Is this a real gap in taxonomy?
2. **Update taxonomy.json** - Add the new entry with description
3. **Update all services** - Ensure they recognize the new key
4. **Update tests** - Add test cases for the new entry
5. **Document the change** - Note why it was added

### Example: Adding a New Category

```json
// In dataset/taxonomy.json
{
  "product_categories": {
    // ... existing categories ...
    "smart_home": {
      "description": "Smart home devices (hubs, sensors, controllers)",
      "examples": ["smart thermostats", "door sensors", "lighting controllers"]
    }
  }
}
```

## Validation

### At Runtime

```python
# Validate category against taxonomy
def validate_category(category: str) -> bool:
    return category in taxonomy["product_categories"]

# Validate substance against taxonomy
def validate_substance(substance: str) -> bool:
    return substance in taxonomy["substances"]

# Use in normalization
if not validate_category(extracted_category):
    logger.warning(f"Unknown category: {extracted_category}")
    # Map to closest match or skip
```

### In Tests

```python
def test_requirement_uses_taxonomy_keys():
    requirement = extract_requirement(raw_data)
    
    # Check regulation family
    assert requirement.regulation_family in taxonomy["regulation_families"]
    
    # Check categories
    for category in requirement.scope["categories"]:
        if category != "all":
            assert category in taxonomy["product_categories"]
    
    # Check substances
    for substance in requirement.scope["substances"]:
        assert substance in taxonomy["substances"]
```

## Consequences of Violation

- **False negatives** - Gaps not detected because strings don't match
- **False positives** - Wrong products flagged due to incorrect mapping
- **Debugging nightmare** - Hard to trace why matching fails
- **Fails judging criteria** - "Quality of insight" (25%) requires correct gaps

## Best Practices

1. **Load taxonomy once** at service startup
2. **Create lookup dictionaries** for fast validation
3. **Log unmapped values** for debugging
4. **Use Literal types** in Pydantic models for compile-time validation
5. **Test with real data** from partners.json and regulatory_updates.json

## Example: Pydantic Model with Taxonomy Enums

```python
from typing import Literal
from pydantic import BaseModel

# Load taxonomy and create Literal types
ProductCategory = Literal[
    "led_lighting", "battery_pack", "emobility_battery",
    "toy_electronic", "medical_wearable", # ... all 17 categories
]

Substance = Literal[
    "lead", "cadmium", "mercury", "DEHP", "BPA",
    "decaBDE", "TBBPA", "MCCP", "PFAS_PFHxA", # ... all 13 substances
]

RegulationFamily = Literal[
    "rohs", "reach", "weee", "battery", "ppwr",
    "gpsr", "red", "espr", "toy_safety", # ... all 20 families
]

class Requirement(BaseModel):
    regulation_family: RegulationFamily  # ✅ Validated at creation
    scope: dict  # Contains categories and substances
```

This ensures **compile-time validation** - invalid keys are caught immediately.
