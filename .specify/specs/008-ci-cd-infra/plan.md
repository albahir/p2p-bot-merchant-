# Plan 008: CI/CD e Infraestructura

## Stack
- GitHub Actions (CI/CD workflows).
- Docker y Docker Compose.
- `ruff`, `mypy`, `pytest`, `gitleaks`, `pip-audit`.

## Arquitectura
- `.github/workflows/ci.yml`: pipeline de validación de código.
- `.github/workflows/cd.yml`: pipeline de despliegue a staging/producción.
- `.github/workflows/security.yml`: escaneo periódico y en PR de seguridad.
- `docker/Dockerfile.engine`: contenedor de ejecución del bot.
- `docker/Dockerfile.dashboard`: contenedor del dashboard Streamlit.
- `docker/docker-compose.yml`: orquestación local/staging con PostgreSQL y Redis.

## Decisiones
- **Multi-stage builds en Docker**: reduce la superficie de ataque y tamaño de imagen.
- **Fail-closed en CI**: ante cualquier warning de tipado estricto o linter, el build falla.

## Dependencias
- Paquetes 001, 002, 005, 006, 007.
