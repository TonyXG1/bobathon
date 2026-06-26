# Assessment Service (Part 2)

Matches requirements against the portfolio to identify compliance gaps.

## Responsibilities

- Load portfolio (partners.json) and taxonomy (taxonomy.json)
- Index portfolio by category/substance/market for fast matching
- Apply applicability predicate: market ∧ category ∧ substance ∧ attribute ∧ ¬exclusion
- Detect gaps (obligation applies but not satisfied)
- Emit Finding objects conforming to finding.schema.json

## API Endpoints

- `POST /assess` - Run assessment against portfolio
- `GET /findings` - List all findings
- `GET /findings/{id}` - Get specific finding
- `GET /health` - Health check

## Key Files

- `main.py` - FastAPI app and endpoints
- `engine.py` - Scope matching and gap detection logic
- `portfolio.py` - Portfolio loading and indexing
- `config.py` - Settings
- `database.py` - SQLite/Postgres connection

## Technology Stack

- **FastAPI** - Web framework
- **Pydantic v2** - Data validation
- **httpx** - HTTP client (for calling extraction service)
- Pure Python logic for matching

## Running Locally

```bash
cd assessment_service
uv sync
uv run uvicorn main:app --reload --port 8082
```

Visit http://localhost:8082/docs for interactive API documentation.

## Running with Docker

```bash
docker build -t assessment-service .
docker run -p 8082:8082 --env-file ../.env -v $(pwd)/../dataset:/app/dataset:ro assessment-service
```

## Testing

```bash
uv run pytest
uv run pytest --cov=. --cov-report=html
```

## Environment Variables

Required:
- `DATABASE_URL` - Database connection string
- `EXTRACTION_SERVICE_URL` - URL of extraction service

Optional:
- `LOG_LEVEL` - Logging level (default: INFO)

## Core Logic: Applicability Predicate

An obligation applies to a product when **ALL** of these hold:

1. **Market** - Company sells where rule applies (`EU` = all 27 states)
2. **Category** - Rule covers product category (or scope is `"all"`)
3. **Substance** - If rule names substances, product actually contains one
4. **Attributes** - Battery type/capacity, has_radio, connector, packaging, intended_use satisfy conditions
5. **Exclusions** - Respect carve-outs (e.g., medical/industrial-only products)

A **gap** = obligation applies AND not yet satisfied.

## Watch for Look-Alikes (Common False Positives)

- ❌ Right category, **WRONG market** (e.g., UK-only SKU vs EU rule)
- ❌ Rule names substance product **does NOT contain**
- ❌ **Attribute takes product OUT of scope** (e.g., portable battery vs LMT battery rule)
- ❌ **Duplicate/correction entries** (corrects field points to another rule)

## Implementation Guidelines

1. **Keep matcher pure and deterministic**
   - No side effects
   - Same input → same output
   - Easy to unit test

2. **Index for performance**
   ```python
   portfolio_by_category = defaultdict(list)
   for partner in partners:
       for product in partner["products"]:
           portfolio_by_category[product["category"]].append(product)
   ```

3. **De-duplicate rules**
   - Skip rules where `corrects` points to another rule
   - They add no new obligation

4. **Every Finding MUST cite source_url**
   - Copy from the Requirement
   - This is non-negotiable

5. **Emit one Finding per (product × applicable-unmet-requirement)**

## Ground Truth Validation

Test against the 5 seeded gaps in partners.json:

- **P006 FitTrack** - PulseBand uses PFAS/PFHxA coating (REACH)
- **P008 PlayBright** - RoboPup DEHP limit + SingAlong button-cell security (GPSR)
- **P010 DisplayOne** - ProPanel mercury in CCFL (RoHS)
- **P013 RideVolt** - e-Scooter missing battery passport (Battery Reg)
- **P022 KidVision** - LittleView micro-USB + RED cybersecurity

Your engine should independently re-derive these from live sources.

## Troubleshooting

**No findings generated:**
- Check that requirements are in database
- Verify portfolio loaded correctly
- Check applicability logic (add debug logging)

**False positives:**
- Review look-alike checklist
- Check market matching (EU expansion)
- Verify substance presence in product
- Check attribute conditions

**Missing source_url:**
- Ensure copying from Requirement
- Validate Requirement has source_url