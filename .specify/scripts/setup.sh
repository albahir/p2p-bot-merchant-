#!/usr/bin/env bash
set -euo pipefail

echo "==> Configurando entorno de desarrollo para p2p-bot-merchant..."

if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 no está instalado." >&2
    exit 1
fi

python3 -m venv .venv
source .venv/bin/activate || source .venv/Scripts/activate

pip install --upgrade pip
pip install -e ".[dev]"

if [ ! -f config/.env ]; then
    cp config/.env.example config/.env
    echo "==> Se ha creado config/.env a partir de .env.example. Por favor configúralo."
fi

echo "==> Entorno listo."
