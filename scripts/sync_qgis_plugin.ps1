param(
    [string]$ProfileName = "default",
    [string]$TargetFolderName,
    [switch]$AllowWhileRunning
)

$ErrorActionPreference = "Stop"

function Invoke-RobocopyChecked {
    param(
        [string]$Source,
        [string]$Destination,
        [string[]]$Arguments
    )

    & robocopy $Source $Destination @Arguments | Out-Null
    if ($LASTEXITCODE -gt 7) {
        throw "robocopy failed with exit code $LASTEXITCODE"
    }

    return $LASTEXITCODE
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$sourceDir = Join-Path $repoRoot "plugin\\power_bi_summarizer"
if (-not (Test-Path $sourceDir)) {
    throw "Plugin source folder not found: $sourceDir"
}

$pluginsRoot = Join-Path $env:APPDATA ("QGIS\\QGIS3\\profiles\\{0}\\python\\plugins" -f $ProfileName)
New-Item -ItemType Directory -Force -Path $pluginsRoot | Out-Null

$qgisProcesses = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like "qgis*" }
if ($qgisProcesses -and -not $AllowWhileRunning) {
    throw "QGIS is running. Close it before syncing, or rerun with -AllowWhileRunning."
}

$candidateNames = @()
if ($TargetFolderName) {
    $candidateNames += $TargetFolderName
}
$candidateNames += @("PowerBISummarizer", "power_bi_summarizer")
$candidateNames = $candidateNames | Select-Object -Unique

$targetDir = $null
foreach ($name in $candidateNames) {
    $candidate = Join-Path $pluginsRoot $name
    if (Test-Path $candidate) {
        $targetDir = $candidate
        break
    }
}

if (-not $targetDir) {
    $defaultFolderName = if ($TargetFolderName) { $TargetFolderName } else { "PowerBISummarizer" }
    $targetDir = Join-Path $pluginsRoot $defaultFolderName
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
}

$sourceResolved = (Resolve-Path $sourceDir).Path
$pluginsRootResolved = (Resolve-Path $pluginsRoot).Path
$targetResolved = (Resolve-Path $targetDir).Path

if (-not $targetResolved.StartsWith($pluginsRootResolved, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to sync outside the QGIS plugins directory: $targetResolved"
}

$backupRoot = Join-Path $pluginsRootResolved "_backup"
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

$backupDir = $null
if ((Get-ChildItem -Force -ErrorAction SilentlyContinue $targetResolved | Measure-Object).Count -gt 0) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $backupDir = Join-Path $backupRoot ("{0}-{1}" -f (Split-Path $targetResolved -Leaf), $timestamp)
    New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
    $backupCode = Invoke-RobocopyChecked -Source $targetResolved -Destination $backupDir -Arguments @(
        "/E", "/R:1", "/W:1", "/NFL", "/NDL", "/NJH", "/NJS", "/NP"
    )
} else {
    $backupCode = 0
}

$syncCode = Invoke-RobocopyChecked -Source $sourceResolved -Destination $targetResolved -Arguments @(
    "/MIR", "/R:1", "/W:1",
    "/XD", "__pycache__",
    "/XF", "*.pyc", "*.pyo",
    "relatorios_debug.log",
    "relatorios_memory.sqlite3",
    "relatorios_memory.sqlite3-shm",
    "relatorios_memory.sqlite3-wal",
    "_tmp_orig.txt"
)

Get-ChildItem -Path $targetResolved -Recurse -Force -Directory -Filter "__pycache__" |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Recurse -Force }

Get-ChildItem -Path $targetResolved -Recurse -Force -File |
    Where-Object {
        $_.Extension -in @(".pyc", ".pyo") -or
        $_.Name -in @(
            "relatorios_debug.log",
            "relatorios_memory.sqlite3",
            "relatorios_memory.sqlite3-shm",
            "relatorios_memory.sqlite3-wal",
            "_tmp_orig.txt"
        )
    } |
    ForEach-Object { Remove-Item -LiteralPath $_.FullName -Force }

Write-Output "Source: $sourceResolved"
Write-Output "Target: $targetResolved"
if ($backupDir) {
    Write-Output "Backup: $backupDir"
}
Write-Output "Backup robocopy exit code: $backupCode"
Write-Output "Sync robocopy exit code: $syncCode"
Write-Output "QGIS plugin sync complete."
