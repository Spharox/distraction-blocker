param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$DistDir = Join-Path $RepoRoot "dist"
$ReleaseDir = Join-Path $RepoRoot "release"
$StageDir = Join-Path $ReleaseDir "DistractionBlocker-v$Version-windows-x64"
$ArchivePath = "$StageDir.zip"

$artifacts = @(
    (Join-Path $DistDir "DistractionBlocker.exe"),
    (Join-Path $DistDir "DistractionBlockerWorker.exe")
)
foreach ($artifact in $artifacts) {
    if (-not (Test-Path -LiteralPath $artifact)) {
        throw "Missing build artifact: $artifact. Run build.ps1 first."
    }
}

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
if (Test-Path -LiteralPath $StageDir) {
    Remove-Item -LiteralPath $StageDir -Recurse -Force
}
if (Test-Path -LiteralPath $ArchivePath) {
    Remove-Item -LiteralPath $ArchivePath -Force
}

New-Item -ItemType Directory -Path $StageDir | Out-Null
New-Item -ItemType Directory -Path (Join-Path $StageDir "installer") | Out-Null
Copy-Item -LiteralPath $artifacts -Destination $StageDir
Copy-Item -LiteralPath (Join-Path $RepoRoot "installer\install.ps1") -Destination (Join-Path $StageDir "installer")
Copy-Item -LiteralPath (Join-Path $RepoRoot "installer\uninstall.ps1") -Destination (Join-Path $StageDir "installer")
Copy-Item -LiteralPath (Join-Path $RepoRoot "README.md") -Destination $StageDir
Copy-Item -LiteralPath (Join-Path $RepoRoot "LICENSE") -Destination $StageDir

Compress-Archive -LiteralPath $StageDir -DestinationPath $ArchivePath -CompressionLevel Optimal
Remove-Item -LiteralPath $StageDir -Recurse -Force
Write-Host "Release package created: $ArchivePath" -ForegroundColor Green
