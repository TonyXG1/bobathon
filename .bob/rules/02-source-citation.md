# Source Citation Rule

**Every Finding MUST cite its source_url.**

## The Non-Negotiable Requirement

No source_url → no finding. This is **mandatory** per AGENTS.md.

## What is source_url?

The `source_url` field must contain:
- The **actual live portal URL** where the rule was read
- A real, accessible link to EUR-Lex, ECHA, or another official source
- **NOT** a reference to the example dataset files
- **NOT** a placeholder or dummy URL

## Why This Matters

1. **Correctness** - Proves the rule came from a live source, not the example dataset
2. **Auditability** - EcoComply (and the jury) can verify the rule exists
3. **Judging Criteria** - "Real-world fit" (10%) scores auditability heavily
4. **Legal Compliance** - Companies need to cite sources for regulatory compliance

## Where source_url Appears

### In Requirement (Part 1 output)
```python
class Requirement(BaseModel):
    source_url: str  # The live portal URL
    celex: str | None  # CELEX number (for EUR-Lex)
    consolidation_date: date | None  # Which version
    access_timestamp: datetime  # When we fetched it
```

### In Finding (Part 2 output)
```python
class Finding(BaseModel):
    source_url: str  # Copied from the Requirement
    # ... other fields
```

## Examples of Valid source_url

✅ **Good:**
- `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R1542`
- `https://eur-lex.europa.eu/eli/reg/2023/1542/oj`
- `https://echa.europa.eu/candidate-list-table/-/dislist/details/0b0236e1807e77a4`
- `https://chem.echa.europa.eu/obligation-lists/candidateList`

❌ **Bad:**
- `https://example.com` (not a real source)
- `file:///dataset/regulatory_updates.json` (local file, not live)
- `null` or empty string
- Missing the field entirely

## Implementation Guidelines

### Part 1 (Extraction Service)
```python
# When fetching from CELLAR
requirement = Requirement(
    source_url=f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}",
    celex=celex,
    access_timestamp=datetime.now(timezone.utc),
    # ... other fields
)

# When fetching from ECHA
requirement = Requirement(
    source_url="https://echa.europa.eu/candidate-list-table",
    access_timestamp=datetime.now(timezone.utc),
    # ... other fields
)
```

### Part 2 (Assessment Service)
```python
# When creating a Finding, copy source_url from Requirement
finding = Finding(
    source_url=requirement.source_url,  # MUST be present
    # ... other fields
)
```

### Part 3 (Alerting Service)
```python
# Include source_url in alert message
message = f"URGENT: {product} non-compliant. Source: {finding.source_url}"
```

## Validation

### At Creation
```python
# Pydantic will enforce this if defined correctly
class Finding(BaseModel):
    source_url: str = Field(..., min_length=1)  # Required, non-empty
```

### In Tests
```python
def test_finding_has_source_url():
    finding = create_finding(...)
    assert finding.source_url
    assert finding.source_url.startswith("http")
    assert "eur-lex.europa.eu" in finding.source_url or "echa.europa.eu" in finding.source_url
```

## Consequences of Violation

- Finding is **invalid** and should be rejected
- Fails judging criteria for "Quality of insight" (25%)
- Fails "Real-world fit" (10%) - not auditable
- EcoComply cannot verify the rule
- Legal team cannot cite the source

## Debugging Missing source_url

If you see a Finding without source_url:

1. **Check the Requirement** - Does it have source_url?
2. **Check the extraction logic** - Is it being set when fetching?
3. **Check the assessment logic** - Is it being copied to Finding?
4. **Check the Pydantic model** - Is source_url marked as required?

## Best Practices

✅ **DO:**
- Set source_url immediately when fetching from live source
- Validate source_url is a real URL (starts with http/https)
- Include source_url in every alert message
- Test that all Findings have valid source_url

❌ **DON'T:**
- Use placeholder URLs
- Reference local files or example dataset
- Leave source_url empty or null
- Forget to copy source_url from Requirement to Finding
