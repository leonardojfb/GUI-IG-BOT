[CmdletBinding()]
param(
    [string]$OutputDirectory = "releases",
    [switch]$IncludeClientConfig,
    [switch]$IncludeClientDatabase,
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
    "version.json",
    "requirements.txt",
    "gui_premium_v7.py",
    "gui_unificada.py",
    "gui_organizador.py",
    "organizador_simple.py",
    "Organizador.py",
    "database.py",
    "organizadortg.py",
    "videos.py",
    "video_editor.py",
    "metadata_pool.py",
    "telegram_core.py",
    "cleaner.py",
    "vercuentas.py",
    "logo_elittisse.svg",
    "styles/colors.py",
    "styles/components.py",
    "styles/__init__.py"
)

foreach ($File in $ReleaseFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $Root $File) -PathType Leaf)) {
        throw "Falta un archivo requerido para la release: $File"
    }
}

$OutputPath = Join-Path $Root $OutputDirectory
$StagePath = Join-Path ([System.IO.Path]::GetTempPath()) ("metodo_ig_release_" + [guid]::NewGuid().ToString("N"))
$ZipPath = Join-Path $OutputPath ("MetodoIG-v{0}.zip" -f $Version)
$ManifestPath = Join-Path $OutputPath "release-manifest.json"
$RepositoryManifestPath = Join-Path $Root "release-manifest.json"

try {
    New-Item -ItemType Directory -Force -Path $OutputPath | Out-Null
    New-Item -ItemType Directory -Force -Path $StagePath | Out-Null

    foreach ($File in $ReleaseFiles) {
        $Destination = Join-Path $StagePath $File
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Destination) | Out-Null
        Copy-Item -LiteralPath (Join-Path $Root $File) -Destination $Destination
    }

    if ($IncludeClientConfig) {
        $ConfigSource = Join-Path $Root "update_config.json"
        if (-not (Test-Path -LiteralPath $ConfigSource -PathType Leaf)) {
            throw "No existe update_config.json para la entrega inicial."
        }
        Copy-Item -LiteralPath $ConfigSource -Destination (Join-Path $StagePath "update_config.json")
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
    }

    if (Test-Path -LiteralPath $ZipPath) {
        Remove-Item -LiteralPath $ZipPath -Force
    }
    Compress-Archive -Path (Join-Path $StagePath "*") -DestinationPath $ZipPath -CompressionLevel Optimal
    $Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath).Hash.ToLowerInvariant()
    $Manifest = [ordered]@{
        version = $Version
        url = $DownloadUrl
        github_repository = $GitHubRepository
        github_release_tag = "v$Version"
        asset_name = "MetodoIG-v$Version.zip"
        sha256 = $Hash
        notes = $Notes
        files = $ReleaseFiles
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
