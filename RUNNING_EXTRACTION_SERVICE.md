# Running the Extraction Service

## Problem with Docker Compose
The full `docker-compose.yml` tries to build all 4 services, but only the extraction service is implemented. This causes the build to fail.

## ✅ Solution: Run Locally (Recommended)

### Option 1: Quick Start with PowerShell Script

```powershell
# Run the service
.\run_extraction_service.ps1
```

This will:
- Create `.env` from `.env.example` if needed
- Install dependencies
- Start the service on http://localhost:8081
- Use SQLite database (no Postgres needed)

### Option 2: Manual Start

```powershell
# 1. Install dependencies
uv pip install -e extraction_service/

# 2. Set environment variables
$env:DATABASE_URL = "sqlite:///./regulatory_radar.db"
$env:CELLAR_SPARQL_ENDPOINT = "http://publications.europa.eu/webapi/rdf/sparql"
$env:CELLAR_REST_BASE_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/"
$env:ECHA_API_BASE_URL = "https://echa.europa.eu"
$env:ECHA_CANDIDATE_LIST_URL = "https://echa.europa.eu/candidate-list-table"

# 3. Start the service
cd extraction_service
uv run uvicorn extraction_service.main:app --reload --port 8081
```

## 🧪 Testing the Service

### Option 1: Use Test Script

```powershell
# In a new terminal (while service is running)
.\test_extraction_service.ps1
```

### Option 2: Manual Testing

1. **Open API Docs**: http://localhost:8081/docs
2. **Test endpoints**:
   ```powershell
   # Root
   curl http://localhost:8081/
   
   # Health check
   curl http://localhost:8081/health
   
   # List requirements
   curl http://localhost:8081/requirements
   
   # Trigger extraction
   curl -X POST http://localhost:8081/extract -H "Content-Type: application/json" -d "{\"force_full_scan\": false}"
   ```

## 🐳 Docker Option (Extraction Service Only)

If you prefer Docker, use the simplified compose file:

```powershell
# Build and run ONLY extraction service + postgres
docker compose -f docker-compose.extraction.yml up --build

# Access at http://localhost:8081
```

## 📊 Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Service info |
| `/health` | GET | Health check (database, taxonomy) |
| `/requirements` | GET | List all requirements (with filters) |
| `/requirements/{update_id}` | GET | Get specific requirement |
| `/extract` | POST | Trigger extraction job |

## 🔍 Monitoring

- **Logs**: Watch the terminal for extraction progress
- **Database**: Check `regulatory_radar.db` (SQLite) or query Postgres
- **API Docs**: http://localhost:8081/docs for interactive testing

## ⚠️ Common Issues

### Port 8081 already in use
```powershell
# Find and kill the process
netstat -ano | findstr :8081
taskkill /PID <PID> /F
```

### Module not found errors
```powershell
# Reinstall dependencies
uv pip install -e extraction_service/
```

### Database connection errors
- For SQLite: Check file permissions in current directory
- For Postgres: Ensure `docker-compose.extraction.yml` postgres is running

## 🎯 Next Steps

1. **Start the service** using one of the methods above
2. **Test endpoints** using the test script or manually
3. **Trigger extraction**: `POST /extract` to fetch live data from CELLAR/ECHA
4. **View results**: `GET /requirements` to see extracted requirements
5. **Integrate**: Once working, connect assessment service (Part 2)

## 📝 Notes

- First extraction may take 5-10 minutes (fetching from live sources)
- CELLAR SPARQL has rate limits (max 5 concurrent connections)
- ECHA caches for 24 hours to be polite
- All requirements include `source_url` for auditability
