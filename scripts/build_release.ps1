[CmdletBinding()]
param(
    [string]$OutputDir = ""
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
        Where-Object { $_.Name -in @("__pycache__", ".pytest_cache", ".ruff_cache", "__MACOSX") } |
        Remove-Item -Recurse -Force

    Get-ChildItem -LiteralPath $Root -Recurse -Force -File |
        Where-Object {
            $_.Extension -in @(".pyc", ".pyo", ".log", ".tmp") -or
            $_.Name -like "*.zip"
        } |
        Remove-Item -Force
}

function Assert-OutsideRepository {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$RepositoryRoot
    )

    $normalizedPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\')
    $normalizedRoot = ([System.IO.Path]::GetFullPath($RepositoryRoot)).TrimEnd('\') + '\'
    if ($normalizedPath.StartsWith($normalizedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "OutputDir must be outside the repository root: $normalizedPath"
    }
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
            throw "ZIP root invalid. Expected only '$PluginFolderName/', but found: $($topLevel -join ', ')"
        }

        $forbiddenPatterns = @(
            '^\.git(/|$)',
            '^\.github(/|$)',
            '^tests(/|$)',
            '^__pycache__(/|$)',
            '\.pytest_cache(/|$)',
            '\.ruff_cache(/|$)',
            '\.pyc$',
            '\.pyo$',
            '__MACOSX(/|$)',
            '\.(exe|dll|so|pyd|dylib)$'
        )

        foreach ($pattern in $forbiddenPatterns) {
            if ($entryNames | Where-Object { $_ -match $pattern }) {
                throw "ZIP contains forbidden artifact matching '$pattern'."
            }
        }

        $requiredEntries = @(
            "$PluginFolderName/__init__.py",
            "$PluginFolderName/metadata.txt",
            "$PluginFolderName/LICENSE",
            "$PluginFolderName/TRADEMARKS.md",
            "$PluginFolderName/README.md",
            "$PluginFolderName/CHANGELOG.md",
            "$PluginFolderName/resources/icon.png",
            "$PluginFolderName/resources/",
            "$PluginFolderName/i18n/",
            "$PluginFolderName/model_view/",
            "$PluginFolderName/report_view/",
            "$PluginFolderName/utils/",
            "$PluginFolderName/ui/"
        )

        foreach ($requiredEntry in $requiredEntries) {
            if (-not ($entryNames | Where-Object { $_ -eq $requiredEntry -or $_.StartsWith($requiredEntry) })) {
                throw "ZIP does not contain required entry '$requiredEntry'."
            }
        }
    }
    finally {
        $archive.Dispose()
    }
}

function Test-ZipPublicClean {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ZipPath
    )

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    try {
        $entryNames = @($archive.Entries | ForEach-Object { $_.FullName.Replace('\', '/') })
        $forbiddenPathPatterns = @(
            '(?i)openai',
            '(?i)langchain',
            '(?i)ollama',
            '(?i)chatgpt',
            '(?i)ai_engine',
            '(?i)hybrid_query',
            '(?i)conversation_memory',
            '(?i)operational_memory',
            '(?i)(^|/)reports_widget\.py$',
            '(?i)(^|/)report_ai_engine\.py$',
            '(?i)(^|/)query_interpreter\.py$',
            '(?i)(^|/)query_preprocessor\.py$',
            '(?i)PowerPages',
            '(?i)Power\s+BI',
            '(?i)powerbi',
            '(?i)Microsoft',
            '(?i)Graphic\s+Walker'
        )

        foreach ($pattern in $forbiddenPathPatterns) {
            $match = $entryNames | Where-Object { $_ -match $pattern } | Select-Object -First 1
            if ($match) {
                throw "ZIP contains forbidden public-release path '$match' matching '$pattern'."
            }
        }

        $forbiddenTextPatterns = @(
            '(?i)openai',
            '(?i)langchain',
            '(?i)ollama',
            '(?i)chatgpt',
            '(?i)ai_engine',
            '(?i)hybrid_query',
            '(?i)conversation_memory',
            '(?i)operational_memory',
            '(?i)\bllm\b',
            '(?i)\bprompt\b',
            '(?i)\bagent\b',
            '(?i)PowerPages',
            '(?i)Power\s+BI',
            '(?i)powerbi',
            '(?i)Microsoft',
            '(?i)Graphic\s+Walker'
        )
        $textExtensions = @(".py", ".txt", ".md", ".json", ".qss", ".svg", ".csv", ".ini")

        foreach ($entry in $archive.Entries) {
            if ([string]::IsNullOrWhiteSpace($entry.Name)) {
                continue
            }
            $extension = [System.IO.Path]::GetExtension($entry.Name)
            if ($textExtensions -notcontains $extension.ToLowerInvariant()) {
                continue
            }
            $reader = New-Object System.IO.StreamReader($entry.Open(), [System.Text.Encoding]::UTF8, $true)
            try {
                $content = $reader.ReadToEnd()
            }
            finally {
                $reader.Dispose()
            }
            foreach ($pattern in $forbiddenTextPatterns) {
                if ($content -match $pattern) {
                    throw "ZIP text audit failed in '$($entry.FullName)' for pattern '$pattern'."
                }
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
$defaultReleaseDir = Join-Path $env:USERPROFILE "Documents\Summarizer_release"
$releaseDir = if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $defaultReleaseDir
}
else {
    $OutputDir
}
$releaseDir = [System.IO.Path]::GetFullPath($releaseDir)
Assert-OutsideRepository -Path $releaseDir -RepositoryRoot $repoRoot
$stageRoot = Join-Path $releaseDir "_staging_release"
$stagePluginRoot = Join-Path $stageRoot $pluginFolderName
$zipPath = Join-Path $releaseDir "Summarizer-qgis-release.zip"

Assert-FileExists -Path (Join-Path $sourcePlugin "metadata.txt") -Message "metadata.txt not found in $sourcePlugin."
Assert-FileExists -Path (Join-Path $sourcePlugin "resources\icon.png") -Message "icon.png not found in $sourcePlugin\resources."

$metadataText = Get-Content -LiteralPath (Join-Path $sourcePlugin "metadata.txt") -Raw
if ($metadataText -notmatch "(?m)^\[general\]\s*$") {
    throw "metadata.txt does not contain the [general] section."
}

foreach ($key in @("name", "version", "icon")) {
    $value = Get-MetadataValue -Text $metadataText -Key $key
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "metadata.txt does not define required key '$key'."
    }
}

$iconRelativePath = Get-MetadataValue -Text $metadataText -Key "icon"
$iconPath = Join-Path $sourcePlugin $iconRelativePath
Assert-FileExists -Path $iconPath -Message "Icon referenced in metadata does not exist: $iconRelativePath"

try {
    Write-Host "Running compileall in $sourcePlugin"
    py -3 -m compileall $sourcePlugin

    Remove-GeneratedArtifacts -Root $sourcePlugin

    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    if (Test-Path -LiteralPath $stageRoot) {
        Remove-Item -LiteralPath $stageRoot -Recurse -Force
    }

    New-Item -ItemType Directory -Path $stagePluginRoot -Force | Out-Null
    Get-ChildItem -LiteralPath $sourcePlugin -Force | Copy-Item -Destination $stagePluginRoot -Recurse -Force
    Remove-GeneratedArtifacts -Root $stageRoot

    Compress-Archive -LiteralPath $stagePluginRoot -DestinationPath $zipPath -CompressionLevel Optimal -Force
    Test-ZipStructure -ZipPath $zipPath -PluginFolderName $pluginFolderName
    Test-ZipPublicClean -ZipPath $zipPath

    Write-Host "ZIP generated at $zipPath"
    Write-Host "Expected structure: $pluginFolderName/..."
}
finally {
    Remove-GeneratedArtifacts -Root $sourcePlugin
    Remove-GeneratedArtifacts -Root $stageRoot
    if (Test-Path -LiteralPath $stageRoot) {
        Remove-Item -LiteralPath $stageRoot -Recurse -Force
    }
    Write-Host "Temporary staging removed from $stageRoot"
}
