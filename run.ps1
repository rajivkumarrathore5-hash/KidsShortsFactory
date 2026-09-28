# KidsShortsFactory PowerShell runner
$projectDir = $PSScriptRoot
$pythonExe = Join-Path $projectDir ".venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    Write-Host "[ERROR] Virtual environment python not found at $pythonExe" -ForegroundColor Red
    exit 1
}

Set-Location $projectDir
& $pythonExe (Join-Path $projectDir "main.py") @args
