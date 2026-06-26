# Extraction Service (Part 1)

Pulls current EU regulatory requirements from live sources and normalizes them to the Requirement schema.

## Responsibilities

- Fetch from EUR-Lex/CELLAR (SPARQL, REST, RSS)
- Fetch from ECHA (SVHC Candidate List)
- Normalize to Requirement Pydantic model
- Change detection (conditional GET, content hashing)
- Provenance tracking (source_url, CELEX, timestamp)

## API Endpoints

- `GET /requirements` - List all requirements
- `GET /requirements/{update_id}` - Get specific requirement
- `POST /extract` - Trigger extraction job
- `GET /health` - Health check

## Key Files

- `main.py` - FastAPI app and endpoints
- `clients.py` - HTTP clients for CELLAR and ECHA
- `normalize.py` - Raw data → Requirement transformation
- `change.py` - Change detection logic
- `config.py` - Settings (BaseSettings from pydantic-settings)
- `database.py` - SQLite/Postgres connection

## Technology Stack

- **FastAPI** - Web framework
- **Pydantic v2** - Data validation
- **httpx** - HTTP client
- **defusedxml** - Safe XML parsing
- **BeautifulSoup + lxml** - HTML parsing
- **SPARQLWrapper** - SPARQL queries

## Running Locally

```bash
cd extraction_service
uv sync
uv run uvicorn main:app --reload --port 8081
```

Visit http://localhost:8081/docs for interactive API documentation.

## Running with Docker

```bash
docker build -t extraction-service .
docker run -p 8081:8081 --env-file ../.env extraction-service
```

## Testing

```bash
uv run pytest
uv run pytest --cov=. --cov-report=html
```

## Environment Variables

Required:
- `DATABASE_URL` - Database connection string
- `CELLAR_SPARQL_ENDPOINT` - CELLAR SPARQL endpoint URL
- `CELLAR_REST_BASE_URL` - CELLAR REST API base URL
- `ECHA_API_BASE_URL` - ECHA API base URL
- `ECHA_CANDIDATE_LIST_URL` - ECHA Candidate List URL

Optional:
- `CELLAR_MAX_CONCURRENT` - Max concurrent SPARQL connections (default: 5)
- `ECHA_CACHE_TTL` - ECHA cache TTL in seconds (default: 86400)
- `HTTP_TIMEOUT` - HTTP request timeout in seconds (default: 30)
- `LOG_LEVEL` - Logging level (default: INFO)

## Security Notes

- Always use `defusedxml` for XML parsing (never plain `xml.etree`)
- Set explicit timeouts on all HTTP requests
- Validate and sanitize all scraped content
- Never log secrets or credentials
- Use conditional GET to be a polite client

## Development Guidelines

1. **Provenance is mandatory** - Every Requirement must have:
   - `source_url` (the live portal URL)
   - `access_timestamp` (when we fetched it)
   - `celex` (for EUR-Lex documents)
   - `consolidation_date` (which version)

2. **Be a polite client**:
   - Send clear User-Agent with contact
   - Honor rate limits (< 5 concurrent SPARQL connections)
   - Use conditional GET (If-None-Match, If-Modified-Since)
   - Cache ECHA results for ~24 hours

3. **Change detection**:
   - Use content hashing to detect actual changes
   - Track cursors for incremental fetching
   - De-duplicate corrections (respect `corrects` field)

4. **Normalize to taxonomy**:
   - Map categories to `taxonomy.product_categories` keys
   - Map substances to `taxonomy.substances` keys
   - Map regulation families to `taxonomy.regulation_families` keys

## Troubleshooting

**SPARQL timeout:**
- Reduce query size
- Add LIMIT/OFFSET for pagination
- Keep < 5 concurrent connections

**XML parsing errors:**
- Verify you're using `defusedxml`, not plain `xml.etree`
- Check XML is well-formed

**ECHA rate limiting:**
- Increase cache TTL
- Add delays between requests
- Check User-Agent is set