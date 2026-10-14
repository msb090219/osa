# Build the Windows release zip: dist/osa-win64.zip
# Usage: powershell -ExecutionPolicy Bypass -File tools\build_win.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-Not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
    .venv\Scripts\pip install -r requirements-dev.txt
    .venv\Scripts\python fetch_models.py
}

& .venv\Scripts\python.exe -m PyInstaller unshrimp.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

if (Test-Path dist\osa-win64.zip) { Remove-Item dist\osa-win64.zip }
Compress-Archive -Path dist\osa -DestinationPath dist\osa-win64.zip
$mb = [math]::Round((Get-Item dist\osa-win64.zip).Length / 1MB, 1)
Write-Host "built dist\osa-win64.zip ($mb MB)"
