<#
.SYNOPSIS
    Regulatory Radar - start all runnable backend services in dependency order.

.DESCRIPTION
    Builds a single shared virtual environment for the uv workspace, then starts
    the three FastAPI services in order, waiting for each /health endpoint before
    starting the next:

        extraction_service  (8081)  ->  assessment_service (8082)  ->  alerting_service (8083)

    Each downstream service calls the previous one over HTTP, so order matters.

    The dashboard/ and orchestrator/ directories are NOT started: dashboard/ is
    empty and orchestrator/ has no run.py in this checkout.

    Logs stream to ./logs/<service>.log. Press Ctrl+C to stop every service.

.NOTES
    Run from anywhere; the script cd's to its own folder (the repo root).
    Twilio is optional - with no credentials the alerting service simulates sends.

    -WithDb additionally starts the pgvector-enabled Postgres from
    docker-compose.yml, waits for it to become healthy, and applies the Alembic
    migrations before starting the services (needs Docker). Without it the
    services run in the stateless fallback mode (no persistence, no audit).
#>

param([switch]$WithDb)

$ErrorActionPreference = "Stop"

# --- repo root = this script's directory ---------------------------------
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$LogDir = Join-Path $Root "logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

# --- service definitions (ordered) ---------------------------------------
$Services = @(
    @{ Name = "extraction"; Dir = "extraction_service"; Port = 8081 },
    @{ Name = "assessment"; Dir = "assessment_service"; Port = 8082 },
    @{ Name = "alerting";   Dir = "alerting_service";   Port = 8083 }
)

$Procs = @()

function Wait-ForHealth {
    param([int]$Port, [string]$Name, [int]$TimeoutSec = 60)
    $url = "http://localhost:$Port/health"
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -eq 200) {
                Write-Host "  [$Name] healthy at $url" -ForegroundColor Green
                return $true
            }
        } catch {
            Start-Sleep -Milliseconds 700
        }
    }
    Write-Host "  [$Name] did NOT become healthy within $TimeoutSec s - check logs/$Name.log" -ForegroundColor Red
    return $false
}

function Stop-All {
    Write-Host "`nStopping services..." -ForegroundColor Yellow
    foreach ($p in $Procs) {
        if ($p -and -not $p.HasExited) {
            try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {}
        }
    }
}

try {
    # --- 1. ensure .env exists (services read it via pydantic-settings) ----
    if (-not (Test-Path (Join-Path $Root ".env")) -and (Test-Path (Join-Path $Root ".env.example"))) {
        Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
        Write-Host "Created .env from .env.example (edit it for real Twilio sends)." -ForegroundColor Cyan
    }

    # --- 2. build the shared venv + install service dependencies -----------
    # The service projects use a flat module layout (no installable package),
    # and they import the shared `contracts` package via a sys.path bootstrap
    # in each config.py - so we only need their THIRD-PARTY deps in the venv,
    # not the projects themselves. `uv pip install -r <pyproject>` reads
    # [project.dependencies] without trying to build the flat-layout project.
    $Py = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path $Py)) {
        Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Cyan
        & uv venv
        if ($LASTEXITCODE -ne 0) { throw "uv venv failed (exit $LASTEXITCODE)" }
    }

    Write-Host "Installing service dependencies..." -ForegroundColor Cyan
    & uv pip install `
        -r (Join-Path $Root "extraction_service\pyproject.toml") `
        -r (Join-Path $Root "assessment_service\pyproject.toml") `
        -r (Join-Path $Root "alerting_service\pyproject.toml") `
        -r (Join-Path $Root "contracts\pyproject.toml") `
        -r (Join-Path $Root "storage\pyproject.toml")
    if ($LASTEXITCODE -ne 0) { throw "dependency install failed (exit $LASTEXITCODE)" }

    if (-not (Test-Path $Py)) { throw "Expected venv python not found at $Py" }

    # --- 2b. optional: obligation store (Postgres + pgvector) --------------
    if ($WithDb) {
        Write-Host "Starting Postgres (docker compose up -d db)..." -ForegroundColor Cyan
        & docker compose up -d db
        if ($LASTEXITCODE -ne 0) { throw "docker compose up failed (exit $LASTEXITCODE)" }

        Write-Host "Waiting for the database to become healthy..." -ForegroundColor Cyan
        $deadline = (Get-Date).AddSeconds(90)
        $healthy = $false
        while ((Get-Date) -lt $deadline) {
            $state = (& docker inspect --format "{{.State.Health.Status}}" regulatory-radar-db 2>$null)
            if ($state -eq "healthy") { $healthy = $true; break }
            Start-Sleep -Seconds 2
        }
        if (-not $healthy) { throw "Postgres did not become healthy within 90 s" }
        Write-Host "  [db] healthy" -ForegroundColor Green

        Write-Host "Applying migrations (alembic upgrade head)..." -ForegroundColor Cyan
        & $Py -m alembic -c (Join-Path $Root "storage\alembic.ini") upgrade head
        if ($LASTEXITCODE -ne 0) { throw "alembic upgrade failed (exit $LASTEXITCODE)" }
    }

    # --- 3. start each service in order, gating on /health -----------------
    foreach ($svc in $Services) {
        $name = $svc.Name; $dir = Join-Path $Root $svc.Dir; $port = $svc.Port
        $log = Join-Path $LogDir "$name.log"
        Write-Host "Starting $name on port $port ..." -ForegroundColor Cyan

        $p = Start-Process -FilePath $Py `
            -ArgumentList @("-m", "uvicorn", "main:app", "--port", "$port") `
            -WorkingDirectory $dir `
            -RedirectStandardOutput $log `
            -RedirectStandardError "$log.err" `
            -PassThru -NoNewWindow
        $Procs += $p

        if (-not (Wait-ForHealth -Port $port -Name $name)) {
            throw "$name failed to start"
        }
    }

    Write-Host "`nAll services up:" -ForegroundColor Green
    Write-Host "  Extraction : http://localhost:8081/docs"
    Write-Host "  Assessment : http://localhost:8082/docs"
    Write-Host "  Alerting   : http://localhost:8083/docs"
    Write-Host "`nFire the whole pipeline with:" -ForegroundColor Green
    Write-Host '  Invoke-RestMethod -Method Post http://localhost:8083/dispatch'
    Write-Host "`nLogs: $LogDir   |   Press Ctrl+C to stop everything." -ForegroundColor DarkGray

    # --- 4. keep running until Ctrl+C or a service dies --------------------
    while ($true) {
        Start-Sleep -Seconds 2
        foreach ($p in $Procs) {
            if ($p.HasExited) { throw "A service exited unexpectedly (PID $($p.Id)) - check logs." }
        }
    }
}
finally {
    Stop-All
}
