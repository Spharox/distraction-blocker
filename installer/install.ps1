#Requires -RunAsAdministrator
<#
Installs Distraction Blocker with a protected privilege boundary:
  1. Copies the worker and GUI to C:\ProgramData\DistractionBlocker
  2. Grants the interactive user write access only to the config subdirectory
  3. Keeps the SYSTEM worker binary and enforcement state protected
  4. Registers a clearly named SYSTEM scheduled task
  5. Migrates configuration from the legacy SystemOptimizer installation
#>

$ErrorActionPreference = "Stop"

$InstallDir       = "C:\ProgramData\DistractionBlocker"
$ConfigDir        = Join-Path $InstallDir "config"
$StateDir         = Join-Path $InstallDir "state"
$TaskName         = "DistractionBlockerWorker"
$WorkerName       = "DistractionBlockerWorker.exe"
$GuiName          = "DistractionBlocker.exe"
$ShortcutName     = "Distraction Blocker.lnk"
$LegacyInstallDir = "C:\ProgramData\SystemOptimizer"
$LegacyTaskName   = "WindowsSystemOptimizer"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$RepoRoot   = Split-Path -Parent $ScriptRoot
$DistDir    = Join-Path $RepoRoot "dist"
$WorkerSrc  = Join-Path $DistDir $WorkerName
$GuiSrc     = Join-Path $DistDir $GuiName

foreach ($sourcePath in @($WorkerSrc, $GuiSrc)) {
    if (-not (Test-Path -LiteralPath $sourcePath)) {
        throw "Missing build artifact: $sourcePath. Run build.ps1 first."
    }
}

# Stop the installed worker before replacing its executable. On Windows, a
# running executable cannot be overwritten even by an elevated process.
Write-Host "Stopping existing Distraction Blocker tasks"
foreach ($existingTaskName in @($TaskName, $LegacyTaskName)) {
    if (Get-ScheduledTask -TaskName $existingTaskName -ErrorAction SilentlyContinue) {
        try { Stop-ScheduledTask -TaskName $existingTaskName -ErrorAction SilentlyContinue } catch {}
        Unregister-ScheduledTask -TaskName $existingTaskName -Confirm:$false
    }
}

# Some Task Scheduler configurations leave the launched process alive after
# Stop-ScheduledTask/Unregister-ScheduledTask. Terminate only processes whose
# executable path exactly matches one of our installed workers.
$installedWorkerPaths = @(
    (Join-Path $InstallDir $WorkerName),
    (Join-Path $LegacyInstallDir "SystemOptimizer.exe")
)
foreach ($processName in @($WorkerName, "SystemOptimizer.exe")) {
    $escapedProcessName = $processName.Replace("'", "''")
    $workerProcesses = Get-CimInstance `
        -ClassName Win32_Process `
        -Filter "Name = '$escapedProcessName'" `
        -ErrorAction Stop
    foreach ($workerProcess in $workerProcesses) {
        $pathMatches = $false
        foreach ($installedWorkerPath in $installedWorkerPaths) {
            if ([string]::Equals(
                $workerProcess.ExecutablePath,
                $installedWorkerPath,
                [System.StringComparison]::OrdinalIgnoreCase
            )) {
                $pathMatches = $true
                break
            }
        }
        if ($pathMatches) {
            Write-Host "Stopping installed worker process $($workerProcess.ProcessId)"
            Stop-Process -Id $workerProcess.ProcessId -Force -ErrorAction Stop
        }
    }
}

function Copy-ReleaseFile {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination,
        [Parameter(Mandatory = $true)][string]$DisplayName
    )

    $lastError = $null
    for ($attempt = 1; $attempt -le 20; $attempt++) {
        try {
            Copy-Item -Force -LiteralPath $Source -Destination $Destination
            return
        }
        catch [System.IO.IOException] {
            $lastError = $_
            Start-Sleep -Milliseconds 250
        }
    }

    throw "Could not update $DisplayName because it is still running. Close Distraction Blocker and rerun the installer. $($lastError.Exception.Message)"
}

Write-Host "Creating protected install directories"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

# Define the root ACL explicitly so reinstalling can never retain a permissive
# rule from an older build. Standard users may execute/read, but only SYSTEM
# and elevated administrators may replace the worker or enforcement state.
$inheritFlags = "ContainerInherit, ObjectInherit"
$rootAcl = New-Object System.Security.AccessControl.DirectorySecurity
$rootAcl.SetAccessRuleProtection($true, $false)
foreach ($principalRule in @(
    @("S-1-5-18", "FullControl"),
    @("S-1-5-32-544", "FullControl"),
    @("S-1-5-32-545", "ReadAndExecute")
)) {
    $sid = New-Object System.Security.Principal.SecurityIdentifier($principalRule[0])
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $sid, $principalRule[1], $inheritFlags, "None", "Allow"
    )
    $rootAcl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $InstallDir -AclObject $rootAcl

Copy-ReleaseFile `
    -Source $WorkerSrc `
    -Destination (Join-Path $InstallDir $WorkerName) `
    -DisplayName $WorkerName
Copy-ReleaseFile `
    -Source $GuiSrc `
    -Destination (Join-Path $InstallDir $GuiName) `
    -DisplayName $GuiName

$InteractiveUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
Write-Host "Granting $InteractiveUser modify rights on configuration only"
$configAcl = Get-Acl -LiteralPath $ConfigDir
$configRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    $InteractiveUser,
    "Modify",
    "ContainerInherit, ObjectInherit",
    "None",
    "Allow"
)
$configAcl.SetAccessRule($configRule)
Set-Acl -LiteralPath $ConfigDir -AclObject $configAcl

if (Test-Path -LiteralPath $LegacyInstallDir) {
    Write-Host "Migrating legacy configuration and active state"
    foreach ($fileName in @("blocklist.json", "schedule.json")) {
        $legacyPath = Join-Path $LegacyInstallDir $fileName
        $newPath = Join-Path $ConfigDir $fileName
        if ((Test-Path -LiteralPath $legacyPath) -and -not (Test-Path -LiteralPath $newPath)) {
            Copy-Item -LiteralPath $legacyPath -Destination $newPath
        }
    }
    $legacyStatePath = Join-Path $LegacyInstallDir "state.json"
    $newStatePath = Join-Path $StateDir "state.json"
    if ((Test-Path -LiteralPath $legacyStatePath) -and -not (Test-Path -LiteralPath $newStatePath)) {
        Copy-Item -LiteralPath $legacyStatePath -Destination $newStatePath
    }
}

Write-Host "Registering scheduled task: $TaskName"
$action = New-ScheduledTaskAction -Execute (Join-Path $InstallDir $WorkerName)
$startupTrigger = New-ScheduledTaskTrigger -AtStartup
$repeatingTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(60) `
    -RepetitionInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger @($startupTrigger, $repeatingTrigger) `
    -Principal $principal `
    -Settings $settings `
    -Description "Enforces Distraction Blocker schedules and focus sessions." | Out-Null

Start-ScheduledTask -TaskName $TaskName

Write-Host "Creating desktop shortcut"
$DesktopDir = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $DesktopDir $ShortcutName
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($ShortcutPath)
$shortcut.TargetPath = Join-Path $InstallDir $GuiName
$shortcut.WorkingDirectory = $InstallDir
$shortcut.IconLocation = (Join-Path $InstallDir $GuiName) + ",0"
$shortcut.Description = "Distraction Blocker"
$shortcut.Save()

if (Test-Path -LiteralPath $LegacyInstallDir) {
    Write-Host "Removing insecure legacy installation directory"
    Remove-Item -LiteralPath $LegacyInstallDir -Recurse -Force
}

Write-Host ""
Write-Host "Installed. Launch from the 'Distraction Blocker' desktop shortcut." -ForegroundColor Green
