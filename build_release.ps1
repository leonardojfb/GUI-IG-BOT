[CmdletBinding()]
param(
    [string]$OutputDirectory = "releases",
    [switch]$IncludeClientDatabase,
    [switch]$BootstrapUpdater,
    [string]$DownloadUrl = "",
    [string]$GitHubRepository = "leonardojfb/GUI-IG-BOT",
    [string]$Notes = ""
)

$ErrorActionPreference = "Stop"
$Root = (Get-Location).Path
$VersionData = Get-Content -Raw -LiteralPath (Join-Path $Root "version.json") | ConvertFrom-Json
$Version = [string]$VersionData.version
if ([string]::IsNullOrWhiteSpace($Version)) {
    throw "version.json no contiene una version."
}

$ReleaseFiles = @(
    "Abrir GUI.bat",
    "Instalar GUI.bat",
    "launch_gui.bat",
    "launcher.py",
    "updater.py",
    "console_encoding.py",
    "version.json",
    "requirements.txt",
    "gui_premium_v7.py",
    "gui_unificada.py",
    "gui_organizador.py",
    "organizador_simple.py",
    "Organizador.py",
    "database.py",
    "airtable_sync.py",
    "organizadortg.py",
    "videos.py",
    "video_editor.py",
    "render_performance.py",
    "metadata_pool.py",
    "trial_content.py",
    "calendar_manifest.py",
    "social_publishing.py",
    "telegram_core.py",
    "cleaner.py",
    "vercuentas.py",
    "catalog/__init__.py",
    "catalog/service.py",
    "captions/__init__.py",
    "captions/importer.py",
    "captions/service.py",
    "vault/__init__.py",
    "vault/backfill.py",
    "vault/integration.py",
    "vault/lineage.py",
    "vault/migration.py",
    "vault/query.py",
    "vault/signatures.py",
    "vault/storage.py",
    "vault/thumbnails.py",
    "logo_elittisse.svg",
    "tools/ffmpeg/bin/ffmpeg.exe",
    "tools/ffmpeg/bin/ffprobe.exe",
    "styles/colors.py",
    "styles/components.py",
    "styles/__init__.py"
)

# Puente para instalaciones cuyo updater aún no permite copiar módulos nuevos.
# Debe publicarse antes de una release que agregue imports locales nuevos.
$BootstrapReleaseFiles = @(
    "updater.py",
    "version.json"
)

if ($BootstrapUpdater) {
    $ReleaseFiles = $BootstrapReleaseFiles
}
$PackageKind = if ($BootstrapUpdater) { "bootstrap" } else { "application" }
$AssetSuffix = if ($BootstrapUpdater) { "-bootstrap" } else { "" }

function Ensure-BundledFfmpegTool {
    param(
        [Parameter(Mandatory=$true)][string]$ExecutableName
    )
    $Target = Join-Path $Root ("tools/ffmpeg/bin/{0}" -f $ExecutableName)
    if (Test-Path -LiteralPath $Target -PathType Leaf) {
        return
    }

    $Command = Get-Command $ExecutableName -ErrorAction SilentlyContinue
    if (-not $Command -or -not (Test-Path -LiteralPath $Command.Source -PathType Leaf)) {
        throw "Falta $ExecutableName. Instala FFmpeg en PATH o coloca $Target antes de generar la release."
    }

    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Target) | Out-Null
    Copy-Item -LiteralPath $Command.Source -Destination $Target -Force
}

if ($ReleaseFiles -contains "tools/ffmpeg/bin/ffmpeg.exe") {
    Ensure-BundledFfmpegTool "ffmpeg.exe"
}
if ($ReleaseFiles -contains "tools/ffmpeg/bin/ffprobe.exe") {
    Ensure-BundledFfmpegTool "ffprobe.exe"
}

foreach ($File in $ReleaseFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root $File) -PathType Leaf)) {
        throw "Falta un archivo requerido para la release: $File"
    }
}

$OutputPath = Join-Path $Root $OutputDirectory
$StagePath = Join-Path ([System.IO.Path]::GetTempPath()) ("metodo_ig_release_" + [guid]::NewGuid().ToString("N"))
$ZipPath = Join-Path $OutputPath ("MetodoIG-v{0}{1}.zip" -f $Version, $AssetSuffix)
$ManifestPath = Join-Path $OutputPath "release-manifest.json"
$RepositoryManifestPath = Join-Path $Root "release-manifest.json"
$PackageFiles = @($ReleaseFiles)

try {
    New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null
    New-Item -ItemType Directory -Force -Path $StagePath | Out-Null

    foreach ($File in $ReleaseFiles) {
        $Destination = Join-Path $StagePath $File
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
        Copy-Item -LiteralPath (Join-Path $Root $File) -Destination $Destination
    }

    if ($BootstrapUpdater) {
        $StagedVersionPath = Join-Path $StagePath "version.json"
        $StagedVersion = Get-Content -Raw -LiteralPath $StagedVersionPath | ConvertFrom-Json
        $StagedVersion | Add-Member -NotePropertyName update_phase -NotePropertyValue "bootstrap" -Force
        $StagedVersionJson = $StagedVersion | ConvertTo-Json -Depth 4
        $StageUtf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($StagedVersionPath, $StagedVersionJson, $StageUtf8NoBom)
    }

    if ($IncludeClientDatabase) {
        # Empaquetar una PLANTILLA limpia y vacia (organizador.default.db), NUNCA la
        # DB real del desarrollador. launcher.py la copia a organizador.db solo si el
        # cliente aun no tiene una: jamas pisa la base de un cliente existente.
        $DefaultDbDest = Join-Path $StagePath "organizador.default.db"
        & python (Join-Path $Root "make_default_db.py") $DefaultDbDest
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $DefaultDbDest -PathType Leaf)) {
            throw "No se pudo generar organizador.default.db para la entrega inicial."
        }
        $PackageFiles += "organizador.default.db"
    }

    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    Compress-Archive -Path (Join-Path $StagePath "*") -DestinationPath $ZipPath -CompressionLevel Optimal
    $Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath).Hash.ToLowerInvariant()
    $Manifest = [ordered]@{
        version = $Version
        package_kind = $PackageKind
        url = $DownloadUrl
        github_repository = $GitHubRepository
        github_release_tag = "v$Version"
        asset_name = "MetodoIG-v$Version$AssetSuffix.zip"
        sha256 = $Hash
        notes = $Notes
        files = $PackageFiles
    }
    $ManifestJson = $Manifest | ConvertTo-Json -Depth 4
    $Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($ManifestPath, $ManifestJson, $Utf8NoBom)
    [System.IO.File]::WriteAllText($RepositoryManifestPath, $ManifestJson, $Utf8NoBom)

    Write-Host "Release creada: $ZipPath"
    Write-Host "SHA-256: $Hash"
    Write-Host "Manifiesto: $ManifestPath"
    Write-Host "Manifiesto para GitHub: $RepositoryManifestPath"
    if (-not $DownloadUrl -and -not $GitHubRepository) {
        Write-Warning "Completa 'url' en release-manifest.json despues de publicar el ZIP."
    }
    elseif ($GitHubRepository) {
        Write-Host "Release privada configurada para GitHub: $GitHubRepository"
    }
}
finally {
    if (Test-Path -LiteralPath $StagePath) {
        Remove-Item -LiteralPath $StagePath -Recurse -Force
    }
}
