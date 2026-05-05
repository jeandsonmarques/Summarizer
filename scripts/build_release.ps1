[CmdletBinding()]
param(
    [string]$OutputZip = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Assert-FileExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw $Message
    }
}

function Get-MetadataValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,
        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    $pattern = "(?m)^$([regex]::Escape($Key))\s*=\s*(.+)$"
    if ($Text -match $pattern) {
        return $Matches[1].Trim()
    }
    return ""
}

function Remove-GeneratedArtifacts {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    if (-not (Test-Path -LiteralPath $Root)) {
        return
    }

    Get-ChildItem -LiteralPath $Root -Recurse -Force -Directory |
        Where-Object { $_.Name -in @("__pycache__", ".pytest_cache", ".ruff_cache") } |
        Remove-Item -Recurse -Force

    Get-ChildItem -LiteralPath $Root -Recurse -Force -File |
        Where-Object {
            $_.Extension -in @(".pyc", ".pyo", ".log", ".tmp") -or
            $_.Name -like "*.zip"
        } |
        Remove-Item -Force
}

function Test-ZipStructure {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ZipPath,
        [Parameter(Mandatory = $true)]
        [string]$PluginFolderName
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        $entryNames = @($archive.Entries | ForEach-Object { $_.FullName.Replace('\', '/') })
        $topLevel = @(
            $entryNames |
                Where-Object { $_ -and $_ -notlike "*/" } |
                ForEach-Object { ($_ -split '/')[0] } |
                Where-Object { $_ } |
                Sort-Object -Unique
        )

        if ($topLevel.Count -ne 1 -or $topLevel[0] -ne $PluginFolderName) {
            throw "ZIP root inválido. Esperado apenas '$PluginFolderName/', mas encontrado: $($topLevel -join ', ')"
        }

        $forbiddenPatterns = @(
            '^\.git(/|$)',
            '^\.github(/|$)',
            '^tests(/|$)',
            '^__pycache__(/|$)',
            '\.pytest_cache(/|$)',
            '\.ruff_cache(/|$)',
            '\.pyc$',
            '\.pyo$'
        )

        foreach ($pattern in $forbiddenPatterns) {
            if ($entryNames | Where-Object { $_ -match $pattern }) {
                throw "ZIP contém artefato proibido correspondente a '$pattern'."
            }
        }
    }
    finally {
        $archive.Dispose()
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sourcePlugin = Join-Path $repoRoot "plugin\Summarizer"
$pluginFolderName = Split-Path $sourcePlugin -Leaf
$releaseDir = Join-Path $repoRoot "_release"
$stageRoot = Join-Path $releaseDir "_staging_release"
$stagePluginRoot = Join-Path $stageRoot $pluginFolderName

if ($OutputZip) {
    $zipPath = if ([System.IO.Path]::IsPathRooted($OutputZip)) {
        $OutputZip
    }
    else {
        Join-Path $releaseDir $OutputZip
    }
}
else {
    $zipPath = Join-Path $releaseDir "Summarizer-qgis-release.zip"
}

Assert-FileExists -Path (Join-Path $sourcePlugin "metadata.txt") -Message "metadata.txt não encontrado em $sourcePlugin."
Assert-FileExists -Path (Join-Path $sourcePlugin "resources\icon.png") -Message "icon.png não encontrado em $sourcePlugin\resources."

$metadataText = Get-Content -LiteralPath (Join-Path $sourcePlugin "metadata.txt") -Raw
if ($metadataText -notmatch "(?m)^\[general\]\s*$") {
    throw "metadata.txt não possui a seção [general]."
}

foreach ($key in @("name", "version", "icon")) {
    $value = Get-MetadataValue -Text $metadataText -Key $key
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "metadata.txt não informa a chave obrigatória '$key'."
    }
}

$iconRelativePath = Get-MetadataValue -Text $metadataText -Key "icon"
$iconPath = Join-Path $sourcePlugin $iconRelativePath
Assert-FileExists -Path $iconPath -Message "Ícone referenciado no metadata não existe: $iconRelativePath"

Write-Host "Rodando compileall em $sourcePlugin"
py -3 -m compileall $sourcePlugin

Remove-GeneratedArtifacts -Root $sourcePlugin

if (Test-Path -LiteralPath $stageRoot) {
    Remove-Item -LiteralPath $stageRoot -Recurse -Force
}
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

New-Item -ItemType Directory -Path $stagePluginRoot -Force | Out-Null
Get-ChildItem -LiteralPath $sourcePlugin -Force | Copy-Item -Destination $stagePluginRoot -Recurse -Force
Remove-GeneratedArtifacts -Root $stageRoot

if (-not (Test-Path -LiteralPath $zipPath)) {
    New-Item -ItemType Directory -Path (Split-Path $zipPath -Parent) -Force | Out-Null
}

Compress-Archive -LiteralPath $stagePluginRoot -DestinationPath $zipPath -CompressionLevel Optimal -Force
Test-ZipStructure -ZipPath $zipPath -PluginFolderName $pluginFolderName

Remove-GeneratedArtifacts -Root $sourcePlugin
Remove-GeneratedArtifacts -Root $stageRoot
if (Test-Path -LiteralPath $stageRoot) {
    Remove-Item -LiteralPath $stageRoot -Recurse -Force
}

Write-Host "ZIP gerado em $zipPath"
Write-Host "Estrutura esperada: $pluginFolderName/..."
