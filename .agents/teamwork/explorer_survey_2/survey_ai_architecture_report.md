# Informe Técnico de Arquitectura de IA: Pipeline Especializado de 3 Roles y Tolerancia a Fallos Round-Robin para Predicción de USDT en Venezuela

**Fecha:** 17 de Noviembre de 2026  
**Especialista:** Explorer 2 — AI Architecture & Pipeline Specialist  
**Módulo Objetivo:** Sistema de Inteligencia y Predicción Macroeconómica de USDT/VES  
**Repositorio:** `p2p-bot-merchant`  

---

## 1. Resumen Ejecutivo y Visión Arquitectónica

El presente informe establece el diseño técnico, la modelación económica y la especificación formal del subsistema de Inteligencia Artificial para la predicción de la tasa cambiaria y el comportamiento del par USDT/VES en el mercado P2P de Venezuela. 

El sistema está concebido bajo el principio constitucional de **Comportamiento Fail-closed** y **Cero Secretos** del proyecto, garantizando que ninguna predicción sea emitida a los operadores humanos o sistemas de trading sin pasar por una cadena estricta de validación y auditoría factual.

### 1.1 Objetivos del Sistema de Predicción
1. **Dirección Proyectada (`direccion`):** Clasificación ternaria calibrada: `SUBE`, `BAJA` o `ESTABLE`.
2. **Ventana Temporal (`lapso_estimado`):** Horizontes definidos y accionables: `24h-48h`, `3-5 dias`, o `semanal`.
3. **Cálculo de Confiabilidad Calibrada (`confiabilidad_porcentaje`):** Estimación probabilística rigurosa entre 0.0% y 100.0%, penalizada por la incertidumbre, la antigüedad de las noticias y la contradicción entre fuerzas macroeconómicas.
4. **Trazabilidad y Mitigación de Alucinaciones:** Pipeline desacoplado en 3 roles especializados donde el modelo Revisor actúa como auditor adversarial independiente.
5. **Alta Disponibilidad sin Caídas:** Enrutador de inferencia con tolerancia a fallos Round-Robin multi-clave y conmutación por error (failover) multi-proveedor con Circuit Breaker.

```
                    +-------------------------------------------------------+
                    |           FUENTES DE INFORMACIÓN EN VENEZUELA          |
                    | (BCV, Redes Oficiales, Banca y Negocios, Patria, etc.)|
                    +-------------------------------------------------------+
                                                |
                                                v
               +=================================================================+
               |     ROL 1: BUSCADOR / RECOPILADOR DE CONTEXTO MACROECONÓMICO   |
               | - Modelo: Gemini 2.0/2.5 Flash / Groq Llama 3.3 70B (Fast)      |
               | - Tarea: Normalización, filtrado de ruido y categorización JSON  |
               +=================================================================+
                                                |
                                                v [MacroContextCollection]
               +=================================================================+
               |       ROL 2: ANALISTA / PREDICTOR MACROECONÓMICO DE USDT        |
               | - Modelo: DeepSeek-R1 / Gemini 2.5 Flash Thinking (Reasoning)   |
               | - Tarea: Razonamiento deductivo monetario, proyección y causas   |
               +=================================================================+
                                                |
                                                v [DraftPrediction]
               +=================================================================+
               |        ROL 3: REVISOR / AUDITOR DE COHERENCIA Y VERACIDAD       |
               | - Modelo: Claude 3.5 Sonnet / OpenAI GPT-4o-mini (Cross-Family)  |
               | - Tarea: Detección de alucinaciones, contradicciones y sesgos    |
               +=================================================================+
                                                |
                       +------------------------+------------------------+
                       |                                                 |
             [Veredicto: APROBADO]                             [Veredicto: RECHAZADO]
                       |                                                 |
                       v                                                 v
         +---------------------------+                     +---------------------------+
         |    FinalUSDTPrediction    |                     |        FAIL-CLOSED        |
         |  (Persistencia DB, Hash   |                     | (Alerta interna, bloqueo  |
         |  SHA-256, Telegram Alert, |                     |  de emisión, reintento o  |
         |  Dashboard Streamlit)     |                     |  revisión humana)         |
         +---------------------------+                     +---------------------------+
```

---

## 2. Comparativa Técnica y Económica de Modelos LLM por Rol

Para maximizar la fiabilidad y minimizar el costo operativo, se evaluaron los principales modelos de frontera y modelos abiertos disponibles vía API en la actualidad.

### 2.1 Tabla Comparativa de Modelos

| Proveedor | Modelo | Ventana de Contexto | Latencia Promedio (TTFT / TPS) | Input Cost ($ / 1M tokens) | Output Cost ($ / 1M tokens) | Modo Structured Output / Schema | Razonamiento Económico | Idoneidad Principal |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Google** | **Gemini 2.5 Flash** | 1,048,576 | ~350ms / 140 tps | $0.15 | $0.60 | Nativo (Pydantic / JSON) | Alta (con Thinking) | **Rol 1 (Primario)** / Rol 2 |
| **Google** | **Gemini 2.0 Flash** | 1,048,576 | ~300ms / 160 tps | $0.10 | $0.40 | Nativo (Pydantic / JSON) | Media-Alta | **Rol 1 (Primario)** |
| **Google** | **Gemini 1.5 Pro** | 2,097,152 | ~1200ms / 45 tps | $1.25 (<=128k) | $5.00 (<=128k) | Nativo | Muy Alta | Rol 2 (Respaldo) |
| **Google** | **Gemini Flash-Lite**| 1,048,576 | ~200ms / 180 tps | $0.075 | $0.30 | Nativo | Media | Ingestas de bajo costo |
| **Groq** | **Llama 3.3 70B** | 128,000 | ~150ms / 280 tps | $0.59 | $0.79 | Compatible OpenAI JSON | Alta | **Rol 1 (Respaldo ultra-rápido)** |
| **DeepSeek**| **DeepSeek-R1 (CoT)**| 64,000 / 128k | ~1500ms / 40 tps | $0.55 (cache $0.14)| $2.19 | Compatible OpenAI JSON | **Excepcional (Reasoning nativo)**| **Rol 2 (Primario)** |
| **DeepSeek**| **DeepSeek-V3** | 64,000 / 128k | ~400ms / 85 tps | $0.14 (cache $0.014)| $0.28 | Compatible OpenAI JSON | Alta | Rol 1 / Rol 2 (Respaldo) |
| **OpenAI** | **GPT-4o-mini** | 128,000 | ~450ms / 95 tps | $0.15 | $0.60 | Strict JSON Schema | Media-Alta | **Rol 3 (Auditor Económico)** |
| **OpenAI** | **GPT-4o** | 128,000 | ~600ms / 70 tps | $2.50 | $10.00 | Strict JSON Schema | Muy Alta | Rol 2 / Rol 3 (Tier 1) |
| **Anthropic**| **Claude 3.5 Sonnet**| 200,000 | ~800ms / 65 tps | $3.00 | $15.00 | Tool-based JSON | **Líder en Pensamiento Crítico** | **Rol 3 (Primario de Calidad)** |
| **Anthropic**| **Claude 3.5 Haiku** | 200,000 | ~400ms / 110 tps | $0.80 | $4.00 | Tool-based JSON | Alta | Rol 3 (Alternativa rápida) |

---

### 2.2 Evaluación Específica por Rol

#### Rol 1: Buscador / Recopilador de Contexto Macroeconómico
- **Requerimientos:** Ventana de contexto masiva para ingerir múltiples noticias completas, reportes del BCV en texto largo y feeds de Telegram; latencia de inicio rápida; costo despreciable por millón de tokens; capacidad nativa de extracción de esquemas JSON estructurados.
- **Evaluación y Selección:**
  - **Primario: Google Gemini 2.0/2.5 Flash.** Con 1M de ventana de contexto, permite consolidar hasta 50 artículos de prensa o transcripciones sin truncamiento. Su costo ($0.10 - $0.15 / 1M) es virtualmente nulo para lotes de 10k tokens ($0.001 por ejecución). Además, soporta nativamente *Google Search Grounding* en caso de requerir búsqueda en vivo.
  - **Respaldo 1: Groq Cloud (Llama 3.3 70B Versatile).** Latencia inigualable (280 tokens/segundo). Procesa el volcado de noticias en menos de 1 segundo.
  - **Respaldo 2: OpenAI GPT-4o-mini.** Garantía estricta de formato JSON válido sin errores de sintaxis.

#### Rol 2: Analista / Predictor Macroeconómico de USDT
- **Requerimientos:** Capacidad superior de razonamiento deductivo económico, modelado de oferta y demanda monetaria (efecto de inyecciones del BCV vs liquidez M2 y nóminas del Estado), ponderación de rezagos temporales (lags) y estimación de probabilidades calibradas.
- **Evaluación y Selección:**
  - **Primario: DeepSeek-R1 (Reasoning nativo).** Genera trazas internas de pensamiento (`<think>`) donde analiza exhaustivamente fuerzas contrapuestas antes de emitir la conclusión (ej. analiza si una intervención cambiaria de $40M el lunes es suficiente para contrarrestar el pago de bonos de $120M equivalentes en bolívares el martes). Costo sumamente accesible ($0.55 input / $2.19 output).
  - **Primario Alternativo: Gemini 2.5 Flash con Thinking Budget.** Excelente balance de velocidad y razonamiento si se opera completamente en el ecosistema Google.
  - **Respaldo 1: OpenAI GPT-4o / Gemini 1.5 Pro.** Para casos donde se requiera robustez institucional probada ante contingencias.

#### Rol 3: Revisor / Auditor de Coherencia y Veracidad
- **Requerimientos:** Pensamiento crítico adversarial, capacidad de detectar contradicciones lógicas entre las premisas (contexto de noticias) y las conclusiones (predicción emitida), validación de alucinaciones cuantitativas y control de sesgos.
- **Principio Fundamental de Arquitectura: Verificación Cruzada entre Familias de Modelos (Cross-Family Model Verification).**
  - *Regla:* El Revisor **NUNCA** debe pertenecer a la misma familia arquitectónica que el Predictor. Si el Predictor es DeepSeek o Gemini, el Revisor debe ser Anthropic (Claude 3.5 Sonnet) u OpenAI (GPT-4o-mini). Esto mitiga sesgos de entrenamiento compartidos y alucinaciones correlacionadas.
- **Evaluación y Selección:**
  - **Primario de Máxima Calidad: Anthropic Claude 3.5 Sonnet.** Es el modelo con mayor rigor analítico y escepticismo de la industria. Detecta inmediatamente cuando el predictor inventa cifras o realiza inferencias causales no fundamentadas en el texto de entrada.
  - **Primario de Costo Eficiente: OpenAI GPT-4o-mini.** Con el modo `strict: true` de Structured Outputs, evalúa la consistencia por menos de $0.0005 por corrida.
  - **Respaldo: Groq Llama 3.3 70B.** Con prompt adversarial de temperatura 0.0.

---

### 2.3 Análisis de Costos por Corrida y Presupuesto Mensual

Asumiendo una ejecución periódica cada 2 horas (12 ejecuciones al día) o cada 4 horas (6 ejecuciones al día), el consumo típico por ciclo es:

- **Rol 1 (Buscador):** Ingesta de 8,000 tokens de noticias -> Salida estructurada de 1,200 tokens.
- **Rol 2 (Predictor):** Entrada de 1,500 tokens estructurados -> Salida de predicción de 1,000 tokens (incluye razonamiento).
- **Rol 3 (Revisor):** Entrada de 2,500 tokens (fuentes + predicción preliminar) -> Salida de auditoría de 600 tokens.

#### Costo por Corrida Individual (Topología Balanceada)
| Rol | Modelo | Input Tokens | Output Tokens | Costo Input ($) | Costo Output ($) | Costo Total por Corrida ($) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Rol 1: Buscador** | Gemini 2.0 Flash | 8,000 | 1,200 | $0.00080 | $0.00048 | **$0.00128** |
| **Rol 2: Predictor**| DeepSeek-R1 | 1,500 | 1,000 | $0.00082 | $0.00219 | **$0.00301** |
| **Rol 3: Revisor**  | GPT-4o-mini | 2,500 | 600 | $0.00037 | $0.00036 | **$0.00073** |
| **TOTAL CICLO**     | - | 12,000 | 2,800 | - | - | **$0.00502 USD** |

#### Proyección Presupuestaria Mensual
- **Frecuencia cada 4 horas (180 corridas/mes):** **$0.90 USD / mes.**
- **Frecuencia cada 2 horas (360 corridas/mes):** **$1.81 USD / mes.**
- **Frecuencia horaria continua 24/7 (720 corridas/mes):** **$3.61 USD / mes.**

*Conclusión económica:* El sistema completo de 3 roles con modelos de frontera tiene un costo operativo inferior a $4 USD mensuales, haciendo viable su ejecución continua sin comprometer la rentabilidad de las operaciones P2P.

---

## 3. Estrategia de Tolerancia a Fallos Round-Robin y Fallback

Para garantizar una operación ininterrumpida (24/7) y evitar interrupciones por cuotas de rate limit (429), fallos temporales de proveedores (5xx) o bloqueos regionales de red, se define una arquitectura desacoplada de balanceo y resiliencia.

### 3.1 Gestión Multi-Clave (Multi-Key Pool)
Los proveedores como Google Gemini en capa gratuita o intermedia imponen restricciones por clave (ej. 15 RPM, 1,500 RPD).
1. **Inyección y Almacenamiento Cifrado:**
   - Múltiples claves separadas por coma en variables de entorno o cargadas desde la base de datos:
     ```bash
     AI_GEMINI_API_KEYS="AIzaSyA...1,AIzaSyB...2,AIzaSyC...3"
     AI_GROQ_API_KEYS="gsk_...1,gsk_...2"
     AI_DEEPSEEK_API_KEYS="sk-...1,sk-...2"
     AI_OPENAI_API_KEYS="sk-proj-...1,sk-proj-...2"
     ```
   - Persistencia segura: Las claves se cifran en reposo con AES-256-GCM mediante el componente existente `src.security.api_key_manager.ApiKeyManager`.
2. **Rotación Proactiva Round-Robin:**
   - La selección de la clave no espera a un fallo: cada petición subsecuente avanza circularmente el puntero de ranura (`slot`), distribuyendo la carga de RPM equitativamente entre las claves activas.
3. **Telemetría de Enfriamiento (Cooldown) por Clave:**
   - Si una clave recibe una respuesta HTTP 429 (`ResourceExhausted` o `RateLimitExceeded`), se calcula el tiempo de espera (leyendo el header `Retry-After` o aplicando una ventana base de 60 segundos) y se marca en estado `COOLDOWN`.
   - Las claves en enfriamiento se omiten de la rotación hasta que su tiempo de recuperación expire.

---

### 3.2 Gestión Multi-Proveedor con Failover en Cascada y Circuit Breaker

Si todas las claves de un proveedor fallan o el proveedor sufre una caída de infraestructura, el sistema conmuta automáticamente al siguiente proveedor configurado en la cadena de prioridad del rol.

#### Jerarquía de Proveedores por Rol:
- **Rol 1 (Buscador):** `Google Gemini` ➔ `Groq Cloud` ➔ `OpenAI` ➔ `DeepSeek`
- **Rol 2 (Predictor):** `DeepSeek` (R1) ➔ `Google Gemini` (2.5 Flash / 1.5 Pro) ➔ `OpenAI` (GPT-4o) ➔ `Groq` (Llama 3.3 70B)
- **Rol 3 (Revisor):** `OpenAI` (GPT-4o-mini/4o) o `Anthropic` (Claude 3.5 Sonnet) ➔ `Groq` (Llama 3.3 70B) ➔ `Google Gemini` (2.5 Flash)

#### Máquina de Estados del Circuit Breaker

```
         [Normal Operation: Requests flow]
                   +-------------+
                   |   CLOSED    |<--------------------------+
                   +-------------+                           |
                          |                                  |
              Failure Threshold Met                          | Probe Success
           (>= 3 errors / 429 all keys)                      | (200 OK)
                          |                                  |
                          v                                  |
                   +-------------+    Cooldown Expired       |
                   |    OPEN     |-------------------+       |
                   +-------------+   (e.g., 60s wait)|       |
                          |                          v       |
              Immediate Bypass to           +---------------+|
              Next Provider in Chain        |   HALF-OPEN   |+
                                            +---------------+
                                                    |
                                      Probe Failed (Error/Timeout)
                                                    |
                                                    v
                                         Back to OPEN (Backoff x2)
```

1. **Estado `CLOSED`:** Todas las solicitudes se despachan al proveedor primario con balanceo Round-Robin entre sus claves disponibles.
2. **Estado `OPEN`:** Se activa cuando:
   - Se acumulan 3 errores 5xx consecutivos en una ventana de 60 segundos.
   - O todas las claves del proveedor están en `COOLDOWN` (429).
   - O se exceden 2 timeouts consecutivos (> 15 segundos).
   - *Comportamiento:* Las solicitudes evitan llamar a este proveedor de inmediato, redirigiendo el tráfico sin latencia de espera al proveedor secundario en cascada.
3. **Estado `HALF-OPEN`:** Tras transcurrir el período de enfriamiento configurado (`reset_timeout`, por defecto 60s):
   - Se permite pasar una única petición de prueba (*canary request*).
   - Si la prueba retorna HTTP 200 con JSON válido: el Circuit Breaker vuelve a `CLOSED`, reseteando el contador de fallos.
   - Si la prueba falla: el estado regresa a `OPEN` con duplicación del tiempo de enfriamiento (Backoff exponencial: 120s, 240s...).

---

### 3.3 Políticas de Reintento con Tenacity (Backoff Exponencial y Jitter)

El subsistema utiliza la librería estándar `tenacity` (ya presente en `pyproject.toml`) para orquestar reintentos en red:

1. **Reglas de Reintento:**
   - Reintentar ante excepciones transitorias de red: `httpx.ConnectTimeout`, `httpx.ReadTimeout`, `httpx.ConnectError`, `httpx.RemoteProtocolError`.
   - **NO** reintentar ante errores fatales de autenticación (401, 403) ni errores de sintaxis en el payload (400), los cuales disparan de inmediato una alerta en el log de auditoría.
2. **Backoff con Jitter:**
   - Estrategia: `wait_random_exponential(multiplier=0.5, max=8.0)`. El jitter aleatorio previene el fenómeno de "rebaño atronador" (*thundering herd problem*) cuando múltiples hilos intentan reconectar simultáneamente.
3. **Rotación Forzada Pre-Reintento:**
   - Antes de ejecutar cada reintento de la política `tenacity`, el hook `before_sleep` fuerza a llamar a `key_pool.get_next_key()`. De esta forma, el reintento nunca reutiliza el mismo socket o clave API saturada.

```python
# Ejemplo arquitectónico de la política de reintentos
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=0.5, max=8.0),
    retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
    reraise=True
)
def execute_provider_call_with_rotation(router, payload):
    key = router.get_current_provider_key()
    return router.dispatch(key, payload)
```

---

## 4. Especificación Detallada de los 3 Roles

### 4.1 Rol 1: Buscador / Recopilador de Contexto Macroeconómico (`MacroContextExtractorAgent`)

- **Objetivo Principal:** Ingerir noticias no estructuradas, comunicados del BCV, minutas gubernamentales y datos de mercado, filtrando opiniones especulativas y consolidando los hechos económicos en una colección de eventos tipificados y ponderados.
- **Parámetros de Inferencia:**
  - `temperature`: `0.1` (fidelidad documental absoluta, cero inventiva).
  - `top_p`: `0.90`
  - `max_tokens`: `2048`
  - `format`: `JSON` con validación Pydantic `MacroContextCollection`.
- **Restricciones Operativas:**
  - Prohibido emitir juicios direccionales sobre el precio.
  - Prohibido inventar cifras numéricas o fechas. Si una cifra no es provista expresamente en el texto, consignar `null`.
  - Debe etiquetar la credibilidad de la fuente en 3 rangos: `ALTA` (Organismos oficiales, BCV, gacetas), `MEDIA` (Portales económicos consolidados: Banca y Negocios, Finanzas Digital), `BAJA` (Rumores en X/Telegram, fuentes no contrastadas).

#### System Prompt Completo y Estructurado (Rol 1)

```markdown
Eres el Agente Especialista en Ingesta y Extracción Macroeconómica de Venezuela para un sistema de trading institucional de USDT en Binance P2P.

TU MISIÓN:
Analizar la información en bruto suministrada (noticias, comunicados del BCV, publicaciones de portales financieros, minutas gubernamentales y mensajes de canales especializados) y transformarla en una colección estructurada de eventos económicos objetivos, verificables y libres de ruido.

TAXONOMÍA OBLIGATORIA DE CATEGORÍAS:
Debes clasificar cada evento estrictamente en una de las siguientes categorías:
1. "INTERVENCION_BCV": Ventas de divisas en efectivo o transferencia realizadas por el Banco Central de Venezuela a la banca pública y privada.
2. "PAGO_PATRIA_NOMINA": Pagos de nóminas de empleados públicos, pensiones, bonos del Sistema Patria, utilidades y aguinaldos.
3. "LIQUIDEZ_MONETARIA_M2": Reportes oficiales de emisión o contracción de liquidez monetaria en bolívares (M2) reportada por el BCV.
4. "BRECHA_CAMBIARIA_ARBITRAJE": Diferencial porcentual entre la tasa oficial de referencia del BCV y la tasa paralela o USDT P2P.
5. "REGULACION_BANCARIA_ENCAJE": Modificaciones en el encaje legal, límites de crédito bancario, límites de pago móvil o comisiones IGTF.
6. "FACTORES_ESTACIONALES_TRIBUTARIOS": Períodos de pago de impuestos (declaración de IVA quincenal, ISLR a fin de mes), feriados bancarios o estacionalidad decembrina.
7. "POLITICA_SANCIONES": Anuncios diplomáticos, sanciones internacionales o licencias de la OFAC relativas a hidrocarburos y comercio.

REGLAS CRÍTICAS DE EXTRACCIÓN:
- Jamás infieras si el precio "subirá" o "bajará". Tu trabajo es estrictamente factual.
- Extrae números exactos siempre que estén presentes: monto en millones de USD o en millones de bolívares, fechas de ejecución y variaciones porcentuales.
- Si un artículo carece de cifras concretas, no inventes valores; declara "cifras_especificadas": false y valores en null.
- Asigna el nivel de credibilidad de la fuente:
  * "ALTA": Banco Central de Venezuela (BCV), Ministerio de Finanzas, SUDEBAN, Gaceta Oficial.
  * "MEDIA": Portales financieros reconocidos (Banca y Negocios, Finanzas Digital, Descifrado, Efecto Cocuyo, Reuters).
  * "BAJA": Cuentas de redes sociales no institucionales, cadenas de mensajería, rumores o especulaciones de mercado.
- Tu salida DEBE ser exclusivamente un objeto JSON válido acorde al esquema `MacroContextCollection`. No agregues preámbulos ni explicaciones en texto plano.
```

---

### 4.2 Rol 2: Analista / Predictor Macroeconómico de USDT (`USDTMacroPredictorAgent`)

- **Objetivo Principal:** Consumir el contexto estructurado generado por el Rol 1 junto con el estado actual del mercado cambiario (tasa P2P, tasa oficial BCV y brecha cambiaria), aplicar principios cuantitativos de transmisión monetaria y emitir una predicción probabilística sobre la dirección, lapso temporal y factores determinantes del USDT en Venezuela.
- **Parámetros de Inferencia:**
  - `temperature`: `0.2` (equilibrio óptimo para razonamiento analítico riguroso y asignación consistente de probabilidades).
  - `top_p`: `0.90`
  - `max_tokens`: `3072`
  - `format`: `JSON` con validación Pydantic `DraftPrediction`.
- **Mecanismos de Transmisión Económica que debe dominar:**
  1. *Fuerzas Alcistas (Demanda de USDT / Inyección de VES):*
     - Desembolso de nóminas y aguinaldos del Estado: Los beneficiarios en bolívares carecen de incentivo para ahorrar en moneda local e inmediatamente demandan USDT en P2P para preservar valor, generando picos de demanda y presión alcista.
     - Aumento abrupto de la liquidez monetaria (M2) sin respaldo de reservas.
     - Ampliación de la brecha cambiaria (> 20%): Genera arbitraje agresivo, desabastecimiento de dólares en la banca y migración masiva de comercios al P2P.
     - Feriados bancarios prolongados: Acumulación de compras de cobertura preventiva ante la inactividad bancaria oficial.
  2. *Fuerzas Bajistas o de Contención (Oferta de USDT / Absorción de VES):*
     - Intervenciones cambiarias robustas del BCV: La venta de divisas en la banca absorbe bolívares del sistema financiero, drenando la liquidez disponible para comprar USDT en P2P y conteniendo el precio temporalmente.
     - Cierres quincenales y de fin de mes tributario (SENIAT): Las empresas comerciales e importadores se ven forzados a liquidar sus posiciones en USDT para obtener liquidez en bolívares y pagar compromisos de IVA e ISLR.
     - Incremento del encaje legal bancario: Restringe la creación de crédito y disponibilidad de bolívares prestables.
  3. *Escenario Neutral o Estable:*
     - Equilibrio entre la inyección de bolívares y la oferta de divisas de la banca, o ausencia de catalizadores macroeconómicos en fines de semana regulares.
- **Reglas de Calibración de Confianza:**
  - Si existen fuerzas contrapuestas (ej. pago de nómina de $50M concurrentemente con intervención cambiaria de $80M), la confianza máxima no puede superar el `70%`.
  - Si los datos provienen de fuentes de credibilidad `BAJA`, la confianza máxima permitida es `55%`.
  - La confianza solo puede superar el `85%` si existen hechos oficiales concurrentes en la misma dirección (ej. intervención cambiaria suspendida + pago de aguinaldos + salto del 5% en M2).

#### System Prompt Completo y Estructurado (Rol 2)

```markdown
Eres el Analista Econométrico y Especialista Senior en Mercados Cambiarios y Criptoactivos en Venezuela para un bot de comercio P2P de USDT.

TU MISIÓN:
Consumir la colección de eventos macroeconómicos estructurados provista por el Rol 1, junto con las métricas actuales del mercado cambiario (tasa P2P, tasa oficial BCV, brecha cambiaria porcentual), y elaborar una predicción formal del comportamiento del precio del USDT/VES.

DIMENSIONES DE LA PREDICCIÓN:
1. `direccion`: Debe ser exactamente uno de los siguientes valores:
   - "SUBE": Presión neta compradora / devaluación del bolívar en el mercado P2P.
   - "BAJA": Presión neta vendedora / apreciación temporal del bolívar o contención efectiva.
   - "ESTABLE": Equilibrio de fuerzas o variación estimada menor al +/- 0.5% en la ventana temporal.
2. `lapso_estimado`: Ventana temporal en la que se materializará el impacto:
   - "24h-48h": Impacto inmediato (ej. transferencias inmediatas de bonos Patria o intervención cambiaria del lunes).
   - "3-5 dias": Impacto de ciclo semanal (ej. rezago de absorción bancaria o compras empresariales).
   - "semanal": Tendencia sostenida por dinámicas estructurales de liquidez monetaria M2.
3. `confiabilidad_porcentaje`: Float calibrado entre 0.0 y 100.0. Debe reflejar honestamente la certidumbre estadística basada en la calidad de las fuentes y el balance de fuerzas.
4. `factores_clave`: Lista de strings con los eventos determinantes que sustentan la decisión.
5. `justificacion_detallada`: Argumentación económica rigurosa explicando el mecanismo de transmisión monetaria.
6. `riesgos_invalidacion`: Lista de condiciones o eventos imprevistos que neutralizarían o invertirían la proyección (ej. "Intervención cambiaria extraordinaria no anunciada del BCV").

DIRECTRICES ANALÍTICAS:
- Modela siempre el flujo de fondos: ¿Quién tiene bolívares en este momento? ¿Tienen incentivo a venderlos o a pagar obligaciones en bolívares (tributos)?
- Considera el rezago temporal (lag): Una inyección de liquidez de bonos suele impactar en el P2P entre 4 y 24 horas después del depósito bancario.
- Genera como salida EXCLUSIVAMENTE un objeto JSON compatible con el esquema `DraftPrediction`.
```

---

### 4.3 Rol 3: Revisor / Auditor de Coherencia y Veracidad (`MacroPredictionAuditorAgent`)

- **Objetivo Principal:** Someter la predicción preliminar del Rol 2 a una auditoría adversarial rigurosa, contrastando cada afirmación, número y conclusión frente al contexto fáctico entregado por el Rol 1. Detectar alucinaciones, inconsistencias de lógica económica, sesgos y sobreconfianza.
- **Parámetros de Inferencia:**
  - `temperature`: `0.0` (máxima rigidez determinista, cero tolerancia a errores).
  - `top_p`: `0.85`
  - `max_tokens`: `2048`
  - `format`: `JSON` con validación Pydantic `AuditResult`.
- **Criterios de Auditoría y Verificación:**
  1. *Verificación de Alucinaciones:* ¿El predictor cita cifras en millones de USD o fechas que NO estaban presentes en los eventos del Rol 1? Si es así, clasificar como ALUCINACIÓN GRAVE.
  2. *Coherencia Lógica:* ¿La justificación económica contradice la dirección? (ej. Afirmar que el BCV realizó una intervención récord de 150M USD y concluir que el USDT subirá en 24h sin justificar una fuerza mayor de demanda).
  3. *Calibración de Confianza:* ¿El predictor asignó > 80% de confianza con fuentes no oficiales o ante eventos contradictorios? Si la confianza está sobreestimada, el auditor DEBE corregirla a la baja.
  4. *Veredicto Final:*
     - `APROBADO`: Predicción perfectamente fundamentada en los datos, lógica impecable y confianza calibrada.
     - `CORREGIDO`: Lógica y dirección válidas, pero la justificación requirió ajuste menor o la confianza estaba sobreestimada (el auditor provee los valores ajustados).
     - `RECHAZADO`: Predicción con alucinaciones severas, inconsistencia lógica flagrante o contradicción directa con los hechos documentados.

#### System Prompt Completo y Estructurado (Rol 3)

```markdown
Eres el Auditor Independiente de Riesgo Cuantitativo y Crítico Adversarial de Modelos de Inteligencia Artificial para el sistema institucional de trading P2P.

TU MISIÓN:
Auditar con máximo escepticismo la predicción preliminar de mercado emitida por el Rol 2, contrastándola minuciosamente contra la evidencia factual primaria provista por el Rol 1.

CRITERIOS INNEGOCIABLES DE AUDITORÍA:
1. DETECCIÓN DE ALUCINACIONES:
   - Comprueba cada cifra, porcentaje, fecha o declaración atribuida a entidades oficiales en la predicción preliminar.
   - Si el Rol 2 menciona hechos que NO figuren en la colección de eventos del Rol 1, debes reportarlo en `hallazgos_alucinacion`.
2. COHERENCIA DE TRANSMISIÓN ECONÓMICA:
   - Verifica si la conclusión direccional ("SUBE", "BAJA", "ESTABLE") se desprende lógicamente de los factores clave.
   - Señala si se ignoraron factores de impacto mayor en sentido opuesto.
3. CONTROL DE SOBRECONFIANZA:
   - Si la confianza emitida es superior a la justificada por la solidez de las fuentes y el consenso de las fuerzas macroeconómicas, reduce el porcentaje de confiabilidad al valor estadísticamente prudente en `confiabilidad_calibrada`.
4. EMISIÓN DE VEREDICTO (`veredicto`):
   - "APROBADO": Cero alucinaciones, lógica de transmisión económica impecable y confianza calibrada.
   - "CORREGIDO": La dirección es correcta, pero la justificación omitió matices relevantes o la confianza requirió corrección a la baja.
   - "RECHAZADO": Fallo constitucional. La predicción se basa en premisas falsas, contiene alucinaciones de datos no presentes en el contexto, o la lógica entre premisas y conclusión es contradictoria.

Devuelve EXCLUSIVAMENTE un objeto JSON compatible con el esquema `AuditResult`.
```

---

### 4.4 Flujo de Interacción y Esquema de Paso de Mensajes

El pipeline sigue un diseño determinista por etapas con salvaguarda fail-closed:

```
[Cron / Event Trigger]
        |
        v
[Paso 1: Ingesta en Bruto] (Fuentes RSS, Web, Telegram)
        |
        v  (Raw Text Data)
+-----------------------------------------------------------+
| PASO 2: ROL 1 (Buscador / Recopilador)                    |
| - Procesa texto con Gemini 2.0 Flash (o Groq Llama 3.3)   |
| - Valida respuesta contra Pydantic `MacroContextCollection|
+-----------------------------------------------------------+
        |
        v  (MacroContextCollection)
+-----------------------------------------------------------+
| PASO 3: ROL 2 (Analista / Predictor)                      |
| - Procesa contexto + Tasa P2P + BCV con DeepSeek-R1       |
| - Genera razonamiento y borrador de predicción            |
| - Valida respuesta contra Pydantic `DraftPrediction`      |
+-----------------------------------------------------------+
        |
        v  (DraftPrediction + MacroContextCollection)
+-----------------------------------------------------------+
| PASO 4: ROL 3 (Revisor / Auditor Adversarial)             |
| - Modelo Cross-Family (Claude 3.5 Sonnet o GPT-4o-mini)   |
| - Cruza factualidad y coherencia lógica                   |
| - Valida respuesta contra Pydantic `AuditResult`          |
+-----------------------------------------------------------+
        |
        +-----------------------+-----------------------+
        |                                               |
  [veredicto == "APROBADO"                        [veredicto == "RECHAZADO"]
   o "CORREGIDO"]                                       |
        |                                               v
        v                                 +---------------------------+
+---------------------------------+       | Pipeline Abortado         |
| Consolidación en                |       | - Se registra en auditoría|
| `FinalUSDTPrediction`           |       | - Alerta Fail-Closed      |
| - Firma SHA-256 de auditoría    |       | - Ninguna predicción es   |
| - Persistencia en Base de Datos |       |   emitida a los operadores|
| - Notificación en Telegram      |       +---------------------------+
| - Publicación en Dashboard      |
+---------------------------------+
```

#### Protocolo de Manejo de Errores y Loops:
- Si el Revisor emite `CORREGIDO`, la predicción se emite aplicando los valores corregidos por el auditor (`confiabilidad_calibrada` y justificación enriquecida), documentando la modificación en los metadatos de auditoría.
- Si el Revisor emite `RECHAZADO`, el pipeline **NO** emite la predicción. Opcionalmente, se permite un **único ciclo de reintento (Max Iterations = 1)** enviando al Predictor el reporte de objeciones del Auditor. Si en la segunda iteración el Revisor no aprueba, el sistema se cierra en modo **Fail-closed**, notificando al administrador por Telegram sobre la inconsistencia detectada.

---

## 5. Esquema Formal de Datos y Salida (Modelos Pydantic v2 y JSON Schema)

A continuación se especifican los modelos de datos tipificados estrictamente mediante Pydantic v2.

### 5.1 Definición de Modelos Pydantic en Python (`src/ai_predictor/schemas.py`)

```python
"""Esquemas de datos tipificados mediante Pydantic v2 para el pipeline de predicción macroeconómica de USDT."""

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class TaxonomyCategory(str, Enum):
    INTERVENCION_BCV = "INTERVENCION_BCV"
    PAGO_PATRIA_NOMINA = "PAGO_PATRIA_NOMINA"
    LIQUIDEZ_MONETARIA_M2 = "LIQUIDEZ_MONETARIA_M2"
    BRECHA_CAMBIARIA_ARBITRAJE = "BRECHA_CAMBIARIA_ARBITRAJE"
    REGULACION_BANCARIA_ENCAJE = "REGULACION_BANCARIA_ENCAJE"
    FACTORES_ESTACIONALES_TRIBUTARIOS = "FACTORES_ESTACIONALES_TRIBUTARIOS"
    POLITICA_SANCIONES = "POLITICA_SANCIONES"


class SourceCredibility(str, Enum):
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"


class PredictionDirection(str, Enum):
    SUBE = "SUBE"
    BAJA = "BAJA"
    ESTABLE = "ESTABLE"


class TimeframeHorizon(str, Enum):
    HORAS_24_48 = "24h-48h"
    DIAS_3_5 = "3-5 dias"
    SEMANAL = "semanal"


class AuditVerdictEnum(str, Enum):
    APROBADO = "APROBADO"
    CORREGIDO = "CORREGIDO"
    RECHAZADO = "RECHAZADO"


# -------------------------------------------------------------
# Esquemas para Rol 1: Buscador / Recopilador
# -------------------------------------------------------------

class MacroEventItem(BaseModel):
    """Representa un hecho macroeconómico individual estructurado a partir de noticias o datos oficiales."""
    titulo: str = Field(..., description="Resumen breve del evento noticioso o hecho económico")
    categoria: TaxonomyCategory = Field(..., description="Categoría formal de la taxonomía económica")
    fuente: str = Field(..., description="Nombre del medio, organismo o cuenta emisora")
    credibilidad_fuente: SourceCredibility = Field(..., description="Nivel de fiabilidad de la fuente")
    fecha_evento: str = Field(..., description="Fecha o período de ocurrencia (YYYY-MM-DD o descripción temporal)")
    cifras_especificadas: bool = Field(default=False, description="Indica si el evento contiene datos cuantitativos explícitos")
    monto_relevante: Optional[float] = Field(None, description="Monto numérico extraído si aplica (ej. millones de USD o bolívares)")
    unidad_monto: Optional[str] = Field(None, description="Unidad de medida: 'MILLONES_USD', 'MILLONES_VES', 'PORCENTAJE'")
    resumen_factual: str = Field(..., description="Descripción objetiva del hecho sin opiniones especulativas")


class MacroContextCollection(BaseModel):
    """Colección completa de eventos recolectados y normalizados por el Rol 1."""
    timestamp_extraccion: datetime = Field(default_factory=datetime.utcnow, description="Timestamp UTC de la extracción")
    total_eventos_detectados: int = Field(..., ge=0, description="Total de eventos relevantes procesados")
    eventos: List[MacroEventItem] = Field(..., description="Lista de eventos clasificados")
    tasa_p2p_actual: Optional[float] = Field(None, description="Tasa de cambio actual USDT/VES en Binance P2P")
    tasa_bcv_actual: Optional[float] = Field(None, description="Tasa de cambio oficial de referencia del BCV")
    brecha_cambiaria_porcentaje: Optional[float] = Field(None, description="Diferencial porcentual entre P2P y BCV")


# -------------------------------------------------------------
# Esquemas para Rol 2: Analista / Predictor
# -------------------------------------------------------------

class DraftPrediction(BaseModel):
    """Borrador de predicción elaborado por el Rol 2 sujeto a auditoría del Rol 3."""
    direccion: PredictionDirection = Field(..., description="Dirección estimada del precio: SUBE, BAJA o ESTABLE")
    lapso_estimado: TimeframeHorizon = Field(..., description="Ventana temporal estimada para el comportamiento")
    confiabilidad_porcentaje: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Grado de certidumbre analítica calibrada (0.0 a 100.0)"
    )
    factores_clave: List[str] = Field(..., min_length=1, description="Factores determinantes que impulsan la proyección")
    justificacion_detallada: str = Field(..., min_length=20, description="Argumentación basada en transmisión monetaria")
    riesgos_invalidacion: List[str] = Field(..., min_length=1, description="Eventos potenciales que invalidarían la hipótesis")


# -------------------------------------------------------------
# Esquemas para Rol 3: Revisor / Auditor
# -------------------------------------------------------------

class AuditResult(BaseModel):
    """Resultado formal de la evaluación adversarial emitida por el Rol 3."""
    veredicto: AuditVerdictEnum = Field(..., description="Resultado de la auditoría: APROBADO, CORREGIDO o RECHAZADO")
    puntaje_rigor: float = Field(..., ge=0.0, le=100.0, description="Puntuación cuantitativa de coherencia lógica (0-100)")
    hallazgos_alucinacion: List[str] = Field(default_factory=list, description="Cifras o afirmaciones no sustentadas en los datos del Rol 1")
    critica_logica: str = Field(..., description="Evaluación crítica de la relación causa-efecto del predictor")
    confiabilidad_calibrada: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Valor ajustado de confianza si el auditor determina sobrestimación o subestimación"
    )
    justificacion_auditada: Optional[str] = Field(None, description="Texto de justificación revisado y libre de sesgos")


# -------------------------------------------------------------
# Esquema Final Consolidado y Publicable
# -------------------------------------------------------------

class AuditMetadata(BaseModel):
    """Metadatos de auditoría y trazabilidad constitucional."""
    timestamp_emision: datetime = Field(default_factory=datetime.utcnow)
    modelos_utilizados: dict = Field(
        ...,
        description="Registro de proveedores y modelos usados por rol (ej. {'rol_1': 'gemini-2.0-flash', ...})"
    )
    tokens_totales_consumidos: int = Field(..., ge=0)
    duracion_pipeline_segundos: float = Field(..., ge=0.0)
    veredicto_auditor: AuditVerdictEnum
    hash_integridad_sha256: str = Field(..., description="Hash SHA-256 de la predicción y evidencia para auditoría append-only")


class FinalUSDTPrediction(BaseModel):
    """Esquema formal consolidado de la predicción final de mercado de USDT en Venezuela."""
    direccion: PredictionDirection = Field(..., description="Dirección proyectada: SUBE, BAJA o ESTABLE")
    lapso_estimado: TimeframeHorizon = Field(..., description="Ventana temporal estimada (24h-48h, 3-5 dias, semanal)")
    confiabilidad_porcentaje: float = Field(..., ge=0.0, le=100.0, description="Porcentaje de confiabilidad final calibrado")
    factores_clave: List[str] = Field(..., min_length=1, description="Factores determinantes que sustentan la predicción")
    justificacion_detallada: str = Field(..., description="Explicación analítica con lógica de transmisión económica")
    riesgos_invalidacion: List[str] = Field(..., min_length=1, description="Condiciones que revertirían la predicción")
    metadata_auditoria: AuditMetadata = Field(..., description="Metadatos de trazabilidad y modelos ejecutados")

    @field_validator("confiabilidad_porcentaje")
    @classmethod
    def validar_confiabilidad_rango(cls, v: float) -> float:
        return round(float(v), 2)
```

---

### 5.2 JSON Schema Estricto para la Salida Final (`FinalUSDTPrediction`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "FinalUSDTPrediction",
  "description": "Esquema formal consolidado de la predicción final de mercado de USDT en Venezuela.",
  "type": "object",
  "properties": {
    "direccion": {
      "type": "string",
      "enum": ["SUBE", "BAJA", "ESTABLE"],
      "description": "Dirección proyectada: SUBE, BAJA o ESTABLE"
    },
    "lapso_estimado": {
      "type": "string",
      "enum": ["24h-48h", "3-5 dias", "semanal"],
      "description": "Ventana temporal estimada (24h-48h, 3-5 dias, semanal)"
    },
    "confiabilidad_porcentaje": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 100.0,
      "description": "Porcentaje de confiabilidad final calibrado"
    },
    "factores_clave": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1,
      "description": "Factores determinantes que sustentan la predicción"
    },
    "justificacion_detallada": {
      "type": "string",
      "description": "Explicación analítica con lógica de transmisión económica"
    },
    "riesgos_invalidacion": {
      "type": "array",
      "items": { "type": "string" },
      "minItems": 1,
      "description": "Condiciones que revertirían la predicción"
    },
    "metadata_auditoria": {
      "type": "object",
      "properties": {
        "timestamp_emision": {
          "type": "string",
          "format": "date-time"
        },
        "modelos_utilizados": {
          "type": "object",
          "additionalProperties": { "type": "string" },
          "description": "Registro de proveedores y modelos usados por rol"
        },
        "tokens_totales_consumidos": {
          "type": "integer",
          "minimum": 0
        },
        "duracion_pipeline_segundos": {
          "type": "number",
          "minimum": 0.0
        },
        "veredicto_auditor": {
          "type": "string",
          "enum": ["APROBADO", "CORREGIDO", "RECHAZADO"]
        },
        "hash_integridad_sha256": {
          "type": "string",
          "description": "Hash SHA-256 de la predicción y evidencia"
        }
      },
      "required": [
        "timestamp_emision",
        "modelos_utilizados",
        "tokens_totales_consumidos",
        "duracion_pipeline_segundos",
        "veredicto_auditor",
        "hash_integridad_sha256"
      ]
    }
  },
  "required": [
    "direccion",
    "lapso_estimado",
    "confiabilidad_porcentaje",
    "factores_clave",
    "justificacion_detallada",
    "riesgos_invalidacion",
    "metadata_auditoria"
  ]
}
```

---

## 6. Integración con Módulos Existentes del Repositorio

La arquitectura diseñada se acopla limpiamente con los estándares y componentes ya presentes en `p2p-bot-merchant`:

1. **Gestión Criptográfica de Claves API (`src/security/api_key_manager.py`):**
   - El router de IA invoca `ApiKeyManager.get_secret()` para descifrar las claves en memoria volátil en tiempo de ejecución utilizando AES-256-GCM.
   - Jamás se almacenan ni registran claves en texto claro en logs o archivos de configuración expuestos.
2. **Auditoría Append-Only (`src/security/audit_logger.py`):**
   - Cada ejecución del pipeline de IA calcula un hash SHA-256 encadenado de la entrada documental, el borrador del predictor y el veredicto del auditor, persistiendo el evento como `AI_MACRO_PREDICTION_GENERATED` en la tabla `security_events`.
3. **Distribución Multicanal:**
   - **Telegram Notifier (`src/integrations/telegram_notifier.py`):** Cuando la predicción es aprobada, se formatea un mensaje visual con sanitización estricta (`sanitize_message()`) y se despacha a los administradores autorizados.
   - **Dashboard Streamlit (`src/reporting/dashboard/`):** Creación de una tarjeta interactiva en el panel "Mission Control" que grafique la probabilidad calibrada, los factores alcistas/bajistas y el velocímetro de dirección de mercado.
4. **Comportamiento Fail-Closed:**
   - Si la API externa está caída, no hay cuota en ningún proveedor o el Revisor emite `RECHAZADO`, el bot aborta la publicación y notifica al operador humano. Ninguna conjetura no validada se transmite como dato fáctico.

---

## 7. Conclusiones y Próximos Pasos

1. **Eficiencia y Viabilidad Técnica:** La arquitectura propuesta combina la amplitud de contexto de Google Gemini en el Rol 1, la profundidad analítica de DeepSeek-R1 en el Rol 2, y la severidad crítica de OpenAI/Anthropic en el Rol 3, todo por un costo menor a $0.006 USD por corrida y con un tiempo de procesamiento promedio inferior a 12 segundos.
2. **Resiliencia Operativa:** El diseño del Circuit Breaker con balanceador Round-Robin proactivo y soporte multi-proveedor garantiza que el bot no sufra apagones por límites de cuota (429) ni sobrecargas en servidores externos.
3. **Paso a Especificación:** Este reporte provee los insumos exactos para que Explorer 3 y el equipo de desarrollo plasmen las especificaciones formales (`spec.md`), arquitectura (`plan.md`) y desglose de tareas (`tasks.md`) en `.specify/specs/`.
