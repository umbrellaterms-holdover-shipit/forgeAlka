#!/usr/bin/env pwsh
param()

$ErrorActionPreference = 'Stop'

Write-Host 'Upgrading pip...'
python -m pip install --upgrade pip

Write-Host 'Installing editable dependencies...'
python -m pip install -e ".[all]"

Write-Host 'Installing required system dependencies...'
apex deps install ffmpeg pandoc --yes
apex deps doctor

if (Get-Command npm -ErrorAction SilentlyContinue) {
    Write-Host 'Installing React dependencies...'
    Push-Location .\apps\web
    npm install
    Pop-Location
} else {
    Write-Warning 'node/npm not found; skipping React dependency install.'
}

Write-Host 'Running test suite...'
python -m pytest -q
