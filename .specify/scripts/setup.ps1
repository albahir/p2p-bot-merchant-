# PowerShell setup script for Windows
Write-Host "==> Configurando entorno de desarrollo para p2p-bot-merchant en Windows..." -ForegroundColor Cyan

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "ERROR: python no está instalado o no se encuentra en el PATH."
    exit 1
}

if (-not (Test-Path ".venv")) {
    Write-Host "==> Creando entorno virtual .venv..."
    python -m venv .venv
}

Write-Host "==> Activando entorno virtual..."
& .\.venv\Scripts\Activate.ps1

Write-Host "==> Instalando dependencias del proyecto..."
python -m pip install --upgrade pip
pip install -e ".[dev]"

if (-not (Test-Path "config\.env")) {
    Copy-Item "config\.env.example" "config\.env"
    Write-Host "==> Se ha creado config\.env a partir de .env.example." -ForegroundColor Yellow
}

Write-Host "==> Entorno configurado exitosamente." -ForegroundColor Green
