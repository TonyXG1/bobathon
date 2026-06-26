# Extraction Service

Part 1 of the Regulatory Radar system - extracts live regulatory requirements from EUR-Lex/CELLAR and ECHA.

## Overview

The extraction service:
1. **Discovers** new/changed legislation from CELLAR SPARQL endpoint
2. **Fetches** Formex XML documents from CELLAR REST API
3. **Parses** XML using defusedxml for security
4. **Normalizes** scope to taxonomy.json controlled vocabulary
5. **Deduplicates** using content hashing
6. **Persists** to database with full provenance (source_url, CELEX, timestamps)
7. **Exposes** REST API for downstream services

## Architecture

```
CELLAR SPARQL → CellarClient → FormexParser → ScopeNormalizer → RequirementBuilder → Database
ECHA HTML     → EchaClient   → BeautifulSoup → ScopeNormalizer → RequirementBuilder → Database
                                                                                      ↓
                                                                            FastAPI REST API
```

## Setup

### Prerequisites

- Python 3.12+
- uv (recommended) or pip

### Installation

```bash
# Install dependencies
cd extraction_service
uv sync

# Or with pip
pip install -e .
```

### Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Database
DATABASE_URL=sqlite:///./regulatory_radar.db

# CELLAR/EUR-Lex
CELLAR_SPARQL_ENDPOINT=http://publications.europa.eu/webapi/rdf/sparql
CELLAR_REST_BASE_URL=https://eur-lex.europa.eu/legal-content/EN/TXT/
CELLAR_TIMEOUT=60
CELLAR_PAGE_SIZE=100

# ECHA
ECHA_CANDIDATE_LIST_URL=https://echa.europa.eu/candidate-list-table
ECHA_CACHE_TTL_HOURS=24

# HTTP Client
USER_AGENT=RegulatoryRadar/1.0 (contact: team@example.com)
MAX_RETRIES=3

# Feature Flags
ENABLE_CELLAR_SPARQL=true
ENABLE_ECHA_FETCH=true

# API
API_HOST=0.0.0.0
API_PORT=8081
CORS_ORIGINS=["http://localhost:8501", "http://localhost:5173"]

# Logging
LOG_LEVEL=INFO
```

## Running

### Development

```bash
# Run with auto-reload
uv run uvicorn main:app --reload --port 8081

# Or
uv run python main.py
```

### Production

```bash
# Run with gunicorn
uv run gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8081
```

### Docker

```bash
# Build
docker build -t extraction-service .

# Run
docker run -p 8081:8081 --env-file .env extraction-service
```

### Docker Compose

```bash
# From repo root
docker-compose up extraction-service
```

## API Endpoints

### GET /

Root endpoint - service info.

### GET /health

Health check with database and taxonomy status.

**Response:**
```json
{
  "status": "healthy",
  "database": "healthy",
  "taxonomy": "loaded",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

### GET /requirements

List requirements with optional filters and pagination.

**Query Parameters:**
- `regulation_family` (optional): Filter by regulation family (e.g., "rohs", "reach")
- `severity` (optional): Filter by severity ("low", "medium", "high")
- `limit` (optional, default=100): Maximum results per page
- `offset` (optional, default=0): Pagination offset

**Response:**
```json
{
  "total": 42,
  "limit": 100,
  "offset": 0,
  "requirements": [
    {
      "update_id": "REG-32011L0065",
      "source_url": "https://eur-lex.europa.eu/...",
      "regulation_family": "rohs",
      "title": "RoHS Directive",
      "severity": "high",
      "deadline_date": "2024-12-31",
      ...
    }
  ]
}
```

### GET /requirements/{update_id}

Get a single requirement by update_id.

**Response:**
```json
{
  "update_id": "REG-32011L0065",
  "source_url": "https://eur-lex.europa.eu/...",
  ...
}
```

### POST /extract

Trigger an extraction job (runs in background).

**Request:**
```json
{
  "force_full_scan": false
}
```

**Response:**
```json
{
  "job_id": 123,
  "status": "running",
  "message": "Extraction job 123 started in background"
}
```

## Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=. --cov-report=html

# Run specific test file
uv run pytest tests/test_clients.py

# Run with verbose output
uv run pytest -v
```

## Development

### Code Style

```bash
# Format code
uv run ruff format .

# Lint
uv run ruff check .

# Fix auto-fixable issues
uv run ruff check --fix .
```

### Project Structure

```
extraction_service/
├── main.py              # FastAPI app and endpoints
├── clients.py           # CellarClient, EchaClient
├── normalize.py         # FormexParser, ScopeNormalizer, RequirementBuilder
├── change.py            # ContentHasher, CursorTracker, ChangeDetector
├── database.py          # SQLAlchemy models and CRUD operations
├── config.py            # Pydantic settings
├── taxonomy.py          # Taxonomy loader and validator
├── tests/               # Unit and integration tests
│   ├── test_clients.py
│   ├── test_normalize.py
│   ├── test_change.py
│   └── test_api.py
└── pyproject.toml       # Dependencies and metadata
```

## Key Concepts

### Cursor-Based Discovery

The service uses cursor-based incremental fetching:
1. Query CELLAR SPARQL for documents modified after last cursor
2. Process batch of documents
3. Update cursor to latest modification timestamp
4. Next run starts from new cursor

### Content Hashing

Requirements are deduplicated using SHA-256 content hashing:
- Hash includes: title, summary, scope, deadline, severity, action
- Excludes: timestamps, IDs
- Prevents churn on republished-identical rules

### Taxonomy Normalization

All scope fields are normalized to `taxonomy.json` keys:
- **Categories**: `led_lighting`, `battery_pack`, etc.
- **Substances**: `lead`, `cadmium`, `DEHP`, etc.
- **Regulation families**: `rohs`, `reach`, `battery`, etc.

### Security

- **XML parsing**: Uses `defusedxml` to prevent XXE attacks
- **Secrets**: Loaded from environment variables only
- **Rate limiting**: Exponential backoff for 429/503 responses
- **Polite client**: User-Agent, timeouts, conditional GET

## Troubleshooting

### Database connection errors

Check `DATABASE_URL` in `.env`. For SQLite, ensure directory exists.

### SPARQL timeout

Reduce `CELLAR_PAGE_SIZE` or increase `CELLAR_TIMEOUT`.

### Taxonomy not found

Ensure `TAXONOMY_PATH` points to `dataset/taxonomy.json` (relative to repo root).

### Rate limiting (429)

The service automatically backs off. If persistent, reduce request frequency.

### XML parsing errors

Check Formex XML structure. XPath queries may need adjustment for new formats.

## Integration

### With Assessment Service (Part 2)

Assessment service reads requirements via `GET /requirements`:

```python
import httpx

response = httpx.get("http://localhost:8081/requirements?regulation_family=rohs")
requirements = response.json()["requirements"]
```

### With Orchestrator

Orchestrator triggers extraction via `POST /extract`:

```python
import httpx

response = httpx.post("http://localhost:8081/extract", json={"force_full_scan": False})
job_id = response.json()["job_id"]
```

## Monitoring

### Extraction Runs

Query `extraction_runs` table for audit trail:

```sql
SELECT * FROM extraction_runs ORDER BY started_at DESC LIMIT 10;
```

### Requirements Stats

```sql
SELECT regulation_family, COUNT(*) 
FROM requirements 
GROUP BY regulation_family;
```

## License

MIT
