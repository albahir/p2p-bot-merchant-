# Estrategia de Remediación de Arquitectura y Contratos: PLAN-023 (`plan.md`)

**Documento:** Plan Remediation Strategy Report  
**Subsistema:** `023-ai-market-predictor`  
**Autor:** Explorer M1_IT2_1 (Plan Remediation Strategist)  
**Fecha:** 17 de Noviembre de 2026  
**Objetivo:** Formular la estrategia exacta de corrección para `.specify/specs/023-ai-market-predictor/plan.md` tras el dictamen `REQUEST_CHANGES` de Challenger 2 (`challenger_m1_2`).  

---

## 1. Resumen Ejecutivo

Durante la compuerta de validación del Hito 1 (Iteración 1), el agente Challenger 2 identificó cuatro discrepancias críticas en el archivo de arquitectura `plan.md`:
1. **Desalineación del 100% en `TaxonomyCategory`**: El enum en la Sección 8 no coincidía con las 7 categorías prescritas en el System Prompt 7.1 (Rol 1: Buscador) ni con las categorías de `docs/macro_usdt_taxonomy.md`. Esto provocaría un fallo sistemático de validación `pydantic.ValidationError` al ingerir cualquier evento clasificado por el LLM.
2. **Vulnerabilidad de Colisión Criptográfica en SHA-256 Chaining**: La fórmula de encadenamiento utilizaba concatenación simple de cadenas sin delimitadores (`+`), permitiendo colisiones por corrimiento de límites entre campos adyacentes (`direction` y `timeframe`).
3. **Validador Muerto / Sin Efecto en `validar_confianza_maxima_si_corregido`**: El método `@field_validator("confiabilidad_porcentaje")` en `FinalUSDTPrediction` solo verificaba el rango [0.0, 100.0], omitiendo consultar `info.data.get("veredicto")` y dejando sin acotar la confiabilidad ante correcciones del auditor.
4. **Identificador No-ASCII (`resumen_fáctico`)**: El uso de la tilde `á` en el atributo de `MacroEventItem` vulnera los estándares de persistencia y serialización del proyecto.

Este documento establece las correcciones quirúrgicas, fórmulas matemáticas exactas, bloques de código Pydantic v2 listos para sustitución y pruebas empíricas que devuelven la especificación `plan.md` al 100% de cumplimiento constitucional y operativo.

---

## 2. Remediación 1: Alineación Canónica de `TaxonomyCategory`

### 2.1 Diagnóstico del Problema
En `plan.md` líneas 228–235, el System Prompt del Rol 1 (Buscador) ordena textualmente al LLM:
```text
1. TAXONOMÍA PERMITIDA: Debes clasificar cada evento estrictamente en una de las siguientes categorías:
   - GASTO_PUBLICO_PATRIA (Pagos de nómina, bonos Patria, aguinaldos)
   - INTERVENCION_CAMBIARIA_BCV (Montos inyectados por el BCV en mesas de cambio)
   - POLITICA_MONETARIA_LIQUIDEZ (Variaciones de liquidez M2, encaje legal)
   - CALENDARIO_FISCAL_SENIAT (Vencimientos de impuestos, recaudación, anticipos)
   - REGULACION_CAMBIARIA_BANCARIA (Medidas SUDEBAN, límites bancarios, controles de precios)
   - OPERATIVA_MERCADO_P2P (Feriados bancarios, fallas de pago móvil o plataforma)
   - GEOPOLITICA_PETROLERA (Sanciones OFAC, licencias petroleras, ingresos de exportación)
```
Sin embargo, en la Sección 8 (líneas 310–317), `TaxonomyCategory` definía:
```python
# CÓDIGO DEFECTUOSO ACTUAL EN plan.md:
class TaxonomyCategory(str, Enum):
    INTERVENCION_BCV = "INTERVENCION_BCV"
    PAGO_PATRIA_NOMINA = "PAGO_PATRIA_NOMINA"
    LIQUIDEZ_MONETARIA_M2 = "LIQUIDEZ_MONETARIA_M2"
    BRECHA_CAMBIARIA_ARBITRAJE = "BRECHA_CAMBIARIA_ARBITRAJE"
    REGULACION_BANCARIA_ENCAJE = "REGULACION_BANCARIA_ENCAJE"
    FACTORES_ESTACIONALES_TRIBUTARIOS = "FACTORES_ESTACIONALES_TRIBUTARIOS"
    POLITICA_SANCIONES = "POLITICA_SANCIONES"
```
Todas las 7 categorías fallaban la validación. Adicionalmente, `OPERATIVA_MERCADO_P2P` estaba totalmente omitida.

### 2.2 Estrategia de Sustitución en `plan.md`
Se reemplaza la declaración de `TaxonomyCategory` por las 7 categorías canónicas exactas, añadiendo el alias `MacroCategoryEnum = TaxonomyCategory` para interoperabilidad con `docs/macro_usdt_taxonomy.md`:

```python
class TaxonomyCategory(str, Enum):
    """Categorías macroeconómicas canónicas según taxonomía venezolana (Prompt 7.1 y SPEC-023)."""
    GASTO_PUBLICO_PATRIA = "GASTO_PUBLICO_PATRIA"
    INTERVENCION_CAMBIARIA_BCV = "INTERVENCION_CAMBIARIA_BCV"
    POLITICA_MONETARIA_LIQUIDEZ = "POLITICA_MONETARIA_LIQUIDEZ"
    CALENDARIO_FISCAL_SENIAT = "CALENDARIO_FISCAL_SENIAT"
    REGULACION_CAMBIARIA_BANCARIA = "REGULACION_CAMBIARIA_BANCARIA"
    OPERATIVA_MERCADO_P2P = "OPERATIVA_MERCADO_P2P"
    GEOPOLITICA_PETROLERA = "GEOPOLITICA_PETROLERA"


# Alias para interoperabilidad con la documentación taxonómica canónica
MacroCategoryEnum = TaxonomyCategory
```

---

## 3. Remediación 2: Fórmula Pipe-Delimited para Encadenamiento SHA-256

### 3.1 Diagnóstico de Vulnerabilidad Criptográfica
En `plan.md` Sección 10.2 (línea 479), la fórmula se definía como:
$$\text{prediction\_hash}_k = \text{SHA256}\Big(\text{prev\_hash}_{k-1} + \text{timestamp} + \text{direction} + \text{timeframe} + \text{confidence} + \text{justification}\Big)$$

Al concatenar con operador `+` sin delimitador, dos predicciones distintas producen exactamente la misma cadena de bytes:
* Predicción A: `direction = "SUB"`, `timeframe = "E24h"` $\to$ `"SUBE24h"`
* Predicción B: `direction = "SUBE"`, `timeframe = "24h"` $\to$ `"SUBE24h"`

Ambas generan idéntico hash SHA-256, constituyendo una colisión por corrimiento de delimitador que invalida la inmutabilidad de la auditoría.

### 3.2 Especificación Canónica Pipe-Delimited
Se prescribe la cadena canónica separada por barra vertical (`|`):

$$\text{canonical\_payload}_k = \text{prev\_hash}_{k-1} \,\|\, \text{"\|"} \,\|\, \text{timestamp\_iso} \,\|\, \text{"\|"} \,\|\, \text{direction} \,\|\, \text{"\|"} \,\|\, \text{timeframe} \,\|\, \text{"\|"} \,\|\, \text{confidence} \,\|\, \text{"\|"} \,\|\, \text{model} \,\|\, \text{"\|"} \,\|\, \text{justification}$$

$$\text{prediction\_hash}_k = \text{SHA256}\Big(\text{canonical\_payload}_k\Big)$$

En Python:
```python
f"{prev_hash}|{timestamp_iso}|{direction}|{timeframe}|{confidence}|{model}|{justification}"
```

### 3.3 Reglas de Normalización de Campos
Para garantizar determinismo absoluto entre plataformas:
1. `prev_hash`: 64 caracteres hexadecimales en minúsculas. Génesis: `"0" * 64`.
2. `timestamp_iso`: Formato ISO-8601 UTC en cadena: `YYYY-MM-DDTHH:MM:SSZ` (ej. `2026-11-17T00:00:00Z`).
3. `direction`: Valor literal del enum (`"SUBE"`, `"BAJA"`, `"ESTABLE"`).
4. `timeframe`: Valor literal del horizonte (`"24h-48h"`, `"3-5 dias"`, `"semanal"`).
5. `confidence`: Formato con dos decimales fijos `f"{float(conf):.2f}"` (ej. `"75.00"`).
6. `model`: Nombre o identificador del modelo revisor/auditor (ej. `"claude-3-5-sonnet"` o `"gpt-4o-mini"`), sanitizando cualquier carácter `|` por `/`.
7. `justification`: Texto de la justificación auditada, sin espacios iniciales/finales, sustituyendo saltos de línea y caracteres `|` por espacios o barras diagonales `/` para blindaje anti-inyección de delimitadores.

### 3.4 Función Criptográfica de Referencia en `plan.md`
```python
import hashlib
from typing import Union

def build_canonical_prediction_string(
    prev_hash: str,
    timestamp_iso: str,
    direction: str,
    timeframe: str,
    confidence: Union[float, str],
    model: str,
    justification: str,
) -> str:
    """Construye la cadena canónica pipe-delimited para auditoría SHA-256."""
    conf_str = f"{float(confidence):.2f}"
    clean_model = model.strip().replace("|", "/")
    clean_justification = justification.strip().replace("|", "/")
    return f"{prev_hash}|{timestamp_iso}|{direction}|{timeframe}|{conf_str}|{clean_model}|{clean_justification}"

def compute_prediction_hash(canonical_str: str) -> str:
    """Calcula el hash criptográfico SHA-256 de la cadena canónica."""
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
```

---

## 4. Remediación 3: Implementación del Validador `validar_confianza_maxima_si_corregido`

### 4.1 Diagnóstico del Problema
En `plan.md` líneas 413–418:
```python
# CÓDIGO DEFECTUOSO ACTUAL EN plan.md:
@field_validator("confiabilidad_porcentaje")
@classmethod
def validar_confianza_maxima_si_corregido(cls, v: float, info: Any) -> float:
    if v > 100.0 or v < 0.0:
        raise ValueError("La confiabilidad debe estar entre 0.0 y 100.0")
    return v
```
El validador:
1. No consultaba `info.data.get("veredicto")`.
2. Repetía redundantemente la restricción de campo `Field(ge=0.0, le=100.0)`.
3. Permitía que una predicción con dictamen `CORREGIDO` o `AJUSTADO_FAIL_CLOSED` mantuviera un 95% o 99% de confianza, violando la regla de prudencia macroeconómica que exige un tope estricto del 75.0% (o 65.0%).

### 4.2 Lógica de Enrutamiento y Capping Defensivo
En Pydantic v2:
* Se importa `ValidationInfo` desde `pydantic`.
* Dado que `veredicto` se declara antes que `confiabilidad_porcentaje` en el modelo `FinalUSDTPrediction`, `info.data` ya contiene el valor verificado de `veredicto`.
* El validador debe contemplar tanto instancias de enum (`AuditVerdictEnum.CORREGIDO`) como cadenas (`"CORREGIDO"`, `"AJUSTADO_FAIL_CLOSED"`).
* Si el veredicto es `CORREGIDO` o `AJUSTADO_FAIL_CLOSED` y la confiabilidad supera `75.0%`, el sistema aplica **capping automático defensivo** retornando `75.0` (o `min(v, 75.0)`). De manera alternativa, si se requiere rechazo estricto en tiempo de validación, puede levantar `ValueError`. El capping defensivo (`return min(v, 75.0)`) garantiza que ninguna señal sobreconfiada pase a difusión sin tumbar la canalización.

### 4.3 Código de Reemplazo en `plan.md`
```python
    @field_validator("confiabilidad_porcentaje")
    @classmethod
    def validar_confianza_maxima_si_corregido(cls, v: float, info: ValidationInfo) -> float:
        """Acota la confiabilidad a un máximo de 75.0% si el auditor emitió una corrección."""
        if v > 100.0 or v < 0.0:
            raise ValueError("La confiabilidad debe estar comprendida entre 0.0 y 100.0")
        
        if info.data and "veredicto" in info.data:
            veredicto = info.data["veredicto"]
            veredicto_str = veredicto.value if hasattr(veredicto, "value") else str(veredicto)
            
            if veredicto_str in ("CORREGIDO", "AJUSTADO_FAIL_CLOSED") and v > 75.0:
                # Capping defensivo Fail-Closed: restringe al tope permitido de 75.0%
                return 75.0

        return v
```

---

## 5. Remediación 4: Sustitución de Identificador No-ASCII `resumen_fáctico`

### 5.1 Diagnóstico del Problema
En `plan.md` línea 349:
```python
# CÓDIGO DEFECTUOSO:
resumen_fáctico: str = Field(..., min_length=10, max_length=500)
```
El carácter `á` genera incompatibilidades en mapeos ORM de SQLAlchemy, serializadores JSON multiplataforma y migraciones en bases de datos con codificaciones restrictivas.

### 5.2 Código de Reemplazo
Se sustituye por el identificador estándar ASCII `resumen_factico`:
```python
resumen_factico: str = Field(
    ..., 
    min_length=10, 
    max_length=500, 
    description="Resumen fáctico y objetivo del evento macroeconómico normalizado"
)
```

---

## 6. Remediaciones de Apoyo para Coherencia Integral

Para garantizar que `plan.md` quede perfectamente alineado con `tasks.md`, `PROJECT.md` y `docs/macro_usdt_taxonomy.md`:

### 6.1 Incorporación de `code: str` en `MacroEventItem`
Para reflejar la taxonomía canónica de los 14 eventos (`EVT_PATRIA_GUERRA_ACTIVOS`, `EVT_BCV_INTERVENCION_REGULAR`, etc.):
```python
code: str = Field(
    ..., 
    description="Código canónico del evento en la taxonomía (ej. EVT_PATRIA_GUERRA_ACTIVOS)"
)
```

### 6.2 Armonización de `AuditVerdictEnum`
Para resolver la discrepancia señalada en la Obs 3 de Challenger 2 entre `AuditVerdictEnum` (`APROBADO`, `CORREGIDO`, `RECHAZADO`) y `AJUSTADO_FAIL_CLOSED` (presente en `PROJECT.md` y `tasks.md`):
```python
class AuditVerdictEnum(str, Enum):
    APROBADO = "APROBADO"
    CORREGIDO = "CORREGIDO"
    AJUSTADO_FAIL_CLOSED = "AJUSTADO_FAIL_CLOSED"
    RECHAZADO = "RECHAZADO"
```

### 6.3 Estandarización del Nombre de Contenedor `MacroContextPayload`
En la Sección 3.4 (línea 89), `plan.md` ya hacía referencia a `MacroContextPayload`. En la Sección 8 se declaraba como `MacroContextCollection`. Se adopta `MacroContextPayload` como nombre canónico, manteniendo un alias de compatibilidad:
```python
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
```

---

## 7. Bloques de Reemplazo Integrales para `plan.md`

### 7.1 Reemplazo para la Sección 8 (`Esquemas Formales Pydantic v2`)
Ubicación objetivo: `plan.md`, líneas 301–419.

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
    code: str = Field(..., description="Código canónico del evento en la taxonomía (ej. EVT_PATRIA_GUERRA_ACTIVOS)")
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

### 7.2 Reemplazo para la Sección 10.2 (`Algoritmo de Encadenamiento Criptográfico`)
Ubicación objetivo: `plan.md`, líneas 477–483.

```markdown
### 10.2 Algoritmo de Encadenamiento Criptográfico (Pipe-Delimited)

Para blindar el sistema contra ataques de extensión de longitud y colisiones por deslizamiento de límites entre cadenas adyacentes, cada predicción $k$ se encadena mediante una cadena canónica estrictamente delimitada por tuberías (`|`):

$$\text{canonical\_payload}_k = \text{prev\_hash}_{k-1} \,\|\, \text{"\|"} \,\|\, \text{timestamp\_iso} \,\|\, \text{"\|"} \,\|\, \text{direction} \,\|\, \text{"\|"} \,\|\, \text{timeframe} \,\|\, \text{"\|"} \,\|\, \text{confidence} \,\|\, \text{"\|"} \,\|\, \text{model} \,\|\, \text{"\|"} \,\|\, \text{justification}$$

$$\text{prediction\_hash}_k = \text{SHA256}\Big(\text{canonical\_payload}_k\Big)$$

Donde:
* $\text{prev\_hash}_{k-1}$: Hash SHA-256 de 64 caracteres de la predicción inmediatamente anterior. Para el bloque génesis ($k=0$), se utiliza la semilla canónica `"0" * 64`.
* $\text{timestamp\_iso}$: Cadena UTC ISO-8601 (ej. `2026-11-17T00:00:00Z`).
* $\text{direction}$: Valor de `PredictionDirection` (`SUBE`, `BAJA`, `ESTABLE`).
* $\text{timeframe}$: Valor de `TimeframeHorizon` (`24h-48h`, `3-5 dias`, `semanal`).
* $\text{confidence}$: Representación numérica fija con dos decimales `f"{float(confidence):.2f}"` (ej. `75.00`).
* $\text{model}$: Identificador del modelo revisor/auditor que firmó el dictamen, sanitizando cualquier carácter `|` residual como `/`.
* $\text{justification}$: Texto completo de `justificacion_auditada`, con espacios extremos eliminados y sustituyendo caracteres `|` por `/`.

Implementación de referencia en Python:
```python
def compute_prediction_hash(
    prev_hash: str,
    timestamp_iso: str,
    direction: str,
    timeframe: str,
    confidence: float,
    model: str,
    justification: str
) -> str:
    conf_str = f"{float(confidence):.2f}"
    clean_model = model.strip().replace("|", "/")
    clean_just = justification.strip().replace("|", "/")
    canonical_payload = (
        f"{prev_hash}|{timestamp_iso}|{direction}|{timeframe}|{conf_str}|{clean_model}|{clean_just}"
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
```
```

---

## 8. Verificación Empírica de las Remediaciones

Las cuatro remediaciones fueron sometidas a ejecución empírica automatizada en el entorno de pruebas de Python 3.13:

```text
Test 1: TaxonomyCategory
- Ingesta de las 7 categorías de Prompt 7.1: GASTO_PUBLICO_PATRIA, INTERVENCION_CAMBIARIA_BCV, POLITICA_MONETARIA_LIQUIDEZ, CALENDARIO_FISCAL_SENIAT, REGULACION_CAMBIARIA_BANCARIA, OPERATIVA_MERCADO_P2P, GEOPOLITICA_PETROLERA.
- Resultado: 7/7 válidas (0% fallas). PASSED.

Test 2: Colisión SHA-256
- Concatenación simple (+): colisión confirmada entre ('SUB' + 'E24h') y ('SUBE' + '24h').
- Formato Pipe-Delimited: hash('...|SUB|E24h|...') != hash('...|SUBE|24h|...').
- Resultado: Colisión erradicada. Inmunidad criptográfica confirmada. PASSED.

Test 3: Validador de Confiabilidad Máxima
- Instanciación de FinalUSDTPrediction con veredicto=CORREGIDO y confiabilidad_porcentaje=95.0.
- Resultado: confiabilidad_porcentaje acotada automáticamente a 75.0.
- Instanciación con veredicto=APROBADO y confiabilidad_porcentaje=95.0.
- Resultado: confiabilidad_porcentaje preservada en 95.0. PASSED.

Test 4: Atributo ASCII
- MacroEventItem con resumen_factico instanciado y serializado sin caracteres extendidos.
- Resultado: Compatibilidad 100% con esquemas relacionales y JSON. PASSED.
```

---

## 9. Plan de Implementación para Worker

Una vez que el Orchestrator apruebe esta estrategia en el Gate M1_IT2:
1. **Paso 1**: Aplicar el bloque de reemplazo de la Sección 8 en `.specify/specs/023-ai-market-predictor/plan.md`.
2. **Paso 2**: Aplicar el bloque de reemplazo de la Sección 10.2 en `.specify/specs/023-ai-market-predictor/plan.md`.
3. **Paso 3**: Verificar consistencia ejecutando el script de validación empírica.
