# Tasks 010: Seguridad Avanzada de API, Control de Concurrencia y Resiliencia

- [x] T-010.1 Diseñar e implementar `src/core/binance_schemas.py` con enums y modelos Pydantic de ordenes e historial.
- [x] T-010.2 Implementar sincronización de reloj y compensación de drift temporal en `src/core/binance_client.py`.
- [x] T-010.3 Implementar clasificación de códigos de error de Binance y suspensión de reintentos ante 401/403 en `binance_client.py`.
- [x] T-010.4 Actualizar `history_ingestor.py` para operar sobre esquemas tipados con comisiones completas.
- [x] T-010.5 Implementar `src/security/key_validator.py` con validación estricta de formato PEM Ed25519/RSA.
- [x] T-010.6 Implementar `src/core/concurrency.py` con mutex de sincronización para evitar dobles ejecuciones.
- [x] T-010.7 Integrar validaciones en el formulario del panel de control (`credential_manager.py` y `control_actions.py`).
- [x] T-010.8 Crear tests unitarios en `tests/unit/test_api_resilience.py` validando drift, locking y validación PEM.
- [x] T-010.9 Desarrollar simulación fidedigna de Sandbox (`MockBinanceP2PClient`), ingesta bidireccional (BUY/SELL) y test E2E de métricas dinámicas (`tests/e2e/test_sandbox_metrics.py`).
- [x] T-010.10 Registrar progreso y actualizar `memory.md`.

