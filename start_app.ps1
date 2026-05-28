<#
.SYNOPSIS
    Start AI Agent Lab (Backend + Frontend)

.PARAMETER Env
    Target environment: dev (default) or prod
    dev  -> config.json
    prod -> config.prod.json

.EXAMPLE
    .\start_app.ps1
    .\start_app.ps1 -Env prod
#>
[CmdletBinding()]
param(
    [ValidateSet("dev","prod","test")]
    [string]$Env = "dev"
)

# ── Resolve project root ───────────────────────────────────────────────────
$Root = $PSScriptRoot
if (-not $Root) { $Root = (Get-Location).Path }

# ── Config file map ────────────────────────────────────────────────────────
$ConfigFile = if ($Env -eq "prod") { "config.prod.json" } elseif ($Env -eq "test") { "config.test.json" } else { "config.json" }
$ConfigPath = Join-Path $Root $ConfigFile

Write-Host ("=" * 60)
Write-Host "  AI Agent Lab  --  Environment: $Env"
Write-Host "  Root   : $Root"
Write-Host "  Config : $ConfigPath"
Write-Host ("=" * 60)

if (-not (Test-Path $ConfigPath)) {
    Write-Host "[ERROR] Config file not found: $ConfigPath" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Config file found." -ForegroundColor Green

# ── Backend ────────────────────────────────────────────────────────────────
$BackendScript = @"
`$env:APP_ENV = '$Env'
`$env:PYTHONPATH = '.'
Write-Host '=== Backend (APP_ENV=$Env) ===' -ForegroundColor Cyan
micromamba run -n OCR_GA python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
Read-Host 'Press Enter to exit'
"@

Write-Host "[*] Starting backend in a new window..." -ForegroundColor Magenta
Start-Process powershell.exe -ArgumentList @("-NoExit","-Command",$BackendScript) -WorkingDirectory $Root

# ── Frontend ───────────────────────────────────────────────────────────────
$FrontendDir = Join-Path $Root "frontend"
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "[WARN] node_modules missing -- running npm install..." -ForegroundColor Yellow
    Start-Process -FilePath "npm" -ArgumentList "install" -WorkingDirectory $FrontendDir -Wait -NoNewWindow
}

$FrontendScript = @"
Write-Host '=== Frontend ===' -ForegroundColor Cyan
npm run dev
Read-Host 'Press Enter to exit'
"@

Write-Host "[*] Starting frontend in a new window..." -ForegroundColor Magenta
Start-Process powershell.exe -ArgumentList @("-NoExit","-Command",$FrontendScript) -WorkingDirectory $FrontendDir

# ── Summary ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host ("=" * 60)
Write-Host "  Backend : http://localhost:8000  (docs: /docs)" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host ("=" * 60)
