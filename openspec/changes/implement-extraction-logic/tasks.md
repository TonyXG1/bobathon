## 1. Project Setup

- [ ] 1.1 Install dependencies in extraction_service (httpx, defusedxml, beautifulsoup4, sqlalchemy, pydantic-settings)
- [x] 1.2 Create config.py with pydantic-settings for environment variables
- [x] 1.3 Create database.py with SQLAlchemy models for requirements and extraction_runs tables
- [x] 1.4 Load and validate taxonomy.json at startup

## 2. CELLAR Client Implementation

- [x] 2.1 Create clients.py with CellarClient class
- [x] 2.2 Implement SPARQL query builder for watchlist documents
- [x] 2.3 Implement cursor-based pagination with LIMIT/OFFSET
- [x] 2.4 Implement consolidated version resolution (CELEX sector 0)
- [x] 2.5 Implement Formex XML fetching from CELLAR REST API
- [x] 2.6 Implement conditional GET with If-None-Match/If-Modified-Since headers
- [x] 2.7 Implement polite client behavior (User-Agent, rate limiting, timeouts)
- [x] 2.8 Add exponential backoff for 429/503 responses

## 3. ECHA Client Implementation

- [x] 3.1 Add EchaClient class to clients.py
- [x] 3.2 Implement SVHC Candidate List HTML fetching
- [x] 3.3 Implement BeautifulSoup table parsing for substance details
- [x] 3.4 Implement change detection (compare current vs cached list)
- [x] 3.5 Implement 24-hour caching with TTL check
- [x] 3.6 Implement polite client behavior for ECHA

## 4. Formex XML Parsing

- [x] 4.1 Create normalize.py with FormexParser class
- [x] 4.2 Implement safe XML parsing with defusedxml.ElementTree
- [x] 4.3 Implement XPath extraction for CELEX number
- [x] 4.4 Implement XPath extraction for publication date
- [x] 4.5 Implement XPath extraction for title (prefer English)
- [x] 4.6 Implement XPath extraction for legal references (articles/annexes)
- [x] 4.7 Implement body text extraction with paragraph structure
- [x] 4.8 Implement consolidation date extraction for consolidated acts

## 5. Scope Normalization

- [x] 5.1 Add ScopeNormalizer class to normalize.py
- [x] 5.2 Load taxonomy.json and build keyword mappings
- [x] 5.3 Implement category keyword matching (map to taxonomy.product_categories)
- [x] 5.4 Implement substance keyword matching (names, CAS numbers, formulas)
- [x] 5.5 Implement regulation family mapping (CELEX-based and title-based)
- [x] 5.6 Implement market extraction (EU-wide vs specific member states)
- [x] 5.7 Implement conditions/exclusions extraction
- [x] 5.8 Validate all mapped keys exist in taxonomy.json

## 6. Requirement Construction

- [x] 6.1 Add RequirementBuilder class to normalize.py
- [x] 6.2 Combine parsed metadata + normalized scope into Requirement object
- [x] 6.3 Set source_url (mandatory field)
- [x] 6.4 Set access_timestamp to current UTC time
- [x] 6.5 Validate Requirement against Pydantic model
- [x] 6.6 Handle validation errors gracefully

## 7. Content Hashing & Deduplication

- [x] 7.1 Create change.py with ContentHasher class
- [x] 7.2 Implement SHA-256 hash calculation from normalized fields
- [x] 7.3 Normalize whitespace before hashing
- [x] 7.4 Implement hash comparison against existing requirements
- [x] 7.5 Implement cursor tracking (store/retrieve last modification timestamp)
- [x] 7.6 Implement cursor advancement after successful batch

## 8. Database Persistence

- [x] 8.1 Implement insert_requirement in database.py
- [x] 8.2 Implement update_requirement in database.py
- [x] 8.3 Implement get_requirement_by_hash for deduplication check
- [x] 8.4 Implement list_requirements with filters (regulation_family, severity)
- [x] 8.5 Implement pagination (limit, offset)
- [x] 8.6 Implement extraction_run tracking (start, complete, fail)
- [x] 8.7 Add database connection pooling and error handling

## 9. FastAPI Application

- [x] 9.1 Create main.py with FastAPI app
- [x] 9.2 Implement GET /requirements endpoint with filters
- [x] 9.3 Implement GET /requirements/{update_id} endpoint
- [x] 9.4 Implement POST /extract endpoint (trigger extraction job)
- [x] 9.5 Implement GET /health endpoint with database connectivity check
- [x] 9.6 Configure CORS for dashboard access
- [x] 9.7 Add OpenAPI documentation at /docs
- [x] 9.8 Add request/response logging

## 10. Extraction Job Orchestration

- [x] 10.1 Create extraction job runner in main.py
- [x] 10.2 Implement CELLAR discovery → fetch → parse → normalize pipeline
- [x] 10.3 Implement ECHA fetch → parse → normalize pipeline
- [x] 10.4 Implement batch processing with error handling
- [x] 10.5 Implement extraction_run audit trail recording
- [x] 10.6 Add background task support for POST /extract

## 11. Testing

- [x] 11.1 Create tests/ directory structure
- [x] 11.2 Write unit tests for CellarClient (mock SPARQL/REST responses)
- [x] 11.3 Write unit tests for EchaClient (mock HTML responses)
- [x] 11.4 Write unit tests for FormexParser (use sample XML fixtures)
- [x] 11.5 Write unit tests for ScopeNormalizer (test taxonomy mapping)
- [x] 11.6 Write unit tests for ContentHasher (test hash consistency)
- [x] 11.7 Write integration tests for full extraction pipeline
- [x] 11.8 Write API endpoint tests (FastAPI TestClient)
- [x] 11.9 Test against contracts/fixtures/requirements.sample.json
- [x] 11.10 Verify all Requirements have source_url

## 12. Documentation & Deployment

- [x] 12.1 Update extraction_service/README.md with setup instructions
- [x] 12.2 Document environment variables in .env.example
- [x] 12.3 Add inline code comments for complex logic
- [ ] 12.4 Test with docker-compose up
- [ ] 12.5 Verify orchestrator can trigger extraction
- [ ] 12.6 Verify assessment_service can read requirements
- [ ] 12.7 Run full extraction against live CELLAR/ECHA (rate-limited)
- [ ] 12.8 Verify dashboard displays requirements correctly
