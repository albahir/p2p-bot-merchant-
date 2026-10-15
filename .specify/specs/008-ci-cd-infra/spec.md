# Spec 008: CI/CD e Infraestructura

## QUÉ
Pipeline de integración y despliegue continuo con GitHub Actions, contenedores Docker y verificación de seguridad automatizada.

## Requisitos Funcionales
- RF-01: CI en cada push/PR: linting (`ruff`), análisis de tipos (`mypy`), tests unitarios e integración (`pytest`).
- RF-02: Escaneo estricto de secretos con `gitleaks` y vulnerabilidades en dependencias con `pip-audit`.
- RF-03: CD automatizado a staging ante merge a `main`, ejecutando smoke tests post-deploy.
- RF-04: CD a producción con aprobación manual y control de entorno.
- RF-05: Verificación estricta de que ningún `.env` ni claves privadas estén trackeados.

## Criterios de Aceptación
- [ ] Pipeline CI finaliza exitosamente sobre el código base.
- [ ] Escaneo de seguridad bloquea PR si detecta claves simuladas.
- [ ] Imágenes Docker para engine y dashboard construyen sin errores.
