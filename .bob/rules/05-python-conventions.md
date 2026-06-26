# Python Conventions

**Code style and best practices for the Regulatory Radar project.**

## Code Style

### Type Hints
```python
# Always use type hints
def process_requirement(req: Requirement) -> Finding | None:
    """Process a requirement and return a finding if applicable."""
    pass

# Use modern union syntax (Python 3.10+)
from typing import Optional  # ❌ Old style
result: str | None  # ✅ New style
```

### Pydantic Models
```python
from pydantic import BaseModel, Field

class Requirement(BaseModel):
    """A regulatory requirement from a live source."""
    
    source_url: str = Field(..., description="Live portal URL")
    celex: str | None = Field(None, description="CELEX number")
    
    class Config:
        frozen = True  # Immutable after creation
```

### HTTP Requests
```python
import httpx

# Always set explicit timeouts
async with httpx.AsyncClient(timeout=30.0) as client:
    response = await client.get(url)

# Use context managers
with httpx.Client() as client:
    response = client.get(url, timeout=30.0)
```

## Security

### XML Parsing
```python
# ❌ NEVER use plain xml.etree (XXE vulnerability)
import xml.etree.ElementTree as ET
tree = ET.parse(file)  # UNSAFE

# ✅ ALWAYS use defusedxml
from defusedxml import ElementTree as ET
tree = ET.parse(file)  # SAFE

# ✅ Or configure lxml safely
from lxml import etree
parser = etree.XMLParser(
    resolve_entities=False,
    no_network=True,
    dtd_validation=False
)
tree = etree.parse(file, parser)
```

### Secrets
```python
# ❌ Never hardcode
TWILIO_SID = "ACxxxxxxxx"

# ✅ Load from environment
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    twilio_account_sid: str
    
    class Config:
        env_file = ".env"

settings = Settings()
```

## Testing

### Pytest Structure
```python
import pytest
from contracts.models import Requirement

def test_requirement_validation():
    """Test that Requirement validates required fields."""
    with pytest.raises(ValueError):
        Requirement()  # Missing required fields

def test_requirement_from_fixture():
    """Test requirement creation from fixture."""
    req = Requirement.model_validate_json(fixture_json)
    assert req.source_url.startswith("http")
```

### Fixtures
```python
@pytest.fixture
def sample_requirement():
    """Provide a sample requirement for testing."""
    return Requirement(
        source_url="https://eur-lex.europa.eu/...",
        # ... other fields
    )

def test_with_fixture(sample_requirement):
    """Test using the fixture."""
    assert sample_requirement.source_url
```

## Code Organization

### Keep Functions Small
```python
# ❌ Too large
def process_everything(data):
    # 200 lines of mixed logic
    pass

# ✅ Small, focused functions
def extract_celex(data: dict) -> str:
    """Extract CELEX number from raw data."""
    return data.get("celex", "")

def validate_celex(celex: str) -> bool:
    """Validate CELEX format."""
    return bool(re.match(r"^\d{5}[LR]\d{4}$", celex))
```

### Pure Functions
```python
# ✅ Pure function (no side effects)
def calculate_deadline(effective_date: date, months: int) -> date:
    """Calculate deadline from effective date."""
    return effective_date + timedelta(days=months * 30)

# ❌ Impure function (side effects)
def process_requirement(req: Requirement):
    """Process requirement and save to database."""
    # Mixing logic with I/O
    db.save(req)
```

## Formatting & Linting

### Ruff Configuration
```toml
# In pyproject.toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
ignore = ["E501"]  # Line too long (handled by formatter)
```

### Commands
```bash
# Format code
uv run ruff format .

# Check for issues
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check --fix .
```

## Async/Await

### When to Use Async
```python
# ✅ Use async for I/O-bound operations
async def fetch_requirements() -> list[Requirement]:
    """Fetch requirements from multiple sources concurrently."""
    async with httpx.AsyncClient() as client:
        tasks = [
            client.get(url1),
            client.get(url2),
            client.get(url3),
        ]
        responses = await asyncio.gather(*tasks)
    return [parse_response(r) for r in responses]

# ❌ Don't use async for CPU-bound operations
async def calculate_hash(data: bytes) -> str:
    """Calculate hash (CPU-bound, no benefit from async)."""
    return hashlib.sha256(data).hexdigest()
```

## Error Handling

### Specific Exceptions
```python
# ✅ Catch specific exceptions
try:
    requirement = Requirement.model_validate(data)
except ValidationError as e:
    logger.error(f"Invalid requirement: {e}")
    raise

# ❌ Don't catch all exceptions
try:
    requirement = Requirement.model_validate(data)
except Exception:  # Too broad
    pass
```

### Custom Exceptions
```python
class ExtractionError(Exception):
    """Raised when extraction fails."""
    pass

class NormalizationError(Exception):
    """Raised when normalization fails."""
    pass

# Use in code
if not celex:
    raise NormalizationError("Missing CELEX number")
```

## Logging

### Structured Logging
```python
import logging

logger = logging.getLogger(__name__)

# ✅ Structured with context
logger.info(
    "Extracted requirement",
    extra={
        "celex": req.celex,
        "regulation_family": req.regulation_family,
        "source": req.source,
    }
)

# ❌ Unstructured
logger.info(f"Got {req.celex} from {req.source}")
```

### Log Levels
```python
logger.debug("Detailed diagnostic info")
logger.info("Normal operation")
logger.warning("Something unexpected but handled")
logger.error("Error that needs attention")
logger.critical("System failure")
```

## Database

### Use Context Managers
```python
# ✅ With context manager
with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute(query)
    conn.commit()

# ❌ Manual management
conn = get_db_connection()
cursor = conn.cursor()
cursor.execute(query)
conn.commit()
conn.close()  # Easy to forget
```

## Documentation

### Docstrings
```python
def match_requirement(
    requirement: Requirement,
    product: dict
) -> bool:
    """
    Check if a requirement applies to a product.
    
    Args:
        requirement: The regulatory requirement to check
        product: Product dict from partners.json
        
    Returns:
        True if requirement applies, False otherwise
        
    Raises:
        ValueError: If product is missing required fields
    """
    pass
```

## Performance

### Use Appropriate Data Structures
```python
# ✅ Use set for membership testing
categories = {"led_lighting", "battery_pack", "toy_electronic"}
if product["category"] in categories:  # O(1)
    pass

# ❌ Use list for membership testing
categories = ["led_lighting", "battery_pack", "toy_electronic"]
if product["category"] in categories:  # O(n)
    pass
```

### Index for Fast Lookups
```python
# ✅ Index portfolio by category
portfolio_by_category = defaultdict(list)
for partner in partners:
    for product in partner["products"]:
        portfolio_by_category[product["category"]].append(product)

# Fast lookup
products = portfolio_by_category["led_lighting"]
```

## Checklist

Before committing:
- [ ] Code is type-hinted
- [ ] Pydantic models used for validation
- [ ] Secrets loaded from environment
- [ ] XML parsed with defusedxml
- [ ] HTTP requests have timeouts
- [ ] Functions are small and focused
- [ ] Tests pass (`uv run pytest`)
- [ ] Code formatted (`uv run ruff format`)
- [ ] No lint errors (`uv run ruff check`)
- [ ] Docstrings on public functions
- [ ] Logging uses appropriate levels
