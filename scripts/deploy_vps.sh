#!/usr/bin/env bash
# Script de aprovisionamiento y despliegue 24/7 en VPS Ubuntu (SPEC-013 T07)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/config/.env"
COMPOSE_FILE="${REPO_ROOT}/docker/docker-compose.yml"

cd "${REPO_ROOT}"

echo "==> [1/6] Verificando Docker y Docker Compose..."
if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker no está instalado. Instálalo primero desde https://get.docker.com"
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: El plugin 'docker compose' no está disponible."
  exit 1
fi

echo "==> [2/6] Verificando archivo de entorno config/.env..."
if [ ! -f "${ENV_FILE}" ]; then
  cp "${REPO_ROOT}/config/.env.example" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
  echo "AVISO FAIL-CLOSED: Se creó config/.env desde la plantilla."
  echo "Edita config/.env con claves reales (MASTER_ENCRYPTION_KEY, POSTGRES_PASSWORD, TELEGRAM_BOT_TOKEN) y vuelve a ejecutar este script."
  exit 1
fi
chmod 600 "${ENV_FILE}"

get_env_val() {
  local key="$1"
  local line
  line=$(grep -E "^${key}=" "${ENV_FILE}" | tail -n 1 || true)
  printf '%s' "${line#*=}" | tr -d '\r' | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}

MASTER_KEY="$(get_env_val MASTER_ENCRYPTION_KEY)"
PG_PASS="$(get_env_val POSTGRES_PASSWORD)"
DB_URL="$(get_env_val DATABASE_URL)"
WHITELIST="$(get_env_val SERVER_IP_WHITELIST)"
ENVIRONMENT_VAL="$(get_env_val ENVIRONMENT)"

if [ "${#MASTER_KEY}" -lt 32 ] || [ "${MASTER_KEY}" = "replace_with_32_byte_hex_key_here" ]; then
  echo "ERROR FAIL-CLOSED: MASTER_ENCRYPTION_KEY en config/.env es inválida o usa el valor plantilla."
  exit 1
fi

if [ -z "${PG_PASS}" ] || [ "${PG_PASS}" = "replace_with_strong_postgres_password" ]; then
  if [[ "${DB_URL}" == *"@postgres:"* ]]; then
    echo "ERROR FAIL-CLOSED: Configura una POSTGRES_PASSWORD segura en config/.env antes de desplegar PostgreSQL."
    exit 1
  fi
fi

if [[ "${DB_URL}" == *"localhost"* ]] || [[ "${DB_URL}" == *"127.0.0.1"* ]]; then
  echo "ADVERTENCIA: DATABASE_URL apunta a localhost/127.0.0.1; dentro de Docker usa host 'postgres' o un DSN externo."
fi

echo "==> [3/6] Detectando IP pública saliente (Binance IP Whitelist)..."
PUBLIC_IP="$(curl -fsS --max-time 5 https://api.ipify.org || true)"
if [ -n "${PUBLIC_IP}" ]; then
  echo "IP Pública Saliente detectada: ${PUBLIC_IP}"
  if [ "${ENVIRONMENT_VAL}" = "production" ] && [[ ",${WHITELIST}," != *",${PUBLIC_IP},"* ]] && [[ ",${WHITELIST}," != *",0.0.0.0,"* ]]; then
    echo "ERROR FAIL-CLOSED: En producción, la IP pública ${PUBLIC_IP} debe estar incluida en SERVER_IP_WHITELIST (config/.env)."
    exit 1
  fi
else
  echo "ADVERTENCIA: No se pudo detectar la IP pública saliente."
fi

echo "==> [4/6] Configurando Firewall UFW (solo SSH 22, HTTP 80, HTTPS 443)..."
if command -v ufw >/dev/null 2>&1; then
  ufw allow 22/tcp >/dev/null || true
  ufw allow 80/tcp >/dev/null || true
  ufw allow 443/tcp >/dev/null || true
  ufw --force enable >/dev/null || true
  echo "Firewall UFW activo (PostgreSQL 5432 y Redis 6379 permanecen aislados del exterior)."
fi

echo "==> [5/6] Construyendo e iniciando contenedores en segundo plano..."
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --build --remove-orphans
docker image prune -f >/dev/null 2>&1 || true

echo "==> [6/6] Verificando estado de servicios..."
sleep 5
docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" ps
if curl -fsS http://127.0.0.1/health >/dev/null 2>&1; then
  echo "✅ API y Proxy Caddy respondiendo correctamente en /health."
else
  echo "ℹ️ Los contenedores siguen iniciando; revisa el log con:"
  echo "   docker compose --env-file config/.env -f docker/docker-compose.yml logs -f --tail=50"
fi
