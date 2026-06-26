# Regulatory Radar - Setup Guide

## Prerequisites

- **Python 3.12+** - [Download](https://www.python.org/downloads/)
- **uv** - Fast Python package manager: `pip install uv`
- **Docker & Docker Compose** (optional) - For full stack deployment

## Quick Start

### 1. Clone and Install

```bash
git clone <repository-url>
cd regulatory-radar
uv sync
```

This installs all workspace dependencies and sets up the development environment.

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your credentials
# Required: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_TEST_NUMBER, TWILIO_TEST_EMAIL
```

**Generate SECRET_KEY:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Run Services Individually

Each service can be run independently for development:

**Extraction Service (Port 8081):**
```bash
cd extraction_service
uv sync
uv run uvicorn main:app --reload --port 8081
```

**Assessment Service (Port 8082):**
```bash
cd assessment_service
uv sync
uv run uvicorn main:app --reload --port 8082
```

**Alerting Service (Port 8083):**
```bash
cd alerting_service
uv sync
uv run uvicorn main:app --reload --port 8083
```

**Orchestrator (Optional):**
```bash
cd orchestrator
uv sync
uv run python run.py
```

### 4. Run with Docker Compose

For a complete deployment with PostgreSQL:

```bash
docker-compose up
```

Services will be available at:
- **Extraction Service:** http://localhost:8081/docs
- **Assessment Service:** http://localhost:8082/docs
- **Alerting Service:** http://localhost:8083/docs
- **PostgreSQL:** localhost:5432

**Note:** The dashboard is a separate microservice (React + Vite + TypeScript) and runs independently.

## Database Setup

### SQLite (Default for Development)

No setup required. Database file will be created automatically at `./regulatory_radar.db`.

### PostgreSQL (Production/Docker)

When using docker-compose, PostgreSQL is automatically initialized with the schema from `database/init.sql`.

For manual setup:
```bash
psql -U radar_user -d regulatory_radar -f database/init.sql
```

## Testing

### Run All Tests

```bash
uv run pytest
```

### Run Service-Specific Tests

```bash
cd extraction_service
uv run pytest
```

### Run with Coverage

```bash
uv run pytest --cov=. --cov-report=html
open htmlcov/index.html
```

## Code Quality

### Lint and Format

```bash
# Check for issues
uv run ruff check .

# Auto-fix issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

### Type Checking (Optional)

```bash
pip install mypy
mypy extraction_service/ assessment_service/ alerting_service/
```

## Contract Validation

The Pydantic models in `contracts/models.py` are the single source of truth. JSON schemas are generated from them.

### Regenerate Schemas

```bash
cd contracts
uv run python export_schemas.py
```

**Important:** CI validates that committed schemas match the models. A drift = build failure.

### Update Contracts

When modifying a contract:
1. Update the Pydantic model in `contracts/models.py`
2. Run `export_schemas.py` to regenerate JSON schemas
3. Update fixtures in `contracts/fixtures/` to match
4. Update all consumers (services) in the same commit

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

Edit code in your service directory. Use Bob's custom modes for focused development:
- `extraction` mode for Part 1
- `assessment` mode for Part 2
- `alerting` mode for Part 3

### 3. Test Your Changes

```bash
cd your_service
uv run pytest
uv run ruff check .
```

### 4. Commit and Push

```bash
git add .
git commit -m "feat: your feature description"
git push origin feature/your-feature-name
```

## Troubleshooting

### Services Can't Connect to Database

**Issue:** `sqlalchemy.exc.OperationalError: unable to open database file`

**Solution:** Check `DATABASE_URL` in `.env`. For SQLite, ensure the directory is writable.

### Twilio Alerts Failing

**Issue:** `TwilioRestException: Unable to create record`

**Solution:**
1. Verify `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN` in `.env`
2. Check Twilio account balance
3. Verify phone number format: `+1234567890`

### CELLAR SPARQL Timeout

**Issue:** `httpx.ReadTimeout: timed out`

**Solution:**
1. Reduce query size (add `LIMIT`)
2. Use pagination (`OFFSET`)
3. Keep < 5 concurrent connections
4. Increase `HTTP_TIMEOUT` in `.env`

### Import Errors Between Services

**Issue:** `ModuleNotFoundError: No module named 'contracts'`

**Solution:**
1. Run `uv sync` in the service directory
2. Ensure you're in the correct virtual environment
3. Check that `contracts` is in the workspace members

### Docker Build Fails

**Issue:** `ERROR [internal] load metadata for docker.io/library/python:3.12-slim`

**Solution:**
1. Check Docker daemon is running
2. Verify internet connection
3. Try `docker-compose build --no-cache`

### Port Already in Use

**Issue:** `OSError: [Errno 48] Address already in use`

**Solution:**
```bash
# Find process using the port
lsof -i :8081

# Kill the process
kill -9 <PID>
```

## Environment Variables Reference

See `.env.example` for a complete list of environment variables.

### Required Variables

- `TWILIO_ACCOUNT_SID` - From Twilio Console
- `TWILIO_AUTH_TOKEN` - From Twilio Console
- `TWILIO_TEST_NUMBER` - YOUR test phone number
- `TWILIO_TEST_EMAIL` - YOUR test email

### Optional Variables

- `DATABASE_URL` - Database connection (default: SQLite)
- `LOG_LEVEL` - Logging level (default: INFO)
- `HTTP_TIMEOUT` - Request timeout in seconds (default: 30)
- `CELLAR_MAX_CONCURRENT` - Max SPARQL connections (default: 5)
- `ECHA_CACHE_TTL` - ECHA cache TTL in seconds (default: 86400)

## Security Checklist

Before deploying:

- [ ] `.env` is gitignored (never commit secrets)
- [ ] `SECRET_KEY` is generated and unique
- [ ] Twilio credentials are valid and not expired
- [ ] Database credentials are strong
- [ ] All secrets loaded from environment (not hardcoded)
- [ ] Logs don't contain sensitive information
- [ ] CORS origins are restricted in production

## Getting Help

- **Documentation:** See `README.md`, `SOURCES.md`, `DATASET_README.md`, `AGENTS.md`
- **Service Docs:** Each service has a `README.md` with specific guidance
- **Bob Rules:** Check `.bob/rules/` for team conventions
- **Issues:** Open an issue on GitHub

## Next Steps

1. **Read AGENTS.md** - Understand the problem and architecture
2. **Read SOURCES.md** - Learn about live data sources
3. **Explore dataset/** - Understand the portfolio and taxonomy
4. **Pick a service** - Start with extraction, assessment, or alerting
5. **Use Bob's custom modes** - Switch to your service's mode for focused development