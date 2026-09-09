<#
Builds DistractionBlockerWorker.exe (worker) and DistractionBlocker.exe (GUI) into .\dist
using PyInstaller. Run from any shell:  pwsh -File .\build.ps1
#>

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$SrcDir   = Join-Path $RepoRoot "src"
$DistDir  = Join-Path $RepoRoot "dist"
$BuildDir = Join-Path $RepoRoot "build"
$WorkDir  = Join-Path $RepoRoot ".pyi_work"

Push-Location $SrcDir
try {
    Write-Host "Building DistractionBlockerWorker.exe (worker)" -ForegroundColor Cyan
    python -s -m PyInstaller `
        --onefile `
        --noconsole `
        --clean `
        --name "DistractionBlockerWorker" `
        --distpath $DistDir `
        --workpath $WorkDir `
        --specpath $BuildDir `
        worker.py
    if ($LASTEXITCODE -ne 0) {
        throw "DistractionBlockerWorker build failed with exit code $LASTEXITCODE."
    }

    Write-Host "Building DistractionBlocker.exe (GUI)" -ForegroundColor Cyan
    python -s -m PyInstaller `
        --onefile `
        --noconsole `
        --clean `
        --name "DistractionBlocker" `
        --distpath $DistDir `
        --workpath $WorkDir `
        --specpath $BuildDir `
        gui.py
    if ($LASTEXITCODE -ne 0) {
        throw "DistractionBlocker build failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

Write-Host ""
Write-Host "Build complete. Artifacts in: $DistDir" -ForegroundColor Green
Write-Host "Next: run installer\install.ps1 from an elevated PowerShell." -ForegroundColor Green
