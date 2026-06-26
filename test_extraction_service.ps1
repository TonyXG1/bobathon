# PowerShell script to test extraction service endpoints
# Usage: .\test_extraction_service.ps1

$BASE_URL = "http://localhost:8081"

Write-Host "🧪 Testing Extraction Service" -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green
Write-Host ""

# Test 1: Root endpoint
Write-Host "1️⃣  Testing root endpoint..." -ForegroundColor Cyan
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/" -Method Get
    Write-Host "✅ Root: $($response.service) - $($response.status)" -ForegroundColor Green
} catch {
    Write-Host "❌ Root endpoint failed: $_" -ForegroundColor Red
}
Write-Host ""

# Test 2: Health check
Write-Host "2️⃣  Testing health endpoint..." -ForegroundColor Cyan
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/health" -Method Get
    Write-Host "✅ Health: Status=$($response.status), DB=$($response.database), Taxonomy=$($response.taxonomy)" -ForegroundColor Green
} catch {
    Write-Host "❌ Health check failed: $_" -ForegroundColor Red
}
Write-Host ""

# Test 3: List requirements (should be empty initially)
Write-Host "3️⃣  Testing list requirements..." -ForegroundColor Cyan
try {
    $response = Invoke-RestMethod -Uri "$BASE_URL/requirements" -Method Get
    Write-Host "✅ Requirements: Total=$($response.total), Limit=$($response.limit)" -ForegroundColor Green
} catch {
    Write-Host "❌ List requirements failed: $_" -ForegroundColor Red
}
Write-Host ""

# Test 4: Trigger extraction (background job)
Write-Host "4️⃣  Testing extraction trigger..." -ForegroundColor Cyan
try {
    $body = @{ force_full_scan = $false } | ConvertTo-Json
    $response = Invoke-RestMethod -Uri "$BASE_URL/extract" -Method Post -Body $body -ContentType "application/json"
    Write-Host "✅ Extraction: JobID=$($response.job_id), Status=$($response.status)" -ForegroundColor Green
    Write-Host "   ⏳ Extraction running in background. Check logs for progress." -ForegroundColor Yellow
} catch {
    Write-Host "❌ Extraction trigger failed: $_" -ForegroundColor Red
}
Write-Host ""

Write-Host "================================" -ForegroundColor Green
Write-Host "📊 View API docs: $BASE_URL/docs" -ForegroundColor Cyan
Write-Host "📋 View requirements: $BASE_URL/requirements" -ForegroundColor Cyan
Write-Host ""
