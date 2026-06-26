# PowerShell script to run extraction service locally
# Usage: .\run_extraction_service.ps1

Write-Host "🚀 Starting Extraction Service..." -ForegroundColor Green
Write-Host ""

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host "⚠️  No .env file found. Creating from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "✅ Created .env file. Please edit it with your configuration." -ForegroundColor Green
    Write-Host ""
}

# Set environment variables for local testing
$env:DATABASE_URL = "sqlite:///./regulatory_radar.db"
$env:CELLAR_SPARQL_ENDPOINT = "http://publications.europa.eu/webapi/rdf/sparql"
$env:CELLAR_REST_BASE_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/"
$env:ECHA_API_BASE_URL = "https://echa.europa.eu"
$env:ECHA_CANDIDATE_LIST_URL = "https://echa.europa.eu/candidate-list-table"
$env:LOG_LEVEL = "INFO"

Write-Host "📦 Installing dependencies..." -ForegroundColor Cyan
uv pip install -e extraction_service/

Write-Host ""
Write-Host "🔧 Configuration:" -ForegroundColor Cyan
Write-Host "  Database: SQLite (./regulatory_radar.db)" -ForegroundColor Gray
Write-Host "  Port: 8081" -ForegroundColor Gray
Write-Host "  API Docs: http://localhost:8081/docs" -ForegroundColor Gray
Write-Host ""

Write-Host "▶️  Starting service on http://localhost:8081" -ForegroundColor Green
Write-Host "   Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# Run the service (stay in root directory)
uv run uvicorn extraction_service.main:app --reload --port 8081 --host 0.0.0.0
