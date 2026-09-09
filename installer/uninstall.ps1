#Requires -RunAsAdministrator
<# Removes Distraction Blocker, its legacy installation, and only its hosts block. #>

$ErrorActionPreference = "Continue"

$InstallDir       = "C:\ProgramData\DistractionBlocker"
$TaskName         = "DistractionBlockerWorker"
$LegacyInstallDir = "C:\ProgramData\SystemOptimizer"
$LegacyTaskName   = "WindowsSystemOptimizer"
$HostsPath        = "C:\Windows\System32\drivers\etc\hosts"
$MarkerStart      = "# DISTRACTION_BLOCKER_START"
$MarkerEnd        = "# DISTRACTION_BLOCKER_END"
$ShortcutName     = "Distraction Blocker.lnk"

foreach ($existingTaskName in @($TaskName, $LegacyTaskName)) {
    Write-Host "Stopping and removing scheduled task: $existingTaskName"
    if (Get-ScheduledTask -TaskName $existingTaskName -ErrorAction SilentlyContinue) {
        try { Stop-ScheduledTask -TaskName $existingTaskName -ErrorAction SilentlyContinue } catch {}
        Unregister-ScheduledTask -TaskName $existingTaskName -Confirm:$false
    }
}

Write-Host "Clearing hosts-file block (if any)"
if (Test-Path -LiteralPath $HostsPath) {
    $content = Get-Content -LiteralPath $HostsPath -Raw
    $pattern = "(?ms)\s*" + [regex]::Escape($MarkerStart) + ".*?" + [regex]::Escape($MarkerEnd) + "\s*"
    $stripped = [regex]::Replace($content, $pattern, "`r`n")
    if ($stripped -ne $content) {
        Set-Content -LiteralPath $HostsPath -Value $stripped.TrimEnd() -NoNewline
        ipconfig /flushdns | Out-Null
    }
}

foreach ($directory in @($InstallDir, $LegacyInstallDir)) {
    if (Test-Path -LiteralPath $directory) {
        Write-Host "Deleting install directory: $directory"
        Remove-Item -LiteralPath $directory -Recurse -Force
    }
}

$ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) $ShortcutName
if (Test-Path -LiteralPath $ShortcutPath) {
    Remove-Item -LiteralPath $ShortcutPath -Force
}

Write-Host ""
Write-Host "Uninstalled." -ForegroundColor Green
