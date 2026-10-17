# Reglas Globales de Agentes — p2p-bot-merchant

## Seguridad e Integridad Criptográfica
- **Cero Secretos**: Queda terminantemente prohibido imprimir o persistir API keys, claves privadas o tokens en logs, excepciones o respuestas.
- **Fail-Closed Obligatorio**: Si ocurre cualquier timeout, error 5xx de Binance, discrepancia de estado o falta de configuración, el bot debe detener la operación y notificar al humano.
- **Validación de IP**: Al inicio de la aplicación se debe verificar la IP pública del host contra la lista blanca.

## Estándares de Código y Calidad
- **Python 3.12+**: Tipado estricto con `mypy` en modo riguroso.
- **TDD (Test-Driven Development)**: Ningún cambio de lógica en `src/` se aprueba sin su prueba correspondiente previa en `tests/`.
- **Aislamiento de Dominios**: El motor de reporting/fiscal (`src/reporting/`) no debe tener dependencias circulares con el motor de conexión (`src/core/`).

## Normativa Fiscal y Reconstrucción P2P (Venezuela)
- **Reglas Fiscales**: Consultar y cumplir estrictamente [`.agents/rules/p2p-fiscal-rules.md`](file:///c:/p2p-bot-merchant/.agents/rules/p2p-fiscal-rules.md).
- **Los Tres Reportes Base**: Transaction History, Deposit History (`/sapi/v1/capital/deposit/hisrec`) y Withdrawal History (`/sapi/v1/capital/withdraw/history`).
- **Conciliación Fiat-Cripto**: Cruce obligatorio de datos P2P con tasa oficial BCV (`bcv.org.ve`) y soportes bancarios en bolívares.
- **Ecuación de Consistencia**: $\text{Saldo Inicial} + \text{Entradas} - \text{Salidas} = \text{Saldo Final Esperado}$.
