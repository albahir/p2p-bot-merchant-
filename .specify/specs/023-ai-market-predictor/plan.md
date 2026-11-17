# PLAN-023: Plan de Arquitectura y Diseño Técnico para el Predictor de Mercado con IA

**Plan de Arquitectura y Especificación de Diseño Técnico (SDD)**  
**Paquete:** `023-ai-market-predictor`  
**Estado:** DRAFT — APROBADO PARA IMPLEMENTACIÓN  
**Fecha:** 17 de Noviembre de 2026  
**Autor:** Architecture & SDD Team  
**Especificación Base:** `SPEC-023`, `docs/macro_usdt_taxonomy.md`  

---

## 1. Stack Tecnológico y Dependencias

El subsistema `023-ai-market-predictor` se construirá sobre el stack técnico estándar de la plataforma `p2p-bot-merchant`:

* **Entorno y Lenguaje:** Python 3.12+ / Python 3.13 en contenedor Docker / entorno virtual `.venv`.
* **Validación de Datos y Contratos Fuertes:** `pydantic` v2.7+ (`BaseModel`, `Field`, `field_validator`, `Enum`).
* **Resiliencia, Reintentos y Backoff:** `tenacity` (`retry`, `stop_after_attempt`, `wait_random_exponential`, rotación de claves en `before_sleep`).
* **Clientes de Red Asíncronos / Síncronos:** `httpx` (connection pooling, timeouts estrictos, soporte SSL personalizado).
* **Ingesta y Web Scraping:** `feedparser` (procesamiento estructurado de feeds RSS de portales financieros) y `beautifulsoup4` (parseo defensivo de tablas HTML del BCV).
* **Conectividad de LLMs:** Conectores REST modulares y SDKs oficiales:
  - Google Gemini API (`google-genai` / REST con soporte de Structured Outputs y `thinking_budget`).
  - Groq Cloud API (`groq` / REST OpenAI-compatible, Llama 3.3 70B de ultra-baja latencia).
  - DeepSeek API (REST OpenAI-compatible con extracción nativa de bloques `<think>`).
  - OpenAI API (`openai` SDK / REST con Strict Structured Outputs).
  - Anthropic API (`anthropic` SDK / REST con Tool use).
* **Criptografía y Seguridad:** `cryptography` (cifrado simétrico AES-256-GCM para llaves en reposo) y `hashlib` (encadenamiento criptográfico SHA-256).
* **Persistencia Relacional:** `sqlalchemy` 2.0+ (compatible con SQLite local y PostgreSQL/Neon en staging y producción).

---

## 2. Arquitectura del Sistema y Layout de Módulos

El diseño respeta el principio de separación estricta de responsabilidades, ubicando la lógica de inteligencia macroeconómica dentro de un subpaquete dedicado bajo `src/core/`:

```
src/core/macro/
├── __init__.py                     # Interfaz pública del subsistema macro
├── schemas.py                      # Modelos Pydantic v2 (MacroContextCollection, FinalUSDTPrediction, etc.)
├── taxonomy.py                     # Constantes canónicas y diccionario de 14 eventos macroeconómicos
├── collector.py                    # MacroNewsCollector: Ingesta RSS, web scraping y polling
├── normalizer.py                   # MacroNormalizer: Limpieza tipográfica y filtrado anti-ruido
├── llm_engine.py                   # MultiProviderAIEngine, AIKeyPool y CircuitBreaker
├── prompts.py                      # System Prompts verbatim para los 3 roles del pipeline
├── analyst.py                      # Rol 2: MacroAnalystPredictor (deducción causal monetaria)
├── auditor.py                      # Rol 3: MacroPredictionAuditor (revisión adversarial independiente)
├── quota_monitor.py                # Telemetría de latencias, tokens y costos por proveedor
└── pipeline.py                     # Orquestador del flujo: Collector -> Rol 1 -> Rol 2 -> Rol 3 -> Repository

src/data/
├── models.py                       # Incorporación de tablas MacroEventModel y MacroPredictionModel
└── repositories.py                 # MacroRepository: Inserción idempotente y consultas históricas

src/integrations/
├── ai_assistant.py                 # Tool 'consultar_prediccion_mercado' y comando /prediccion
└── telegram_notifier.py            # Método send_macro_prediction_alert() sanitizado

src/reporting/dashboard/components/
└── macro_intelligence.py           # Componente visual para Streamlit (Mission Control)

tests/unit/
├── test_macro_schemas.py           # Validación unitaria de contratos Pydantic v2
├── test_macro_collector.py         # Mocks de ingesta RSS y scraping de noticias
├── test_multi_provider_pool.py     # Pruebas de Round-Robin, cooldown y failover
├── test_macro_pipeline.py          # Pruebas del pipeline de 3 roles con mocks de LLMs
└── test_macro_auditor.py           # Pruebas de compuerta adversarial y veto de alucinaciones
```

---

## 3. Desglose de Componentes Principales

### 3.1 `MacroNewsCollector` y `MacroNormalizer`
* **Misión:** Extraer noticias y eventos macroeconómicos desde feeds RSS de portales financieros (`Banca y Negocios`, `Finanzas Digital`), tablas del portal del BCV y calendarios del SENIAT.
* **Manejo Defensivo:** Elimina etiquetas HTML, caracteres especiales de codificación mixta, normaliza fechas al huso horario UTC y descarta entradas duplicadas o sin fuente verificable.

### 3.2 `MultiProviderPool` & `RoundRobinEngine`
* **Misión:** Gestionar las API Keys asignadas a cada proveedor de inteligencia artificial, manteniendo punteros de rotación circular atómicos protegidos con `threading.Lock`.
* **Control de Cooldown:** Ante un código HTTP 429, extrae la cabecera `retry-after` (o asigna 60 segundos por defecto) y aísla temporalmente la clave sin degradar las demás.

### 3.3 `CircuitBreaker`
* **Misión:** Supervisar la disponibilidad de los proveedores de LLM.
* **Estados:**
  - `CLOSED`: Operación normal.
  - `OPEN`: Tras 3 fallos consecutivos o indisponibilidad masiva de cuota, el proveedor se inhabilita por una ventana de enfriamiento y las peticiones conmutan automáticamente al siguiente proveedor de la cadena en cascada.
  - `HALF-OPEN`: Permite una petición de sondeo tras expirar la ventana; si es exitosa, restablece a `CLOSED`.

### 3.4 `USDTPredictor` (`MacroAnalystPredictor`)
* **Misión:** Ejecutar el Rol 2. Procesa el `MacroContextPayload` estructurado, computa la resultante macroeconómica de fuerzas vectoriales $F_{\text{net}}(t) = \sum F_i(t)$ y emite el borrador calibrado `DraftPrediction`.
* **Motor Matemático Vectorial y Activación con Floor Defensivo:**
  La fuerza efectiva instantánea de cada evento $i$ se calcula como:
  $$F_i(t) = d_i \cdot w_i \cdot c_i \cdot \alpha_i(\Delta t_i) \cdot D_i(\Delta t_i)$$
  Donde:
  - $\alpha_i(\Delta t_i) = \max(0.0, \Delta t_i / L_i)$ para $\Delta t_i < L_i$ con $L_i > 0$, garantizando cota cero para eventos futuros ($\Delta t_i \le 0$) para erradicar cualquier inversión de signo.
  - $D_i(\Delta t_i) = \exp\left( -\frac{\ln(2)}{h_i} \cdot \max(0, \Delta t_i - L_i) \right)$ modela el enfriamiento exponencial posterior a la absorción.
  - El software implementa la función determinista `calc_activation(dt: float, latency: float) -> float`:
    ```python
    def calc_activation(dt: float, latency: float) -> float:
        if latency > 0.0 and dt < latency:
            return max(0.0, dt / latency)
        if dt < 0.0:
            return 0.0
        return 1.0
    ```

### 3.5 `PredictionAuditor` (`MacroPredictionAuditor`)
* **Misión:** Ejecutar el Rol 3 bajo el mandato innegociable de **Verificación Cruzada entre Familias de Modelos (Cross-Family Model Verification)**. Audita factualidad, veta alucinaciones y emite veredicto formal (`APROBADO`, `CORREGIDO`, `RECHAZADO`).

---

## 4. Comparativa Técnica y Económica de Modelos LLM

| Proveedor | Modelo | Ventana de Contexto | Latencia (TTFT / TPS) | Input Cost ($/1M) | Output Cost ($/1M) | Razonamiento Económico | Idoneidad en el Pipeline |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Google** | **Gemini 2.5 Flash** | 1,048,576 | ~350ms / 140 tps | $0.15 | $0.60 | Alta (con Thinking) | **Rol 1 (Primario)** / Rol 2 |
| **Google** | **Gemini 2.0 Flash** | 1,048,576 | ~300ms / 160 tps | $0.10 | $0.40 | Media-Alta | **Rol 1 (Primario Económico)** |
| **Groq** | **Llama 3.3 70B** | 128,000 | ~150ms / 280 tps | $0.59 | $0.79 | Alta | **Rol 1 (Respaldo ultra-rápido)** |
| **DeepSeek** | **DeepSeek-R1 (CoT)**| 64,000 / 128k | ~1500ms / 40 tps | $0.55 (cache $0.14)| $2.19 | **Excepcional (CoT Nativo)** | **Rol 2 (Primario)** |
| **OpenAI** | **GPT-4o-mini** | 128,000 | ~450ms / 95 tps | $0.15 | $0.60 | Media-Alta | **Rol 3 (Auditor Económico)** |
| **Anthropic**| **Claude 3.5 Sonnet**| 200,000 | ~800ms / 65 tps | $3.00 | $15.00 | **Líder Pensamiento Crítico**| **Rol 3 (Primario de Máxima Calidad)** |

### Presupuesto Operativo Mensual Proyectado
* **Costo por Corrida Individual (Pipeline Completo):**
  - Rol 1 (Gemini 2.0 Flash): ~1,500 tokens in / 400 out $\to \approx \$0.00031$ USD.
  - Rol 2 (DeepSeek-R1): ~1,800 tokens in / 800 out $\to \approx \$0.00274$ USD.
  - Rol 3 (Claude 3.5 Sonnet o GPT-4o-mini): ~1,200 tokens in / 300 out $\to \approx \$0.00197$ USD (con GPT-4o-mini baja a $\$0.00036$).
  - **Costo total promedio por inferencia completa:** $\approx \$0.00502$ USD.
* **Proyección de Ejecución Periódica:**
  - Corrida cada 2 horas (12 ejecuciones/día $\times 30$ días = 360 corridas): $\approx \$1.81$ USD/mes.
  - Corrida horaria continua (24 ejecuciones/día $\times 30$ días = 720 corridas): $\approx \$3.61$ USD/mes.

---

## 5. Diagramas de Clases y Flujo de Arquitectura

```
 +-----------------------------------------------------------------------------------+
 |                             MacroPredictionPipeline                               |
 +-----------------------------------------------------------------------------------+
 | - collector: MacroNewsCollector                                                   |
 | - engine: MultiProviderAIEngine                                                   |
 | - analyst: MacroAnalystPredictor                                                  |
 | - auditor: MacroPredictionAuditor                                                 |
 | - repository: MacroRepository                                                     |
 +-----------------------------------------------------------------------------------+
 | + run_prediction_cycle() -> FinalUSDTPrediction                                   |
 | + get_latest_prediction() -> Optional[FinalUSDTPrediction]                        |
 +-----------------------------------------------------------------------------------+
          |                     |                      |                      |
          v                     v                      v                      v
 +------------------+  +--------------------+  +--------------------+  +--------------------+
 |MacroNewsCollector|  |MultiProviderAIEngine| |MacroAnalystPredict |  |MacroPredictionAuditor|
 +------------------+  +--------------------+  +--------------------+  +--------------------+
 |+ fetch_news()    |  |+ dispatch(prompt)  |  |+ generate_draft()  |  |+ audit_draft()     |
 |+ extract_events()|  |+ get_healthy_key() |  +--------------------+  +--------------------+
 +------------------+  |  circuit_breaker   |
                       +--------------------+
                                 |
                                 v
                       +--------------------+
                       |     AIKeyPool      |
                       +--------------------+
                       | - keys: List[Key]  |
                       | - slot_index: int  |
                       | + rotate_key()     |
                       | + set_cooldown()   |
                       +--------------------+
```

---

## 6. Diagramas de Secuencia del Pipeline

### 6.1 Flujo Principal Exitoso (Happy Path)

```
Operador / Cron      MacroCollector      Rol 1: Buscador     Rol 2: Predictor     Rol 3: Auditor      AuditLogger / DB      Telegram
      |                    |                    |                   |                   |                    |                  |
      |--- 1. Trigger ---->|                    |                   |                   |                    |                  |
      |                    |--- 2. Fetch HTML ->|                   |                   |                    |                  |
      |                    |    & RSS Feeds     |                   |                   |                    |                  |
      |                    |--- 3. Raw Data --->|                   |                   |                    |                  |
      |                    |                    |-- 4. Extracción ->|                   |                    |                  |
      |                    |                    |   Estructurada    |                   |                    |                  |
      |                    |                    |-- 5. Context JSON                    |                    |                  |
      |                    |                    |------------------>|                   |                    |                  |
      |                    |                                        |-- 6. Razonamiento |                    |                  |
      |                    |                                        |   Monetario & Lag |                    |                  |
      |                    |                                        |-- 7. DraftPrediction                   |                  |
      |                    |                                        |------------------>|                    |                  |
      |                    |                                                            |-- 8. Auditoría --->|                  |
      |                    |                                                            |   Adversarial      |                  |
      |                    |                                                            |                    |                  |
      |                    |                                                            |-- [VEREDICTO] ---->|                  |
      |                    |                                                            |   APROBADO/CORREG  |                  |
      |                    |                                                            |                    |-- 9. SHA-256 --->|
      |                    |                                                            |                    |   Chained Hash   |
      |                    |                                                            |                    |                  |-- 10. Alerta -->
      |                    |                                                            |                    |                  |   Sanitizada
```

### 6.2 Flujo de Veto Adversarial (Fail-Closed por Alucinación o Inconsistencia)

```
Rol 2: Predictor               Rol 3: Auditor (Cross-Family)               AuditLogger / DB                  Telegram
       |                                      |                                    |                            |
       |--- 1. DraftPrediction -------------->|                                    |                            |
       |    (Alucinación o Inconsistencia)    |-- 2. Detección de Falla            |                            |
       |                                      |      (Dato no respaldado)          |                            |
       |                                      |-- 3. Veredicto: RECHAZADO -------->|                            |
       |                                      |                                    |-- 4. Log REJECTION Event ->|
       |                                      |                                    |      (Motivo auditado)     |
       |                                      |                                    |                            |-- 5. Alerta Fail-Closed
       |                                      |                                    |                            |      (Estado NEUTRAL)
```

### 6.3 Conmutación por Error de Proveedores (Failover en Cascada)

```
MultiProviderAIEngine              Gemini Pool                   Groq Pool                  DeepSeek Pool
          |                             |                            |                            |
          |--- 1. Inferencia Req ------>|                            |                            |
          |                             |-- 2. HTTP 429 Quota Ex -->|                            |
          |-- 3. Cooldown Key & Circuit |                            |                            |
          |      Breaker Open (Gemini)  |                            |                            |
          |                                                          |                            |
          |--- 4. Failover Inmediato ------------------------------->|                            |
          |                                                          |-- 5. Inferencia Exitosa -->|
          |<-- 6. Payload JSON OK -----------------------------------|                            |
```

---

## 7. Prompts del Sistema Especializados para los 3 Roles (Verbatim)

### 7.1 Rol 1: Buscador / Recopilador de Noticias y Variables
```
Eres un Asistente Especializado en Extracción y Clasificación de Noticias Macroeconómicas para el mercado cambiario venezolano.

Tu única función es analizar el texto suministrado, identificar hechos económicos concretos y transformarlos en una estructura JSON estricta según la taxonomía económica canónica.

REGLAS INNEGOCIABLES:
1. TAXONOMÍA PERMITIDA Y CÓDIGOS DE EVENTO: Debes clasificar cada evento asignando estrictamente su código taxonómico (código canónico o alias corto) y su categoría canónica:
   - GASTO_PUBLICO_PATRIA: GP-01 (EVT_PATRIA_GUERRA_ACTIVOS), GP-02 (EVT_PATRIA_GUERRA_JUBILADOS), GP-03 (EVT_PATRIA_AGUINALDOS_FRAC)
   - INTERVENCION_CAMBIARIA_BCV: IC-01 (EVT_BCV_INTERVENCION_REGULAR), IC-02 (EVT_BCV_INTERVENCION_AGRESIVA), IC-03 (EVT_BCV_INTERVENCION_DEFICIT)
   - POLITICA_MONETARIA_LIQUIDEZ: PM-01 (EVT_BCV_LIQUIDEZ_M2_SPIKE)
   - CALENDARIO_FISCAL_SENIAT: CF-01 (EVT_SENIAT_PAGO_QUINCENA), CF-02 (EVT_SENIAT_ZAFRA_ISLR_MAR)
   - REGULACION_CAMBIARIA_BANCARIA: RB-01 (EVT_REGULACION_FISCALIZACION)
   - OPERATIVA_MERCADO_P2P: OP-01 (EVT_SUDEBAN_LUNES_BANCARIO), OP-02 (EVT_CAIDA_PAGO_MOVIL_NAC)
   - GEOPOLITICA_PETROLERA: GPET-01 (EVT_OFAC_LICENCIA_RENOVADA), GPET-02 (EVT_OFAC_LICENCIA_REVOCADA)
2. OBJETIVIDAD RADICAL: Prohibido interpretar si el precio del USDT subirá o bajará. Solo extrae hechos fácticos.
3. DATOS CUANTITATIVOS: Si la noticia menciona montos específicos (USD, VES o porcentajes), extráelos con su unidad. Si no se especifican montos exactos, asigna "cifras_especificadas": false.
4. CREDIBILIDAD: Evalúa la fuente en "ALTA" (comunicados oficiales, BCV, ministerios), "MEDIA" (portales financieros reconocidos) o "BAJA" (rumores o redes sociales sin corroboración).
5. SALIDA EXCLUSIVAMENTE JSON: Tu respuesta debe ser un objeto JSON parseable sin texto explicativo adicional.
```

### 7.2 Rol 2: Analista / Predictor Econométrico
```
Eres un Economista Senior Especialista en Dinámica Monetaria y Mercados Cambiarios en Venezuela.

Tu objetivo es proyectar el comportamiento del precio del USDT frente al Bolívar (VES) en Binance P2P a partir de los hechos macroeconómicos y el estado del mercado proporcionados en el contexto.

MARCO DE RAZONAMIENTO ECONÓMICO:
1. FUERZAS ALCISTAS (Presión de Devaluación del VES / Subida del USDT):
   - Inyecciones masivas de bolívares por subsidios gubernamentales (Sistema Patria) y aguinaldos del sector público.
   - Incremento acelerado de la liquidez monetaria M2.
   - Disminución o insuficiencia en la intervención cambiaria semanal del BCV.
   - Sanciones petroleras o revocación de licencias energéticas.
2. FUERZAS BAJISTAS / DE CONTENCIÓN (Apreciación del VES / Contención del USDT):
   - Asignaciones cambiarias de shock del BCV (> $100 millones de USD en la banca comercial).
   - Vencimientos de anticipos de impuestos del SENIAT (las empresas liquidan USDT para pagar en bolívares).
   - Zafra tributaria anual de ISLR en el mes de marzo.
   - Prórrogas o flexibilizaciones de licencias petroleras por la OFAC.
3. FUERZAS DE VOLATILIDAD / NEUTRALES:
   - Feriados bancarios (Lunes bancarios SUDEBAN) ensanchan los spreads bid-ask pero no definen una tendencia direccional sostenida.

REGLAS DE SALIDA:
- "direccion": Exclusivamente "SUBE", "BAJA" o "ESTABLE".
- "lapso_estimado": "24h-48h", "3-5 dias" o "semanal".
- "confiabilidad_porcentaje": Número flotante de 0.0 a 100.0. Debe reflejar la calidad de los datos y penalizar la presencia de fuerzas contrapuestas.
- "factores_clave": Lista de factores que justifican la dirección.
- "justificacion_detallada": Cadena explicativa rigurosa y causal del mecanismo de transmisión.
- "riesgos_invalidacion": Factores que revertirían la proyección estimada.
```

### 7.3 Rol 3: Revisor / Auditor Adversarial Anti-Alucinaciones
```
Eres un Auditor Cuantitativo y Crítico Adversarial de Señales Financieras.

Tu misión es auditar de manera escéptica e implacable la predicción macroeconómica generada por el Analista, asegurando consistencia matemática, veracidad empírica y salvaguarda Fail-Closed.

REGLA CONSTITUCIONAL:
Operas como una compuerta independiente bajo el principio de Verificación Cruzada entre Familias de Modelos. Si el borrador fue elaborado por un modelo de la familia DeepSeek o Google, tú aportas un criterio analítico desacoplado para eliminar sesgos comunes.

CRITERIOS DE AUDITORÍA:
1. VERIFICACIÓN FÁCTICA ANTI-ALUCINACIÓN:
   - ¿Cada hecho, cifra o fecha citada en la justificación proviene textualmente del contexto macroeconómico suministrado?
   - Si el Analista cita eventos no presentes en el contexto, márcalo inmediatamente como "ALUCINACIÓN DETECTADA".
2. COHERENCIA DE TRANSMISIÓN MONETARIA:
   - ¿La dirección propuesta ("SUBE", "BAJA", "ESTABLE") es coherente con el balance neto de fuerzas?
   - Si hay una megaintervención del BCV en curso y el Analista proyecta "SUBE" sin sustentar una fuerza mayor, veta o ajusta la señal.
3. CALIBRACIÓN DE SOBRECONFIANZA:
   - Si existen fuerzas antagónicas activas (ej. bonos Patria vs intervención BCV simultánea) y la confiabilidad supera el 75%, redúcela al rango razonable (50% - 65%).
4. DETERMINACIÓN DEL VEREDICTO:
   - "APROBADO": La predicción es sólida, fáctica y calibrada.
   - "CORREGIDO": La dirección es correcta pero la confiabilidad o la justificación requieren ajuste prudencial.
   - "RECHAZADO": Existen alucinaciones graves, contradicciones económicas directas o falta de quórum fáctico. (Activa salvaguarda Fail-Closed hacia estado seguro NEUTRAL).

Emite tu informe exclusivamente en formato JSON estructurado según el esquema de auditoría.
```

---

## 8. Esquemas Formales Pydantic v2 (Modelos de Datos)

```python
"""Esquemas Pydantic v2 para el subsistema de predicción macroeconómica."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ValidationInfo, field_validator


class TaxonomyCategory(str, Enum):
    """Categorías macroeconómicas canónicas según taxonomía venezolana (Prompt 7.1 y SPEC-023)."""
    GASTO_PUBLICO_PATRIA = "GASTO_PUBLICO_PATRIA"
    INTERVENCION_CAMBIARIA_BCV = "INTERVENCION_CAMBIARIA_BCV"
    POLITICA_MONETARIA_LIQUIDEZ = "POLITICA_MONETARIA_LIQUIDEZ"
    CALENDARIO_FISCAL_SENIAT = "CALENDARIO_FISCAL_SENIAT"
    REGULACION_CAMBIARIA_BANCARIA = "REGULACION_CAMBIARIA_BANCARIA"
    OPERATIVA_MERCADO_P2P = "OPERATIVA_MERCADO_P2P"
    GEOPOLITICA_PETROLERA = "GEOPOLITICA_PETROLERA"


# Alias para interoperabilidad con documentación canónica
MacroCategoryEnum = TaxonomyCategory


class SourceCredibility(str, Enum):
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"


class PredictionDirection(str, Enum):
    SUBE = "SUBE"
    BAJA = "BAJA"
    ESTABLE = "ESTABLE"


class TimeframeHorizon(str, Enum):
    HORIZONTE_24_48H = "24h-48h"
    HORIZONTE_3_5D = "3-5 dias"
    HORIZONTE_SEMANAL = "semanal"


class AuditVerdictEnum(str, Enum):
    APROBADO = "APROBADO"
    CORREGIDO = "CORREGIDO"
    AJUSTADO_FAIL_CLOSED = "AJUSTADO_FAIL_CLOSED"
    RECHAZADO = "RECHAZADO"


class MacroEventItem(BaseModel):
    """Evento macroeconómico individual normalizado por el Buscador."""
    event_id: str = Field(..., description="Identificador único del evento")
    code: str = Field(..., description="Código corto del evento (ej. GP-01, IC-01)")
    categoria: TaxonomyCategory
    titulo: str = Field(..., min_length=5, max_length=150)
    resumen_factico: str = Field(..., min_length=10, max_length=500, description="Resumen fáctico y objetivo")
    fuente_nombre: str
    fuente_url: Optional[str] = None
    credibilidad: SourceCredibility
    cifras_especificadas: bool = False
    monto_relevante: Optional[float] = None
    unidad_monto: Optional[str] = None
    timestamp_evento_utc: datetime
    base_weight: Optional[float] = Field(None, ge=0.10, le=1.00, description="Peso intrínseco w_i")
    vector_direction: Optional[int] = Field(None, description="Dirección d_i: +1 (SUBE), -1 (BAJA), 0 (ESTABLE)")
    latency_hours: Optional[float] = Field(None, ge=0.0, description="Latencia inicial L_i en horas")
    half_life_hours: Optional[float] = Field(None, gt=0.0, description="Semivida de decaimiento h_i en horas")


class MacroContextPayload(BaseModel):
    """Colección de contexto macroeconómico enviada al Predictor."""
    timestamp_extraccion: datetime
    eventos: List[MacroEventItem]
    tasa_p2p_actual: float = Field(gt=0.0)
    tasa_bcv_actual: float = Field(gt=0.0)
    brecha_cambiaria_porcentaje: float
    fuentes_consultadas: List[str]


# Alias de compatibilidad
MacroContextCollection = MacroContextPayload


class DraftPrediction(BaseModel):
    """Borrador preliminar de proyección económica emitido por el Predictor."""
    direccion: PredictionDirection
    lapso_estimado: TimeframeHorizon
    confiabilidad_porcentaje: float = Field(ge=0.0, le=100.0)
    factores_clave: List[str] = Field(min_length=1)
    justificacion_detallada: str = Field(min_length=30)
    riesgos_invalidacion: List[str] = Field(min_length=1)


class AuditResult(BaseModel):
    """Dictamen crítico emitido por el Revisor adversarial."""
    veredicto: AuditVerdictEnum
    direccion_validada: PredictionDirection
    confiabilidad_calibrada: float = Field(ge=0.0, le=100.0)
    puntaje_rigor: float = Field(ge=0.0, le=10.0)
    alucinaciones_detectadas: bool = False
    hallazgos_criticos: List[str] = Field(default_factory=list)
    observaciones_correccion: Optional[str] = None


class AuditMetadata(BaseModel):
    """Metadatos de auditoría y trazabilidad criptográfica."""
    predictor_model: str
    reviewer_model: str
    cross_family_verified: bool = True
    prev_hash: str
    prediction_hash: str
    timestamp_utc: datetime
    execution_duration_ms: int


class FinalUSDTPrediction(BaseModel):
    """Predicción final consolidada, auditada y lista para difusión."""
    id: str
    veredicto: AuditVerdictEnum
    direccion: PredictionDirection
    lapso_estimado: TimeframeHorizon
    confiabilidad_porcentaje: float = Field(ge=0.0, le=100.0)
    justificacion_auditada: str
    factores_clave: List[str]
    riesgos_invalidacion: List[str]
    metadata: AuditMetadata

    @field_validator("confiabilidad_porcentaje")
    @classmethod
    def validar_confianza_maxima_si_corregido(cls, v: float, info: ValidationInfo) -> float:
        """Acota la confiabilidad a un máximo de 75.0% si el veredicto es CORREGIDO o AJUSTADO_FAIL_CLOSED."""
        if v > 100.0 or v < 0.0:
            raise ValueError("La confiabilidad debe estar entre 0.0 y 100.0")

        if info.data and "veredicto" in info.data:
            veredicto = info.data["veredicto"]
            veredicto_str = veredicto.value if hasattr(veredicto, "value") else str(veredicto)

            if veredicto_str in ("CORREGIDO", "AJUSTADO_FAIL_CLOSED") and v > 75.0:
                return 75.0

        return v
```

---

## 9. Lógica del Circuit Breaker y Tolerancia a Fallos Round-Robin

### 9.1 Máquina de Estados del Circuit Breaker
Cada proveedor de LLM cuenta con una instancia de Circuit Breaker desacoplada:
* **Estado `CLOSED`:** Todas las solicitudes se enrutan de forma normal rotando claves en el pool mediante Round-Robin.
* **Estado `OPEN`:** Si se registran 3 fallos consecutivos (HTTP 429, 500, 503 o timeouts) o todas las claves entran en cooldown, el proveedor conmuta inmediatamente a `OPEN`. Cualquier nueva petición es derivada al siguiente proveedor en la lista sin esperar timeout.
* **Estado `HALF-OPEN`:** Al expirar el tiempo de reposo (*cooling period*, default 60 segundos), el circuito autoriza una petición de sondeo (*canary probe*). Si responde con éxito, se restablece a `CLOSED`. Si vuelve a fallar, regresa a `OPEN`.

### 9.2 Política de Reintentos con Tenacity
```python
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_random_exponential
import httpx

@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=0.5, max=8.0),
    retry=retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException)),
    before_sleep=lambda retry_state: retry_state.args[0].rotate_key_pre_retry(),
    reraise=True
)
def execute_provider_call_with_rotation(router: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    key = router.get_current_provider_key()
    return router.dispatch(key, payload)
```

---

## 10. Persistencia, Trazabilidad SHA-256 y Modelos de Base de Datos

### 10.1 Modelo de Base de Datos SQLAlchemy
```python
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from src.data.database import Base

class MacroPredictionModel(Base):
    __tablename__ = "macro_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prediction_id = Column(String(64), unique=True, nullable=False, index=True)
    timestamp_utc = Column(DateTime, nullable=False, index=True)
    direction = Column(String(16), nullable=False)
    timeframe = Column(String(32), nullable=False)
    confidence_pct = Column(Float, nullable=False)
    auditor_verdict = Column(String(32), nullable=False)
    justification = Column(Text, nullable=False)
    key_drivers = Column(Text, nullable=False)  # JSON codificado
    invalidating_risks = Column(Text, nullable=False)  # JSON codificado
    predictor_model = Column(String(64), nullable=False)
    reviewer_model = Column(String(64), nullable=False)
    cross_family_verified = Column(Boolean, default=True)
    prev_hash = Column(String(64), nullable=False)
    prediction_hash = Column(String(64), nullable=False, unique=True)
```

### 10.2 Algoritmo de Encadenamiento Criptográfico (Pipe-Delimited)

Para blindar el sistema contra ataques de colisión por corrimiento de límites entre campos adyacentes y garantizar inmutabilidad absoluta, cada predicción $k$ se encadena mediante una cadena canónica estrictamente delimitada por tuberías (`|`):

$$\text{canonical\_payload}_k = \text{prev\_hash}_{k-1} \,\|\, \text{"\|"} \,\|\, \text{timestamp\_iso} \,\|\, \text{"\|"} \,\|\, \text{direction} \,\|\, \text{"\|"} \,\|\, \text{timeframe} \,\|\, \text{"\|"} \,\|\, \text{confidence} \,\|\, \text{"\|"} \,\|\, \text{model} \,\|\, \text{"\|"} \,\|\, \text{justification}$$

$$\text{prediction\_hash}_k = \text{SHA256}\Big(\text{canonical\_payload}_k\Big)$$

Donde:
* $\text{prev\_hash}_{k-1}$: Hash SHA-256 de 64 caracteres de la predicción inmediatamente anterior. Para el bloque génesis ($k=0$), se utiliza la semilla canónica `"0" * 64`.
* $\text{timestamp\_iso}$: Cadena UTC ISO-8601 (ej. `2026-11-17T00:00:00Z`).
* $\text{direction}$: Valor literal del enum `PredictionDirection` (`"SUBE"`, `"BAJA"`, `"ESTABLE"`).
* $\text{timeframe}$: Valor literal de `TimeframeHorizon` (`"24h-48h"`, `"3-5 dias"`, `"semanal"`).
* $\text{confidence}$: Representación numérica fija con dos decimales `f"{float(confidence):.2f}"` (ej. `"75.00"`).
* $\text{model}$: Identificador del modelo revisor/auditor que firmó el dictamen, sanitizando cualquier carácter `|` residual como `/`.
* $\text{justification}$: Texto completo de `justificacion_auditada`, con espacios extremos eliminados y sustituyendo caracteres `|` por `/`.

Implementación de referencia en Python:
```python
import hashlib


def compute_prediction_hash(
    prev_hash: str,
    timestamp_iso: str,
    direction: str,
    timeframe: str,
    confidence: float,
    model: str,
    justification: str,
) -> str:
    """Calcula el hash criptográfico SHA-256 de la cadena canónica pipe-delimited."""
    conf_str = f"{float(confidence):.2f}"
    clean_model = model.strip().replace("|", "/")
    clean_just = justification.strip().replace("|", "/")
    canonical_payload = (
        f"{prev_hash}|{timestamp_iso}|{direction}|{timeframe}|{conf_str}|{clean_model}|{clean_just}"
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
```

---

## 11. Alineación Constitucional y Reglas de Seguridad Innegociables

| Mandato Constitucional | Cumplimiento en SPEC-023 / PLAN-023 |
| :--- | :--- |
| **Fail-Closed Ante Incertidumbre** | Si el Revisor emite `RECHAZADO` o si la coherencia direccional entre fuerzas es nula ($\text{Coh} < 0.20$), el sistema bloquea recomendaciones y emite `NEUTRAL` con alerta preventiva. |
| **Cero Secretos en Memoria y Logs** | Cifrado AES-256-GCM en reposo para claves de IA. Filtrado estricto por regex en `sanitize_message()` antes de notificar por Telegram o renderizar en Dashboard. |
| **Separación de Responsabilidades** | El pipeline no altera precios ni ejecuta órdenes P2P; solo produce inteligencia advisory. |
| **Trazabilidad Total Append-Only** | Registro encadenado SHA-256 en la tabla `macro_predictions` y en `security_events`. |
| **Verificación Cruzada (Cross-Family)** | Obligatoriedad arquitectónica: el Revisor LLM jamás pertenece a la misma familia de pesos que el Predictor. |
| **Desarrollo Guiado por Pruebas (TDD)** | 100% de contratos y componentes cuentan con pruebas unitarias e integración en `tests/unit/`. |
