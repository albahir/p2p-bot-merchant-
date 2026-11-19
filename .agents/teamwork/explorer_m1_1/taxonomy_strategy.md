# Estrategia y Blueprint Técnico para `docs/macro_usdt_taxonomy.md`

**Documento:** Plan de Contenido, Modelado Matemático y Taxonomía Canónica de Impacto Macroeconómico USDT/VES  
**Autor:** Explorer M1_1 (Macro Taxonomy Strategist)  
**Destino:** Worker M1_1 y Orquestador de Arquitectura  
**Fecha:** 2026-11-17  
**Estado:** ESTRATEGIA APROBADA — LISTA PARA REDACCIÓN  

---

## 1. Resumen Ejecutivo y Alcance Estratégico

El objetivo de esta estrategia es proveer al Worker M1_1 el diseño integral, riguroso y ejecutable para redactar el documento canónico `docs/macro_usdt_taxonomy.md`. 

En la economía venezolana, la cotización **USDT/VES** en Binance P2P representa el mercado libre más líquido, eficiente y continuo (24/7) de formación de precios. Dicho mercado opera bajo una dinámica de oferta y demanda altamente sensible a:
1. **Inyecciones fiscales de liquidez en bolívares** (subsidios del Sistema Patria, bonificaciones indexadas, aguinaldos y nóminas públicas).
2. **Intervenciones cambiarias del Banco Central de Venezuela (BCV)** que colocan divisas extranjeras en la banca nacional.
3. **Restricciones estacionales de liquidez tributaria** (obligaciones del SENIAT en bolívares).
4. **Fricciones operativas del sistema bancario nacional** (lunes bancarios SUDEBAN, límites de Pago Móvil, incidencias de compensación).
5. **Régimen geopolítico y flujo de caja petrolero** (licencias OFAC y exportaciones de hidrocarburos).

El documento resultante (`docs/macro_usdt_taxonomy.md`) servirá de base conceptual, matemática y operativa para todo el subsistema `023-ai-market-predictor`, guiando tanto al **Buscador/Recopilador** (extracción y clasificación de eventos), al **Analista/Predictor** (ponderación causal y cálculo de probabilidades) como al **Revisor/Auditor** (verificación de consistencia y salvaguardas Fail-Closed).

---

## 2. Estructura y Esquema Detallado de `docs/macro_usdt_taxonomy.md`

El Worker M1_1 deberá estructurar el archivo final `docs/macro_usdt_taxonomy.md` siguiendo estrictamente el siguiente índice de ocho secciones:

```
docs/macro_usdt_taxonomy.md
├── 1. Fundamentos del Mercado USDT/VES en Venezuela
│   ├── 1.1 Doble Rol del USDT: Activo de Cobertura y Medio de Liquidación 24/7
│   ├── 1.2 Formación de Precios: Tasa Oficial BCV vs Binance P2P
│   └── 1.3 Dinámica de la Brecha Cambiaria y Regímenes de Volatilidad
├── 2. Modelado Matemático de Fuerzas Macroeconómicas
│   ├── 2.1 Ecuación de Brecha Cambiaria Porcentual
│   ├── 2.2 Micro-Spreads y Jerarquía por Método de Liquidación Bancaria
│   ├── 2.3 Formulación Vectorial de Fuerza Macroeconómica Neta (F_net)
│   ├── 2.4 Funciones de Activación y Decaimiento Temporal (Half-Life Formulation)
│   └── 2.5 Algoritmo de Calibración de Confianza, Coherencia y Ambigüedad
├── 3. Taxonomía Canónica de 14 Eventos Macroeconómicos
│   ├── 3.1 Tabla Maestra Canónica (14 Códigos Normalizados)
│   └── 3.2 Fichas Técnicas Descriptivas por Evento (EVT_01 al EVT_14)
├── 4. Matriz Cuantitativa de Rezagos Temporales (Lag Matrix)
│   ├── 4.1 Horizontes de Propagación: T+0, T+1, T+3 y T+7
│   └── 4.2 Respuestas al Impulso y Persistencia de Shocks (Transitorio vs Escalón)
├── 5. Catálogo de Fuentes de Datos e Ingesta Técnica
│   ├── 5.1 Inventario de Fuentes Primarias, Secundarias y Agregadores
│   ├── 5.2 Matriz de Factibilidad, Latencia y Canales de Ingesta
│   └── 5.3 Filosofía Fail-Closed y Resiliencia ante Caídas de Fuentes
├── 6. Protocolo de Resolución de Interferencias y Choques Contrapuestos
│   ├── 6.1 Interferencia de Fuerzas Simultáneas (Intervención BCV vs Bonos Patria)
│   └── 6.2 Reglas Heurísticas y Matriz de Decisión para el Predictor y Auditor
├── 7. Esquemas Formales de Datos para el Pipeline de IA (Pydantic v2)
│   ├── 7.1 Enums Canónicos (Categoría, Dirección, Criticidad, Ventana)
│   └── 7.2 Modelos de Evento y Snapshot Macroeconómico
└── 8. Guía de Mantenimiento, Gobernanza y Calibración Continua
```

---

## 3. Especificación Rigurosa de los Modelos Matemáticos

El Worker M1_1 debe plasmar con exactitud las siguientes formulaciones matemáticas en la Sección 2 del documento.

### 3.1 Ecuación de Brecha Cambiaria y Regímenes de Mercado

La brecha cambiaria porcentual ($B_t$) mide la disparidad relativa entre la cotización libre en Binance P2P ($P_t^{\text{P2P}}$) y el tipo de cambio oficial reportado por el BCV ($P_t^{\text{BCV}}$):

$$B_t = \left( \frac{P_t^{\text{P2P}} - P_t^{\text{BCV}}}{P_t^{\text{BCV}}} \right) \times 100$$

Regímenes de mercado determinados por $B_t$:
* **Régimen I — Calma / Equilibrio Institucional ($B_t < 8.0\%$):** Oferta suficiente de divisas en mesas de cambio bancarias; bajo incentivo para arbitraje informal; mercado P2P opera con volatilidad baja.
* **Régimen II — Fricción Moderada ($8.0\% \le B_t < 15.0\%$):** Demanda corporativa no satisfecha en la banca; comercios formales sufren presión en reposición de inventarios; spreads P2P se amplían de forma gradual.
* **Régimen III — Tensión Severa / Racionamiento ($15.0\% \le B_t < 25.0\%$):** Racionamiento severo de divisas en la banca; proliferación de arbitraje cruzado; retención defensiva de inventario en USDT por parte de comerciantes.
* **Régimen IV — Desalineación Crítica / Ruptura ($B_t \ge 25.0\%$):** Fallo del mecanismo oficial de asignación; riesgo inminente de paralización de ventas minoristas por fiscalizaciones SUNDDE; volatilidad extrema intradía en Binance P2P.

### 3.2 Micro-Spreads y Ponderación por Método de Liquidación

El precio P2P efectivo no es un escalar único sino una función del método de pago bancario $m \in M$:

$$P_t^{\text{P2P}} = \sum_{m \in M} \omega_m \cdot P_{t, m}^{\text{P2P}}$$

Donde los métodos y sus pesos de liquidez empíricos son:
1. **Banesco y Pago Móvil Interbancario ($\omega_{\text{Banesco}} = 0.55$):** Mercado de referencia nacional, mayor volumen y liquidez inmediata ($24/7$).
2. **Banco de Venezuela ($\omega_{\text{BDV}} = 0.30$):** Canal primario de dispersión de fondos públicos (Patria, nóminas del Estado); presenta diferenciales de $+0.3\%$ a $+1.0\%$ en picos de bonos.
3. **Otros Bancos Privados (Mercantil, BBVA Provincial, Bancamiga) ($\omega_{\text{Otros}} = 0.15$):** Menor profundidad de libro, spreads bid-ask más anchos.

### 3.3 Formulación Vectorial de Fuerza Macroeconómica Neta ($F_{\text{net}}$)

Sea $\mathcal{E}_t = \{e_1, e_2, \dots, e_N\}$ el conjunto de eventos macroeconómicos activos detectados en la ventana rodante de análisis $W$ (donde $W = 7$ días = 168 horas).

Para cada evento $e_i \in \mathcal{E}_t$:
- $d_i \in \{+1.0, -1.0, 0.0\}$: Dirección intrínseca del evento sobre el precio USDT/VES ($+1.0$: Depreciación del VES / Subida del USDT; $-1.0$: Apreciación o contención del VES / Bajada del USDT; $0.0$: Neutral / Volatilidad pura).
- $w_i \in [0.10, 1.00]$: Peso base o magnitud intrínseca del evento.
- $c_i \in (0.0, 1.0]$: Factor de confianza o certeza de la fuente (ej. $1.0$ para Gaceta Oficial / BCV verificado; $0.85$ para portales especializados como Banca y Negocios; $0.70$ para alertas de redes sociales o Telegram).
- $\Delta t_i = t - t_i \ge 0$: Horas transcurridas desde la emisión u ocurrencia del evento.
- $L_i \ge 0$: Latencia o retraso empírico de transmisión hasta el libro de órdenes (en horas).
- $h_i > 0$: Semivida (*half-life*) de decaimiento del impacto (en horas).

#### 3.3.1 Función de Activación de Propagación ($\alpha_i$)

Los eventos macroeconómicos no impactan instantáneamente al 100%; requieren un periodo de transmisión bancaria y psicológica:

$$\alpha_i(\Delta t_i) = \begin{cases}
\frac{\Delta t_i}{L_i} & \text{si } L_i > 0 \text{ y } \Delta t_i < L_i \\
1.0 & \text{si } \Delta t_i \ge L_i
\end{cases}$$

#### 3.3.2 Función de Decaimiento Temporal ($D_i$)

El decaimiento posterior al inicio del impacto sigue un proceso exponencial gobernado por la constante de decaimiento $\lambda_i = \frac{\ln(2)}{h_i}$:

$$D_i(\Delta t_i) = \exp\left( -\frac{\ln(2)}{h_i} \cdot \max(0, \Delta t_i - L_i) \right)$$

#### 3.3.3 Fuerza Efectiva Instantánea ($F_i(t)$)

$$F_i(t) = d_i \cdot w_i \cdot c_i \cdot \alpha_i(\Delta t_i) \cdot D_i(\Delta t_i)$$

#### 3.3.4 Fuerza Neta Macroeconómica ($F_{\text{net}}(t)$)

$$F_{\text{net}}(t) = \sum_{i=1}^N F_i(t) = \sum_{i=1}^N d_i \cdot w_i \cdot c_i \cdot \alpha_i(\Delta t_i) \cdot \exp\left( -\frac{\ln(2)}{h_i} \cdot \max(0, \Delta t_i - L_i) \right)$$

### 3.4 Algoritmo de Calibración de Confianza, Coherencia y Ambigüedad

Para transformar $F_{\text{net}}(t)$ en una predicción estructurada con dirección y confianza probabilística:

#### 3.4.1 Masa de Fuerza Bruta ($F_{\text{gross}}(t)$)

$$F_{\text{gross}}(t) = \sum_{i=1}^N w_i \cdot c_i \cdot \alpha_i(\Delta t_i) \cdot D_i(\Delta t_i)$$

#### 3.4.2 Índice de Coherencia Direccional ($\text{Coh}(t)$)

Mide si las fuerzas macroeconómicas apuntan en la misma dirección o si están en conflicto abierto:

$$\text{Coh}(t) = \begin{cases}
\frac{|F_{\text{net}}(t)|}{F_{\text{gross}}(t)} & \text{si } F_{\text{gross}}(t) > 0 \\
0.0 & \text{si } F_{\text{gross}}(t) = 0
\end{cases}$$

* Si todos los eventos son alcistas: $\text{Coh}(t) = 1.0$ (Concordancia total).
* Si una intervención bajista ($w=0.8$) choca contra un bono alcista ($w=0.8$): $|0.8 - 0.8| / 1.6 = 0.0$ (Ambigüedad total / Choque nulo).

#### 3.4.3 Índice de Cobertura de Evidencia ($\text{Cov}(t)$)

Garantiza que un único evento menor no genere una falsa confianza del 100%:

$$\text{Cov}(t) = \min\left(1.0, \frac{F_{\text{gross}}(t)}{\Omega_{\text{ref}}}\right)$$

Donde $\Omega_{\text{ref}} = 1.50$ es la masa mínima de referencia de eventos requerida para considerar un mercado plenamente fundamentado.

#### 3.4.4 Determinación de la Dirección

Con un umbral direccional calibrado $\theta = 0.25$:

$$\text{Dirección Proyectada} = \begin{cases}
\text{SUBE} & \text{si } F_{\text{net}}(t) > +\theta \\
\text{BAJA} & \text{si } F_{\text{net}}(t) < -\theta \\
\text{ESTABLE / LATERAL} & \text{si } |F_{\text{net}}(t)| \le \theta
\end{cases}$$

#### 3.4.5 Cálculo de Confianza Calibrada ($C_t \in [0, 100\%]$)

$$C_t = \left( \gamma_1 \cdot \text{Coh}(t) + \gamma_2 \cdot \text{Cov}(t) \right) \times 100$$

Parámetros calibrados:
* $\gamma_1 = 0.65$ (Ponderación de coherencia interna de fuerzas).
* $\gamma_2 = 0.35$ (Ponderación de volumen y solidez de evidencia).

**Salvaguarda Fail-Closed:**  
Si $F_{\text{gross}}(t) < 0.20$ o si $\text{Coh}(t) < 0.20$ con $F_{\text{gross}}(t) > 1.0$, el sistema **DEBE** forzar el veredicto a:
* Dirección: `ESTABLE`
* Confianza: $\le 45.0\%$
* Flag de Advertencia: `HIGH_AMBIGUITY_COLLIDING_FORCES` o `INSUFFICIENT_MACRO_EVIDENCE`.

---

## 4. Taxonomía Canónica de 14 Eventos Macroeconómicos

El Worker M1_1 debe plasmar íntegramente la siguiente tabla maestra de 14 eventos normalizados con sus atributos canónicos, seguida de las fichas técnicas individuales.

### 4.1 Tabla Maestra Canónica de 14 Eventos

| Código Canónico | Nombre del Evento | Categoría | Condición Disparadora | Dir. ($d_i$) | Peso ($w_i$) | Canal de Transmisión | Latencia ($L_i$) | Semivida ($h_i$) | Fuente Primaria | Fuente Fallback |
| :--- | :--- | :--- | :--- | :---: | :---: | :--- | :---: | :---: | :--- | :--- |
| `EVT_PATRIA_GUERRA_ACTIVOS` | Bono Guerra Económica: Activos y Cestaticket | `GASTO_PUBLICO_PATRIA` | Inicio de abono mensual días 12-15 en BDV/Patria | **+1 (SUBE)** | 0.90 | Acreditación bancaria BDV $\rightarrow$ Pago Móvil $\rightarrow$ Fuerte compra retail USDT | 1.0 h | 36.0 h | Telegram `@PatriaDigital` | Blog Patria / X `@BonosSocial` |
| `EVT_PATRIA_GUERRA_JUBILADOS` | Bono Guerra Económica: Jubilados y Pensionados | `GASTO_PUBLICO_PATRIA` | Inicio de abono mensual días 16-22 en Patria | **+1 (SUBE)** | 0.65 | Monederos Patria $\rightarrow$ Retiro bancario $\rightarrow$ Consumo y cobertura familiar | 2.0 h | 24.0 h | Telegram `@PatriaDigital` | Blog Patria / X `@CarnetDLaPatria` |
| `EVT_PATRIA_AGUINALDOS_FRAC` | Desembolso de Fracción de Aguinaldos Públicos | `GASTO_PUBLICO_PATRIA` | Anuncio / Ejecución de cuotas de fin de año (Oct-Dic) | **+1 (SUBE)** | 1.00 | Inyección masiva de masa monetaria no respaldada $\rightarrow$ Vaciado de liquidez comercial | 1.5 h | 72.0 h | MPPEF / Medios Financieros | Canales Gremiales / Banca y Negocios |
| `EVT_BCV_INTERVENCION_REGULAR` | Intervención Cambiaria Semanal Ordinaria ($50M-$90M) | `INTERVENCION_CAMBIARIA_BCV` | Adjudicación cambiaria de lunes en rango regular | **-1 (BAJA)** | 0.70 | Asignación de divisas a bancos comerciales $\rightarrow$ Drenaje de encaje en VES $\rightarrow$ Cobertura corporativa | 2.0 h | 36.0 h | Banca y Negocios | Portal Oficial BCV |
| `EVT_BCV_INTERVENCION_AGRESIVA` | Intervención Extraordinaria / Shock (> $120M) | `INTERVENCION_CAMBIARIA_BCV` | Asignación semanal acumulada > $120M o extensión jueves | **-1 (BAJA)** | 0.95 | Sobreoferta institucional de USD en mesas bancarias $\rightarrow$ Parálisis temporal de compras P2P | 1.0 h | 48.0 h | Portal Oficial BCV | Banca y Negocios |
| `EVT_BCV_INTERVENCION_DEFICIT` | Intervención Restringida / Insuficiente (< $40M) | `INTERVENCION_CAMBIARIA_BCV` | Monto semanal adjudicado menor a $40M | **+1 (SUBE)** | 0.85 | Déficit de cobertura en mesas bancarias $\rightarrow$ Desvío compulsivo de importadores a Binance P2P | 3.0 h | 40.0 h | Banca y Negocios | Finanzas Digital |
| `EVT_BCV_LIQUIDEZ_M2_SPIKE` | Expansión Semanal Acelerada de Liquidez M2 (> 3.5%) | `POLITICA_MONETARIA_LIQUIDEZ` | Reporte viernes BCV muestra $\Delta \text{M2} > 3.5\%$ semanal | **+1 (SUBE)** | 0.60 | Ajuste de expectativas de tesorerías corporativas y formadores de mercado P2P | 12.0 h | 96.0 h | BCV (Estadísticas M2) | Finanzas Digital / OVF |
| `EVT_SENIAT_PAGO_QUINCENA` | Vencimiento Anticipos IVA/ISLR Especiales | `CALENDARIO_FISCAL_SENIAT` | Días 18-25 del mes; vencimiento según calendario RIF | **-1 (BAJA)** | 0.65 | Obligación ineludible de pago en VES $\rightarrow$ Venta forzada de USDT por empresas para pagar al fisco | 0.5 h (anticipado) | 24.0 h | Calendario SENIAT en Gaceta | Portal Fiscal SENIAT |
| `EVT_SENIAT_ZAFRA_ISLR_MAR` | Cierre de Zafra Anual ISLR (Marzo) | `CALENDARIO_FISCAL_SENIAT` | Periodo 15 al 31 de marzo; cierre del ejercicio fiscal | **-1 (BAJA)** | 0.85 | Drenaje histórico colosal de bolívares hacia el Tesoro Nacional $\rightarrow$ Sequía de VES interbancario | 24.0 h (anticipado) | 120.0 h | SENIAT Oficial | Medios Nacionales |
| `EVT_SUDEBAN_LUNES_BANCARIO` | Feriado Bancario Nacional / Lunes Bancario SUDEBAN | `OPERATIVA_MERCADO_P2P` | Calendario bancario oficial SUDEBAN activo en día hábil | **0 (NEUTRAL)** | 0.50 | Cierre de mesas de cambio bancarias; el 100% del intercambio opera en P2P (spread se ensancha) | 0.0 h | 18.0 h | Calendario SUDEBAN | SUDEBAN en X (`@SudebanInforma`) |
| `EVT_OFAC_LICENCIA_RENOVADA` | Renovación / Ampliación Licencia Petrolera OFAC | `GEOPOLITICA_PETROLERA` | Emisión de General License (GL44, GL41 o similar) por US Treasury | **-1 (BAJA)** | 0.90 | Incremento de expectativas de caja de divisas para el BCV $\rightarrow$ Calma y compresión de la prima de riesgo | 2.0 h | 168.0 h | US Department of Treasury (OFAC) | Agencias (Reuters / Bloomberg) |
| `EVT_OFAC_LICENCIA_REVOCADA` | Revocación o Vencimiento sin Prórroga de Licencia | `GEOPOLITICA_PETROLERA` | Cancelación o reimposición de sanciones energéticas | **+1 (SUBE)** | 1.00 | Anticipación de insolvencia de caja en divisas del BCV $\rightarrow$ Huida masiva hacia activos estables (USDT) | 1.0 h | 240.0 h | US Department of Treasury (OFAC) | Prensa Internacional / Medios Financieros |
| `EVT_REGULACION_FISCALIZACION` | Operativos SUNDDE/SENIAT sobre Tasa Oficial | `REGULACION_CAMBIARIA_BANCARIA` | Despliegue de inspecciones a comercios con multas | **+1 (SUBE)** | 0.70 | Miedo a transar en bolívares a tasa oficial $\rightarrow$ Retención de dólares/USDT $\rightarrow$ Mercado negro se aísla y sube | 4.0 h | 48.0 h | Min. Comercio / SUNDDE | Medios Nacionales |
| `EVT_CAIDA_PAGO_MOVIL_NAC` | Incidencia Crítica en Plataforma Interbancaria | `OPERATIVA_MERCADO_P2P` | Caída de Suiche 7B, Biopago o fallas eléctricas masivas | **0 (NEUTRAL)** | 0.55 | Imposibilidad técnica de liquidar órdenes P2P en VES $\rightarrow$ Parálisis de volumen y ampliación de spread | 0.1 h | 6.0 h | Redes de Monitoreo / Usuarios | Canales de Banca Digital |

---

## 5. Matriz Cuantitativa de Rezagos Temporales (Lag Matrix)

El Worker M1_1 debe detallar el comportamiento del choque en cuatro horizontes canónicos:
- **$T+0$ (Intradía 0 - 6 horas):** Reacción inmediata en libros de órdenes de Binance P2P, absorción inicial de liquidez y ampliación de spread bid-ask.
- **$T+1$ (24 horas):** Absorción en el sistema bancario, clearing de transferencias masivas y liquidación comercial retail.
- **$T+3$ (72 horas):** Reposición de inventarios comerciales, respuesta defensiva del BCV y efecto acumulativo en precios.
- **$T+7$ (Semanal / Tendencial):** Consolidación en agregados monetarios (M2), absorción completa del shock y establecimiento de un nuevo piso nominal de equilibrio.

### 5.1 Matriz de Horizontes y Persistencia del Choque

| Código de Evento | Impacto en $T+0$ (0-6h) | Impacto en $T+1$ (24h) | Impacto en $T+3$ (72h) | Impacto en $T+7$ (Semanal) | Naturaleza del Shock |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `EVT_PATRIA_GUERRA_ACTIVOS` | Presión compradora inicial (+0.4% a +1.0%) | Pico de subida (+1.5% a +2.5%) | Decaimiento leve, estabilización en nuevo piso | Reversión marginal (queda escalón nominal) | **Escalón Permanente Parcial** |
| `EVT_PATRIA_GUERRA_JUBILADOS` | Neutral / Dispersión lenta | Subida gradual (+0.5% a +1.2%) | Decaimiento casi total | Totalmente absorbido | **Transitorio** |
| `EVT_PATRIA_AGUINALDOS_FRAC` | Shock de compra explosivo (+1.5% a +3.0%) | Máxima aceleración (+3.0% a +6.0%) | Presión sostenida por reposición de stock | Nuevo piso nominal inamovible | **Escalón Permanente Total** |
| `EVT_BCV_INTERVENCION_REGULAR` | Contención inmediata (-0.5% a -1.2%) | Estabilización / Frenazo del rally | Agotamiento del efecto; reactivación de demanda | Tasa retoma tendencia previa | **Transitorio de Corto Plazo** |
| `EVT_BCV_INTERVENCION_AGRESIVA` | Retroceso marcado (-1.5% a -3.0%) | Contención severa y compresión de brecha | Inicio de rebote técnico lento | Tasa retoma ascenso si M2 no cesa | **Transitorio de Mediano Plazo** |
| `EVT_BCV_INTERVENCION_DEFICIT` | Alerta en tesorerías; subida incipiente | Aceleración de compra (+1.0% a +2.0%) | Presión alcista sostenida en P2P | Brecha cambiaria se consolida al alza | **Persistente** |
| `EVT_BCV_LIQUIDEZ_M2_SPIKE` | Sin impacto perceptible | Filtrado en modelos analíticos | Desplazamiento progresivo de órdenes | Correlación del 92% con devaluación efectiva | **Estructural Acumulativo** |
| `EVT_SENIAT_PAGO_QUINCENA` | Oferta corporativa de USDT activa | Caída moderada o freno (-0.8% a -1.5%) | Rebote vigoroso al cesar la obligación fiscal | Sin rastro bajista en la tendencia semanal | **Transitorio con Rebote Inmediato** |
| `EVT_SENIAT_ZAFRA_ISLR_MAR` | Apreciación sostenida del VES | Sequía extrema de liquidez en bolívares | Mínimo mensual de volatilidad cambiaria | Repunte explosivo a partir del 5 de abril | **Estacional Cíclico Prolongado** |
| `EVT_SUDEBAN_LUNES_BANCARIO` | Spread bid-ask se amplía al 2.5% - 4.0% | Normalización al abrir la banca el martes | Cero impacto residual | Cero impacto residual | **Puro Friccional Intradía** |
| `EVT_OFAC_LICENCIA_RENOVADA` | Caída de prima de riesgo (-2.0% a -4.0%) | Aplanamiento de la curva de depreciación | Expectativas optimistas de oferta de divisas | Estabilidad cambiaria multimensual | **Cambio de Régimen Macroeconómico** |
| `EVT_OFAC_LICENCIA_REVOCADA` | Pánico comprador instantáneo (+3.0% a +8.0%) | Desconexión entre tasa BCV y P2P | Disparada de la brecha por encima del 25% | Régimen inflacionario acelerado | **Cambio de Régimen Estructural** |
| `EVT_REGULACION_FISCALIZACION` | Retiro de anuncios de venta en P2P | Mercado formal congelado; P2P sube | Distorsión de precios y sobreprecio en USDT | Normalización o asimilación de riesgo | **Shock Regulatorio Asimétrico** |
| `EVT_CAIDA_PAGO_MOVIL_NAC` | Congelamiento de transacciones P2P | Sin impacto direccional una vez restaurado | Cero impacto | Cero impacto | **Falla Operativa No Direccional** |

---

## 6. Catálogo de Fuentes de Datos e Ingesta Técnica

El Worker M1_1 debe estructurar el catálogo técnico especificando canales, protocolos y mecanismos defensivos de captura.

### 6.1 Especificación Técnica de Fuentes de Datos

```
+----------------------------------------------------------------------------------------------------+
| FUENTE 1: Banco Central de Venezuela (BCV Oficial)                                                 |
| - URL: https://www.bcv.org.ve                                                                      |
| - Datos Extraídos: Tipos de cambio oficiales (USD, EUR), Fecha Valor, Informes semanales de M2     |
| - Protocolo: Web Scraping HTTPS defensivo vía httpx (Requiere verify=False por fallos SSL del BCV) |
| - Latencia: 1 a 5 minutos tras publicación (14:30 - 17:30 VET)                                     |
| - Fallback: Cuenta oficial en X (@BCV_ORG_VE) / Canal Telegram @BCV_Oficial                       |
+----------------------------------------------------------------------------------------------------+
| FUENTE 2: Ecosistema Sistema Patria                                                                |
| - URL: https://blog.patria.org.ve                                                                  |
| - Canales Clave: Telegram (@PatriaDigital, @BonosSocial), X (@CarnetDLaPatria)                     |
| - Datos Extraídos: Montos exactos, inicio de adjudicación de Bonos de Guerra y Aguinaldos          |
| - Protocolo: Telethon / MTProto Client para Telegram push (< 30s) + RSS feed del blog oficial      |
| - Latencia: Push casi instantáneo (< 45 segundos tras emisión del SMS del 3532)                    |
| - Fallback: Portal Patria Blog / Medios agregadores nacionales                                    |
+----------------------------------------------------------------------------------------------------+
| FUENTE 3: Portales de Inteligencia Financiera (Banca y Negocios, Finanzas Digital)                |
| - URL: https://www.bancaynegocios.com / https://www.finanzasdigital.com                             |
| - Datos Extraídos: Montos exactos de intervención cambiaria BCV (cada lunes y jueves), inflación    |
| - Protocolo: Parseo de RSS Feeds (/feed) + HTTP Headless Scraping con rotación de User-Agent       |
| - Latencia: 5 a 15 minutos tras el comunicado                                                      |
| - Fallback: Síntesis de noticias en Descifrado / Efecto Cocuyo                                     |
+----------------------------------------------------------------------------------------------------+
| FUENTE 4: SENIAT (Portal y Gaceta Oficial)                                                         |
| - URL: http://declaraciones.seniat.gob.ve                                                          |
| - Datos Extraídos: Calendario oficial de Sujetos Pasivos Especiales (SPE), prórrogas tributarias   |
| - Protocolo: Ingesta estática anual en base de datos relacional + Web polling mensual de avisos    |
| - Latencia: 24h previas al inicio de cada ciclo fiscal quincenal                                   |
| - Fallback: Consultas a firmas tributarias / Gaceta Oficial de la República Bolivariana            |
+----------------------------------------------------------------------------------------------------+
| FUENTE 5: Binance P2P Public Ticker & Orderbook                                                    |
| - Endpoint: POST https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search                       |
| - Datos Extraídos: Mejores 5 órdenes Buy/Sell para USDT/VES (filtrado por Banesco, BDV, PagoMóvil)|
| - Protocolo: Cliente httpx autenticado/asíncrono con User-Agent pool y circuit breaker             |
| - Latencia: 15 a 30 segundos                                                                       |
| - Fallback: Monitores agregadores (EnParaleloVzla, Yadio.io)                                       |
+----------------------------------------------------------------------------------------------------+
| FUENTE 6: Geopolítica y Regulaciones (US Treasury OFAC / SUDEBAN)                                 |
| - Portales: https://ofac.treasury.gov / https://www.sudeban.gob.ve                                 |
| - Datos Extraídos: Sanciones, licencias petroleras, resoluciones bancarias, feriados bancarios     |
| - Protocolo: RSS Readers + Scraping con reintentos Tenacity                                        |
| - Latencia: 10 a 30 minutos                                                                        |
| - Fallback: Agencias de prensa financiera internacional (Reuters, Bloomberg)                       |
+----------------------------------------------------------------------------------------------------+
```

### 6.2 Políticas Fail-Closed y Sanitización en Ingesta
1. **Cero Secretos en Ingesta:** Ninguna credencial de Telegram (API ID/Hash) ni cabeceras sensibles debe exponerse en registros de error o eventos auditados.
2. **Rechazo ante Fuentes Únicas Dudadas:** Noticias provenientes de cuentas no verificadas de redes sociales tienen factor de certeza $c_i = 0.0$ y son descartadas inmediatamente por el filtro anti-ruido del Buscador.
3. **Manejo de Caídas de Conectividad:** Si el portal del BCV falla o retorna 504/timeout, el sistema utiliza la última tasa confirmada auditada con su hash SHA-256 e incrementa la incertidumbre temporal sin inventar datos.

---

## 7. Protocolo de Resolución de Interferencias y Choques Contrapuestos

Uno de los aportes más críticos que el Worker M1_1 debe plasmar en la Sección 6 es el **manejo determinista de colisiones de señales**.

### 7.1 Matriz de Choques Típicos en Venezuela

| Escenario de Choque | Fuerza A (Magnitud / Dirección) | Fuerza B (Magnitud / Dirección) | Vector Resultante ($F_{\text{net}}$) | Comportamiento Esperado en Mercado |
| :--- | :--- | :--- | :---: | :--- |
| **Lunes de Intervención vs Pago de Bono Patria** | Intervención BCV Ordinaria ($w=0.70, d=-1$) | Asignación Bono Guerra ($w=0.90, d=+1$) | $+0.20$ (Levemente Alcista) | **Compresión inicial:** En las primeras 4h la intervención frena el precio; pasadas 6h la demanda masiva de bolívares supera la oferta de divisas bancarias y el USDT cierra al alza. |
| **Lunes de Intervención vs Pago de Aguinaldos** | Intervención BCV Agresiva ($w=0.95, d=-1$) | Fracción de Aguinaldos ($w=1.00, d=+1$) | $+0.05$ (Neutral / Fuerte Volatilidad) | **Tensión Explosiva:** Spread se dispara; el BCV agota rápidamente su cupo semanal y la tasa libre rompe al alza con fuerza a las 24-48h. |
| **Cierre Fiscal SENIAT vs Pago de Quincena Pública** | Vencimiento SENIAT SPE ($w=0.65, d=-1$) | Nómina Ordinaria Pública ($w=0.55, d=+1$) | $-0.10$ (Estable / Ligera Caída) | **Apatía / Lateralidad:** Las tesorerías privadas venden dólares para pagar tributos mientras los empleados compran USDT; las fuerzas se anulan temporalmente. |
| **Revocación de Licencia OFAC vs Megaintervención BCV** | Revocación OFAC ($w=1.00, d=+1$) | Inyección BCV $150M ($w=0.95, d=-1$) | $+0.05$ (Dirección estructural ALCISTA) | **Pánico estructural domina sobre liquidez inmediata:** La intervención solo frena la subida 24h; el mercado descuenta la escasez futura de dólares. |

### 7.2 Reglas de Decisión para el Analista/Predictor y Revisor/Auditor

1. **Regla de Asimetría Fiscal/Cambiaria de Venezuela:**  
   *En el horizonte mayor a 24 horas, la emisión inorgánica de bolívares para gasto público siempre supera la capacidad del BCV para contener el tipo de cambio mediante reservas.*
2. **Regla de Contención Transitoria:**  
   *Si una intervención del BCV ocurre dentro de las últimas 6 horas ($\Delta t \le 6\text{h}$), el modelo DEBE emitir advertencia de "Frenado o Rebote de Corto Plazo" aun cuando la proyección de 48 horas sea fuertemente ALCISTA.*
3. **Regla de Indeterminación y Veredicto Fail-Closed:**  
   *Si el índice de coherencia $\text{Coh}(t) < 0.25$ con una masa total $F_{\text{gross}}(t) \ge 1.40$, el Predictor y el Revisor tienen prohibido emitir un llamado especulativo direccional. El veredicto DEBE ser `ESTABLE / AMBIGUO` con recomendación de abstención o ampliación de márgenes de spread en el bot.*

---

## 8. Esquemas Formales de Datos Pydantic v2

El Worker M1_1 debe incluir en la Sección 7 las definiciones formales completas de Pydantic v2 que implementarán los contratos de datos entre los roles del pipeline.

```python
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class MacroCategoryEnum(str, Enum):
    GASTO_PUBLICO_PATRIA = "GASTO_PUBLICO_PATRIA"
    INTERVENCION_CAMBIARIA_BCV = "INTERVENCION_CAMBIARIA_BCV"
    POLITICA_MONETARIA_LIQUIDEZ = "POLITICA_MONETARIA_LIQUIDEZ"
    CALENDARIO_FISCAL_SENIAT = "CALENDARIO_FISCAL_SENIAT"
    REGULACION_CAMBIARIA_BANCARIA = "REGULACION_CAMBIARIA_BANCARIA"
    OPERATIVA_MERCADO_P2P = "OPERATIVA_MERCADO_P2P"
    GEOPOLITICA_PETROLERA = "GEOPOLITICA_PETROLERA"


class DirectionEnum(str, Enum):
    SUBE = "SUBE"
    BAJA = "BAJA"
    ESTABLE = "ESTABLE"


class CriticalityEnum(str, Enum):
    BAJO = "BAJO"
    MEDIO = "MEDIO"
    ALTO = "ALTO"
    CRITICO = "CRITICO"


class ImpactWindowEnum(str, Enum):
    INMEDIATO_0_6H = "INMEDIATO_0_6H"
    CORTO_PLAZO_24H = "CORTO_PLAZO_24H"
    MEDIANO_PLAZO_72H = "MEDIANO_PLAZO_72H"
    SEMANAL_TENDENCIAL = "SEMANAL_TENDENCIAL"


class MacroEventItem(BaseModel):
    """Representación normalizada de un evento macroeconómico capturado por el Buscador."""
    event_id: str = Field(..., description="Identificador único, e.g., EVT-202611-BCV-INT-001")
    code: str = Field(..., description="Código canónico de la taxonomía de 14 eventos")
    category: MacroCategoryEnum
    name: str = Field(..., min_length=5, max_length=150)
    trigger_timestamp_utc: datetime
    source_name: str
    source_channel: str
    source_confidence: float = Field(ge=0.0, le=1.0)
    criticality: CriticalityEnum
    base_weight: float = Field(ge=0.10, le=1.00)
    vector_direction: int = Field(..., description="+1 para alcista, -1 para bajista, 0 para neutral")
    latency_hours: float = Field(ge=0.0)
    half_life_hours: float = Field(gt=0.0)
    expected_window: ImpactWindowEnum
    summary_verified: str = Field(..., max_length=500)
    raw_attributes: Dict[str, float | str | int | bool] = Field(default_factory=dict)

    @field_validator("vector_direction")
    @classmethod
    def validate_direction(cls, v: int) -> int:
        if v not in (-1, 0, 1):
            raise ValueError("vector_direction debe ser -1, 0 o 1")
        return v


class MarketRateSnapshot(BaseModel):
    """Instantánea de precios de mercado al momento del análisis."""
    timestamp_utc: datetime
    p2p_rate_ves: float = Field(gt=0.0)
    bcv_rate_ves: float = Field(gt=0.0)
    brecha_porcentual: float
    spread_banesco_pct: Optional[float] = None
    spread_bdv_pct: Optional[float] = None


class VectorialMacroAnalysis(BaseModel):
    """Cálculo cuantitativo de suma de fuerzas vectoriales macroeconómicas."""
    active_events_count: int
    gross_force: float
    net_force: float
    directional_coherence: float = Field(ge=0.0, le=1.0)
    evidence_coverage: float = Field(ge=0.0, le=1.0)
    calibrated_confidence_pct: float = Field(ge=0.0, le=100.0)
    dominant_direction: DirectionEnum
    warning_flags: List[str] = Field(default_factory=list)
```

---

## 9. Instrucciones Paso a Paso para el Worker M1_1

El Worker M1_1 debe ejecutar las siguientes instrucciones de trabajo para redactar `docs/macro_usdt_taxonomy.md` de forma impecable:

### Paso 1: Verificación de Entorno y Preparación
- Asegurarse de que el directorio `docs/` exista en `c:\p2p-bot-merchant\docs`.
- Comprobar que no se sobreescriban archivos existentes no relacionados.
- Utilizar formato Markdown estándar con ecuaciones en bloques LaTeX renderizables (`$$ ... $$` y `$ ... $`).

### Paso 2: Redacción de la Sección 1 y Sección 2 (Fundamentos y Modelado Matemático)
- Redactar los fundamentos del mercado cambiario venezolano y la fijación de precios en Binance P2P.
- Describir con total exactitud las 5 ecuaciones matemáticas:
  1. Ecuación de Brecha Cambiaria $B_t$ y los 4 regímenes (Calma, Fricción, Tensión, Ruptura).
  2. Micro-spreads ponderados por método bancario (Banesco/PagoMóvil $\omega=0.55$, BDV $\omega=0.30$, Otros $\omega=0.15$).
  3. Formulación Vectorial de Fuerza Neta $F_{\text{net}}(t) = \sum F_i(t)$.
  4. Decaimiento temporal exponencial gobernado por semivida $h_i$ y retraso de activación $L_i$.
  5. Calibración de confianza $C_t$ a partir de Coherencia y Cobertura, explicitando las salvaguardas Fail-Closed.

### Paso 3: Redacción de la Sección 3 (Taxonomía Canónica de 14 Eventos)
- Insertar la Tabla Maestra Canónica de 14 eventos con todas sus columnas completas.
- Elaborar las 14 fichas técnicas individuales detallando:
  - Código, Categoría y Nombre Canónico.
  - Condición de activación cuantitativa / cronograma histórico.
  - Mecanismo de transmisión micro y macroeconómica (paso a paso: liquidez $\rightarrow$ banca $\rightarrow$ P2P).
  - Parámetros empíricos: Dirección ($+1, -1, 0$), Peso base ($w_i$), Latencia ($L_i$), Semivida ($h_i$).
  - Fuentes de datos recomendadas (primaria y fallback).
  - Condición de invalidación o amortiguamiento.

### Paso 4: Redacción de la Sección 4 (Matriz de Rezagos Cuantitativos)
- Insertar la Matriz de Rezagos Temporales ($T+0$, $T+1$, $T+3$, $T+7$).
- Clasificar los shocks según su persistencia económica: Transitorio, Escalón Permanente Parcial, Escalón Permanente Total, Cambio de Régimen Macroeconómico, Friccional Intradía.

### Paso 5: Redacción de la Sección 5 y Sección 6 (Fuentes de Datos y Resolución de Conflictos)
- Desarrollar el catálogo detallado de fuentes de datos con su protocolo de ingesta, SLA de latencia y gestión de errores Fail-Closed (certificados SSL del BCV, anti-bot en Binance).
- Desarrollar la matriz de colisión de señales (interferencia de ondas macroeconómicas) y documentar las tres reglas heurísticas de decisión para el Predictor y el Revisor.

### Paso 6: Redacción de la Sección 7 y Sección 8 (Esquemas Pydantic y Mantenimiento)
- Transcribir los esquemas de código Pydantic v2 limpios, validados y listos para ser importados o referenciados por `src/`.
- Detallar las directrices de mantenimiento: recalibración trimestral de pesos, monitoreo de cambios regulatorios en Gaceta Oficial y revisión de certificados SSL.

### Paso 7: Verificación de Calidad y Cierre
- Realizar una lectura de auto-verificación: comprobar que no existan placeholders tipo `[TBD]`, enlaces rotos o contradicciones entre tablas y texto.
- Confirmar que el tono sea estrictamente profesional, analítico, técnico y redactado en español neutro de alta precisión financiera.

---

## 10. Conclusión Estratégica

Con esta estrategia y blueprint técnico, el Worker M1_1 dispone de toda la información requerida, ecuaciones matemáticas formalizadas, parámetros cuantitativos y tablas canónicas para crear `docs/macro_usdt_taxonomy.md` con el estándar de máxima calidad del proyecto `p2p-bot-merchant`.
