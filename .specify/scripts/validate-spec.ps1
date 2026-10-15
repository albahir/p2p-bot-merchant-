# PowerShell script para validar especificaciones SDD en Windows
Write-Host "==> Validando integridad de especificaciones SDD..." -ForegroundColor Cyan

$specDirs = Get-ChildItem -Path ".specify\specs" -Directory

foreach ($dir in $specDirs) {
    Write-Host "Revisando: $($dir.FullName)"
    $spec = Join-Path $dir.FullName "spec.md"
    $plan = Join-Path $dir.FullName "plan.md"
    $tasks = Join-Path $dir.FullName "tasks.md"

    if (-not (Test-Path $spec)) { Write-Error "Falta spec.md en $($dir.Name)"; exit 1 }
    if (-not (Test-Path $plan)) { Write-Error "Falta plan.md en $($dir.Name)"; exit 1 }
    if (-not (Test-Path $tasks)) { Write-Error "Falta tasks.md en $($dir.Name)"; exit 1 }
}

Write-Host "==> Todas las especificaciones cumplen la estructura requerida (spec.md, plan.md, tasks.md)." -ForegroundColor Green
