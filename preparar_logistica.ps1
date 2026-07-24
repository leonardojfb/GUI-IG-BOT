[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Folder,

    [Parameter(Mandatory = $true)]
    [string]$Category
)

$ErrorActionPreference = 'Stop'
$resolvedFolder = (Resolve-Path -LiteralPath $Folder).Path
$categoryId = $Category.Trim()

if ([string]::IsNullOrWhiteSpace($categoryId)) {
    throw 'La categoria no puede estar vacia.'
}

$files = Get-ChildItem -LiteralPath $resolvedFolder -File |
    Where-Object { $_.Extension -match '^\.mp4$|^\.mov$' }

if (-not $files) {
    Write-Host "No hay archivos MP4 o MOV en: $resolvedFolder" -ForegroundColor Yellow
    exit 0
}

$operations = foreach ($file in $files) {
    # Ejemplo: Output 14 (11) (1)_foto05_editado.mp4
    # Resultado: EDITADAS__Output 14 (11) (1)__foto05_editado.mp4
    $match = [regex]::Match(
        $file.BaseName,
        '^(?<p1>.+)_foto(?<photo>\d+)_editado(?<suffix>_\d+)?$'
    )

    if (-not $match.Success) {
        [pscustomobject]@{
            Source = $file.Name
            Target = $null
            Status = 'IGNORADO: no coincide con *_fotoXX_editado'
        }
        continue
    }

    $p1 = $match.Groups['p1'].Value
    $p2 = "foto$($match.Groups['photo'].Value)_editado$($match.Groups['suffix'].Value)"
    $newName = "${categoryId}__${p1}__${p2}$($file.Extension)"
    $targetPath = Join-Path $resolvedFolder $newName

    if ($newName -eq $file.Name) {
        $status = 'YA CORRECTO'
    } elseif (Test-Path -LiteralPath $targetPath) {
        $status = 'NO SE TOCA: destino ya existe'
    } else {
        $status = 'RENOMBRAR'
    }

    [pscustomobject]@{
        Source = $file.Name
        Target = $newName
        Status = $status
        SourcePath = $file.FullName
        TargetPath = $targetPath
    }
}

Write-Host "`nCarpeta: $resolvedFolder" -ForegroundColor Cyan
Write-Host "Categoria: $categoryId`n" -ForegroundColor Cyan
$operations | Select-Object Source, Target, Status | Format-Table -AutoSize

$pending = @($operations | Where-Object { $_.Status -eq 'RENOMBRAR' })
$blocked = @($operations | Where-Object { $_.Status -like 'NO SE TOCA*' })

if ($blocked.Count -gt 0) {
    Write-Host "Hay $($blocked.Count) destino(s) existente(s); no se sobrescribiran." -ForegroundColor Yellow
}

if ($pending.Count -eq 0) {
    Write-Host 'No hay renombrados pendientes.' -ForegroundColor Green
    exit 0
}

$answer = Read-Host "Renombrar $($pending.Count) archivo(s)? Escribe S para confirmar"
if ($answer -notmatch '^(s|si|sí)$') {
    Write-Host 'Operacion cancelada.' -ForegroundColor Yellow
    exit 0
}

foreach ($operation in $pending) {
    Move-Item -LiteralPath $operation.SourcePath -Destination $operation.TargetPath
}

Write-Host "`nListo: $($pending.Count) archivo(s) preparados para Logistica." -ForegroundColor Green
Write-Host 'Formato generado: CATEGORIA__P1__P2.mp4' -ForegroundColor Green
