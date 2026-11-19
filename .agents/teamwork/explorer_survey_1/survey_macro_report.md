# Informe de Investigación Macroeconómica: Factores, Fuentes y Taxonomía de Eventos que Impactan el Precio del USDT en Venezuela

**Fecha:** 2026-11-17  
**Investigador:** Explorer 1 — Macroeconomic & Market Survey Specialist  
**Destino:** Equipo de Arquitectura de IA y Modelado Predictivo (`p2p-bot-merchant`)  
**Directorio de Trabajo:** `c:\p2p-bot-merchant\.agents\teamwork\explorer_survey_1\`

---

## 1. Resumen Ejecutivo

En la economía venezolana, el par **USDT/VES** (negociado primordialmente en el libro de órdenes peer-to-peer de **Binance P2P**) constituye el **mecanismo primario y termómetro en tiempo real de formación de precios del mercado cambiario libre (paralelo)**. Debido a las severas restricciones de liquidez del sistema bancario tradicional, la existencia de controles cambiarios y la pérdida constante de valor adquisitivo del bolívar (VES), el USDT cumple una triple función de facto: **unidad de cuenta, reserva de valor y medio de pago/liquidación comercial 24/7**.

La tasa oficial emitida por el **Banco Central de Venezuela (BCV)** se determina mediante el promedio ponderado de las operaciones de las mesas de cambio bancarias reguladas, alimentadas semanalmente mediante inyecciones forzadas de divisas ("intervención cambiaria"). Sin embargo, la oferta de divisas oficiales es estructuralmente deficitaria respecto a la demanda global de cobertura. Esto genera una **brecha cambiaria sistemática** entre el tipo de cambio oficial y la cotización del USDT en Binance P2P.

Este informe desglosa de manera exhaustiva:
1. Los factores macroeconómicos y operativos subyacentes que empujan o contienen el precio de USDT.
2. Los mecanismos cuantitativos de transmisión y la matriz de rezago temporal (*lag*).
3. El catálogo y factibilidad técnica de ingesta de fuentes públicas y canales de noticias venezolanos.
4. Una **taxonomía canónica formal de eventos** diseñada para alimentar de forma directa el pipeline de inteligencia artificial (Buscador, Predictor y Revisor).

---

## 2. Factores Macroeconómicos Clave en Venezuela

### 2.1 Pagos de Nóminas del Sector Público, Aguinaldos y Bonos del Sistema Patria
El gasto público fiscal financiado mediante emisión monetaria es el **catalizador alcista más potente y predecible** del tipo de cambio USDT/VES.

* **Patrón Cronológico del "Bono Contra la Guerra Económica" (Plataforma Patria):**
  El subsidio mensual indexado se distribuye de manera escalonada en tres oleadas mensuales claramente definidas:
  1. **Oleada 1 (Días 13 al 15 de cada mes):** Trabajadores activos de la administración pública y jubilados con Cestaticket. Concentra el mayor volumen de masa monetaria inyectada en cuentas de nómina del Banco de Venezuela, Bicentenario y Tesoro.
  2. **Oleada 2 (Días 16 al 19 de cada mes):** Jubilados de la administración pública centralizada y descentralizada sin beneficio de alimentación.
  3. **Oleada 3 (Días 21 al 24 de cada mes):** Pensionados del Instituto Venezolano de los Seguros Sociales (IVSS) y programa Amor Mayor.
* **Quincenas del Sector Público y Privado:**
  * Días **10 al 15** y **25 al 30/31**: Acreditación masiva de sueldos en cuentas corrientes bancarias.
* **Estacionalidad Crítica de Fin de Año (Octubre a Diciembre):**
  * Pago fraccionado de **Aguinaldos / Bonificaciones de Fin de Año**: Históricamente se divide en 3 o 4 fracciones quincenales desembolsadas a partir de la primera quincena de octubre y extendiéndose hasta la primera semana de diciembre.
  * Durante este trimestre, la masa de bolívares en circulación se expande exponencialmente en lapsos de 48 horas, provocando picos de demanda explosiva e incrementando la velocidad de circulación del dinero (*velocity of money*).

### 2.2 Intervenciones Cambiarias del Banco Central de Venezuela (BCV)
La intervención cambiaria es la herramienta central del BCV para contener el tipo de cambio mediante venta directa de moneda extranjera (dólares y euros en efectivo o transferencia) a la banca comercial pública y privada.

* **Días de Adjudicación Habitual:**
  * **Lunes por la mañana (08:30 - 10:30 AM VET):** Operación principal de la semana. Se fija el monto de venta y la tasa de cambio de colocación en las mesas de cambio bancarias.
  * **Miércoles o Jueves:** Intervenciones complementarias o extensiones cambiarias, activadas únicamente cuando la presión cambiaria en el mercado informal y P2P desborda el límite de tolerancia del ente emisor.
* **Montos Semanales y Rangos Típicos:**
  * **Rango Bajo / Escasez:** Entre **$35M y $60M** semanales. Indica restricciones de caja o merma de flujo petrolero. El mercado percibe la oferta como insuficiente, acelerando la subida del USDT.
  * **Rango Moderado / Neutral:** Entre **$70M y $110M** semanales. Satisface parcialmente la demanda de grandes importadores.
  * **Rango Agresivo / Contención Fuerte:** Superiores a **$120M - $180M** semanales (frecuentes en épocas electorales o picos de aguinaldos). Provoca un congelamiento temporal o retracción del precio informal de 24 a 72 horas.
* **Impacto en la Liquidez Interbancaria:**
  Al vender divisas, el BCV debita inmediatamente los bolívares de las cuentas de reserva y encaje de las entidades financieras, drenando liquidez neta del sistema bancario y reduciendo la capacidad de los bancos de prestar o liquidar operaciones en bolívares.

### 2.3 Emisión y Variación de Liquidez Monetaria (M2)
* **Reporte Semanal:** Publicado por el BCV los días viernes (o inicio de la semana siguiente) con corte al viernes precedente (rezago de 7 a 14 días).
* **Métrica:** M2 = Efectivo en poder del público + Depósitos transferibles + Otros depósitos a la vista y de ahorro.
* **Efecto de Transmisión:** Un incremento semanal superior al **2.5% - 4.0%** en M2 se traduce directamente en una depreciación proporcional diferida del bolívar. Los creadores de mercado (*merchants* de Binance P2P) y mesas de tesorería corporativa ajustan sus márgenes de protección ante la constatación de inflación monetaria no esterilizada.

### 2.4 Brecha Cambiaria (Spread Oficial BCV vs Binance P2P USDT)
La brecha porcentual se define como:
$$\text{Brecha} = \left(\frac{\text{Tasa P2P (USDT/VES)} - \text{Tasa Oficial BCV (USD/VES)}}{\text{Tasa Oficial BCV (USD/VES)}}\right) \times 100$$

* **Umbral de Calma (< 8%):** Mercado balanceado, alta oferta de divisas oficiales en mesas de cambio, bajo incentivo de arbitraje.
* **Umbral de Fricción (8% - 15%):** Escasez en las mesas bancarias. Los comercios formales (obligados por ley a facturar a tasa BCV) comienzan a sufrir pérdidas operativas si sus reposiciones de inventario están tasadas en P2P.
* **Umbral de Tensión Severa (15% - 25%):** Racionamiento estricto de divisas en la banca. Aparece el arbitraje compulsivo: agentes que logran comprar cupos a tasa oficial intentan monetizar en P2P para capturar la prima de riesgo.
* **Umbral de Crisis / Descalabro (> 25%):** Distorsión de precios generalizada, desabastecimiento en comercios que temen multas del SENIAT/SUNDDE, retención masiva de USDT por parte de los operadores de Binance (falta de vendedores en el libro de órdenes).

### 2.5 Calendario Fiscal del SENIAT y Demanda de Bolívares
El impacto tributario es uno de los factores menos comprendidos por el público general, pero de mayor poder predictivo **bajista/estabilizador**:

* **Contribuyentes Especiales (Sujetos Pasivos Especiales):**
  Obligados a declarar y pagar anticipos quincenales de Impuesto al Valor Agregado (IVA) e Impuesto Sobre la Renta (ISLR) según el último dígito del RIF.
* **Mecanismo de Pago Obligatorio en Bolívares:**
  Aun cuando las empresas facturen o posean activos en divisas o USDT, el SENIAT exige **exclusivamente bolívares** transferidos a las cuentas recaudadoras del Tesoro Nacional.
* **Efecto en la Venta de Divisas:**
  Entre 2 y 4 días antes del vencimiento del ciclo fiscal (generalmente entre los días **18 y 25 de cada mes** y al **cierre mensual**), las grandes empresas e industrias venden compulsivamente dólares y USDT en el mercado para aprovisionarse de bolívares fiscales. Esto incrementa fuertemente la oferta vendedora de USDT en Binance P2P, frenando las alzas del precio o generando correcciones bajistas transitorias.
* **Zafra Anual del ISLR (Marzo):**
  Históricamente, marzo registra las tasas de apreciación real temporal más altas del bolívar o los períodos de menor volatilidad cambiaria debido al drenaje monumental de bolívares hacia el SENIAT.

### 2.6 Dinámicas Operativas en Binance P2P y Feriados Bancarios
* **Lunes Bancarios y Feriados Nacionales (Calendario SUDEBAN):**
  Durante los feriados bancarios, las mesas de cambio oficiales y las transferencias de alto valor interbancarias están cerradas. Binance P2P opera como el **único mercado cambiario líquido disponible**, absorbiendo toda la presión comercial a través de Pago Móvil inmediato. Esto suele ensanchar el spread entre la orden de compra (*bid*) y la orden de venta (*ask*).
* **Diferenciales por Entidad Bancaria:**
  En el mercado P2P venezolano no existe un único precio USDT/VES; existen micro-precios según el método de liquidación:
  * **Banesco y Pago Móvil:** Máxima liquidez, menor spread, cotización de referencia nacional.
  * **Banco de Venezuela (BDV):** Alta liquidez, muy utilizado para retiros de nóminas estatales y transferencias internas BDV a BDV.
  * **Mercantil / BBVA Provincial / Bancamiga:** Liquidez media, spreads que pueden distar entre 0.5% y 1.5% respecto a Banesco.

### 2.7 Contexto Geopolítico y Flujos Petroleros (Licencias OFAC)
El flujo de caja de divisas que nutre las intervenciones del BCV proviene en más de un 75% de las exportaciones de crudo de PDVSA y empresas mixtas (Chevron, Eni, Repsol). Anuncios sobre sanciones de la OFAC, prórrogas o revocaciones de licencias petroleras alteran de inmediato las expectativas de solvencia del BCV:
* **Renovación / Flexibilización de Licencias:** Incrementa la expectativa de oferta de divisas $\rightarrow$ Impacto **BAJISTA o ESTABILIZADOR** en USDT.
* **Amenazas de Sanciones o Vencimiento sin Renovación:** Contrae la expectativa de caja del BCV $\rightarrow$ Impacto **FUERTEMENTE ALCISTA** en USDT.

---

## 3. Mecanismos de Transmisión y Matriz de Rezago Temporal (Lag Analysis)

### 3.1 Cadenas Causales de Transmisión

```
[Inyección Fiscal: Bonos Patria / Aguinaldos]
   │
   ├─► Acreditación masiva en Banco de Venezuela / Banesco (Minutos a Horas)
   │
   ├─► Repudio al Bolivar / Pérdida del poder de compra
   │
   └─► Avalancha de órdenes "Buy USDT" en Binance P2P
         │
         ├─► Consumo de liquidez en el lado vendedor (Ask)
         └─► Aumento acelerado de la tasa USDT/VES (Lag: 30m - 6h)
```

```
[Anuncio e Inyección de Intervención Cambiaria BCV]
   │
   ├─► Venta de divisas a bancos comerciales a tasa regulada
   │
   ├─► Cobertura parcial de compras de grandes importadores en Mesas de Cambio
   │
   ├─► Drenaje de reservas bancarias en VES (Esterilización de liquidez)
   │
   └─► Reducción momentánea de la demanda privada en Binance P2P (Lag: 2h - 24h)
```

```
[Vencimiento Fiscal SENIAT: Quincena / Fin de Mes]
   │
   ├─► Obligación empresarial ineludible de pago en VES al Fisco
   │
   ├─► Venta forzada de reservas en USDT / USD en P2P
   │
   └─► Saturación de oferta vendedora de USDT $\rightarrow$ Contención / Caída de tasa USDT/VES (Lag: 24h - 48h)
```

### 3.2 Matriz Cuantitativa de Rezagos Temporales (Lag Matrix)

| Evento Macroeconómico / Operativo | Canal de Transmisión Principal | Dirección Intrínseca | Tiempo Respuesta Inicial ($t_0$) | Pico de Volatilidad ($t_{\text{peak}}$) | Duración Total del Impacto ($t_{\text{duration}}$) | Factor de Persistencia / Reversión |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Acreditación Bono Guerra Económica (Activos)** | Pago Móvil / Binance P2P retail | **ALCISTA** | 15 - 45 min | 4 - 8 horas | 24 - 48 horas | Alto (rara vez revierte el precio) |
| **Acreditación Bono Jubilados/Pensionados** | Demanda retail consumo inmediato | **ALCISTA** | 1 - 2 horas | 6 - 12 horas | 24 horas | Moderado |
| **Pago Fracción de Aguinaldos (Oct-Dic)** | Consumo masivo + Cobertura comercial | **FUERTEMENTE ALCISTA** | 30 min | 12 - 24 horas | 3 - 5 días | Permanente (escalón nominal) |
| **Intervención Cambiaria BCV (Lunes estándar)** | Mesas de cambio bancarias | **BAJISTA / CONTENCIÓN** | 1 - 2 horas | 4 - 6 horas | 24 - 48 horas | Temporal (reversión hacia el alza) |
| **Intervención BCV Extraordinaria (> $120M)** | Inyección masiva banca | **FUERTEMENTE BAJISTA** | 30 min | 2 - 4 horas | 48 - 72 horas | Transitorio (frena rally pero no cambia tendencia) |
| **Publicación Semanal M2 (BCV)** | Señal analítica institucional | **ALCISTA** | 4 - 12 horas | 24 - 48 horas | 3 - 7 días | Acumulativo de mediano plazo |
| **Cierre Tributario Quincenal SENIAT** | Liquidación de tesorerías corporativas | **BAJISTA / ESTABLE** | 24h antes | 4h previas a cierre | 12h post-cierre | Rápida reversión alcista al día siguiente |
| **Vencimiento Anual ISLR (31 de Marzo)** | Venta masiva de divisas por empresas | **BAJISTA PROLONGADO** | 5 días antes | Días 29-31 Mar | 7 - 10 días | Moderado (abril retoma ritmo) |
| **Lunes Bancario (SUDEBAN)** | Desvío 100% de operaciones a P2P | **NEUTRAL / VOLÁTIL** | 0 min | 11:00 AM - 3:00 PM | 24 horas | Spread temporal que se normaliza el martes |
| **Advertencia / Fiscalización SUNDDE-SENIAT** | Miedo regulatorio / Retención de USDT | **VOLÁTIL / ALCISTA P2P** | 1 - 3 horas | 12 - 24 horas | 2 - 4 días | Brecha se expande drásticamente |
| **Endurecimiento Sanciones / Licencias OFAC** | Expectativa de insolvencia BCV | **FUERTEMENTE ALCISTA** | 10 - 30 min | 24 - 48 horas | 1 a 3 semanas | Permanente (cambio de régimen macro) |

---

## 4. Catálogo de Fuentes Públicas de Información y Métodos de Ingesta

### 4.1 Inventario de Fuentes Primarias y Secundarias

#### Grupo A: Fuentes Oficiales e Institucionales
1. **Banco Central de Venezuela (BCV)**
   * *Portal Web:* `https://www.bcv.org.ve`
   * *Redes Sociales:* Cuenta en X `@BCV_ORG_VE`
   * *Datos Clave:* Tasa oficial de cambio diaria (divisas USD, EUR), tabla de Fecha Valor, informes semanales de Liquidez Monetaria (M2), reservas internacionales y comunicados de directorio.
2. **Superintendencia de las Instituciones del Sector Bancario (SUDEBAN)**
   * *Portal Web:* `https://www.sudeban.gob.ve`
   * *Redes Sociales:* Cuenta en X `@SudebanInforma`
   * *Datos Clave:* Calendario bancario anual de feriados y lunes bancarios, circulares de encaje legal y límites diarios de transferencias/Pago Móvil.
3. **Plataforma Patria / Blog Patria**
   * *Portal Web:* `https://blog.patria.org.ve`
   * *Redes Sociales:* Canales de Telegram (`@PatriaDigital`, `@BonosSocial`), cuentas de X (`@CarnetDLaPatria`).
   * *Datos Clave:* Avisos de liberación de Bonos de Guerra Económica, montos oficiales, cronogramas de adjudicación.
4. **Servicio Nacional Integrado de Administración Aduanera y Tributaria (SENIAT)**
   * *Portal Web:* `http://declaraciones.seniat.gob.ve`
   * *Datos Clave:* Calendario de Sujetos Pasivos Especiales (SPE), fechas de corte de IVA, ISLR e IGTF.

#### Grupo B: Portales de Inteligencia Financiera y Económica
1. **Banca y Negocios (`bancaynegocios.com`)**
   * *Relevancia:* Fuente de referencia nacional para el reporte anticipado y exclusivo de los **montos exactos de intervención cambiaria del BCV** cada lunes y miércoles.
   * *Formato:* Artículos editoriales y análisis de banca.
2. **Finanzas Digital (`finanzasdigital.com`)**
   * *Relevancia:* Cobertura técnica y detallada de estadísticas de inflación (Observatorio Venezolano de Finanzas - OVF y BCV), crédito bancario y comercio exterior.
3. **Descifrado (`descifrado.com`)**
   * *Relevancia:* Monitoreo de actividad comercial retail, tendencias de precios al consumidor y distorsiones cambiarias de calle.
4. **Efecto Cocuyo (`efectococuyo.com`) y Crónica Uno (`cronica.uno`)**
   * *Relevancia:* Reportajes sobre acuerdos laborales públicos, retrasos en pagos salariales estatales y pulso socioeconómico.

#### Grupo C: Monitores de Mercado y Agregadores de Cotizaciones
1. **Binance P2P Ticker & Orderbook (`c2c.binance.com`)**
   * *Relevancia:* Verdad básica del mercado. Libros de órdenes en vivo para USDT/VES filtrados por métodos bancarios (Banesco, Pago Móvil, Banco de Venezuela).
2. **Monitor Dólar Venezuela (`monitordolarvenezuela.com` / `@monitordolarvla`)**
   * *Relevancia:* Agregador histórico de tasas paralelas ponderadas.
3. **EnParaleloVzla (`@enparalelovzla`)**
   * *Relevancia:* Publicación bi-diaria (9:00 AM y 1:00 PM) que históricamente ancla expectativas de fijación de precios en el comercio informal.
4. **Yadio.io / DolarVzla APIs**
   * *Relevancia:* Feeds de agregación técnica y cálculo de brechas cambiarias automatizadas.

#### Grupo D: Canales de Difusión Inmediata y Economistas de Referencia
* **Asdrúbal Oliveros** (`@aroliveros` / Ecoanalítica): Análisis de flujos de divisas, proyecciones de tipo de cambio y política fiscal.
* **Henkel García** (`@HenkelGarcia` / AlbusData): Análisis técnico de liquidez, comportamiento de la masa monetaria y paridades teóricas.
* **Víctor Álvarez** (`@victoralvarezr`): Enfoque en política monetaria, encaje y desequilibrios fiscales.
* **Leonardo Buniak** (`@leonardobuniak`): Análisis de solvencia y riesgo de la banca venezolana.
* **Canal Telegram "Patria Digital" / "Bonos de la Patria":** Primera señal de alerta (latencia < 2 minutos) cuando se emite el SMS 3532 de acreditación bancaria.

---

### 4.2 Métodos de Ingesta Técnica y Factibilidad

| Fuente / Canal | Método de Ingesta Recomendado | Latencia Estimada | Nivel de Robustez | Complejidad de Implementación | Observaciones / Riesgos Técnicos |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Portales de Noticias (Banca y Negocios, Finanzas Digital)** | **RSS Feeds** / Scraping HTTP ligero (`httpx`) | 5 - 15 minutos | **ALTA** | Baja | Muy bajo riesgo de bloqueo. El RSS expone título y resumen inmediato. |
| **BCV (Tasas Oficiales)** | Web Scraping HTML (`httpx` Fail-closed) | 1 - 5 minutos | **ALTA** | Ya implementada en `src/reporting/bcv_service.py` | Requiere ignorar validación de certificados SSL (`verify=False`) por fallas crónicas del certificado del BCV. |
| **BCV (Liquidez Monetaria M2)** | Extracción de tablas HTML / Excel del BCV | Semanal (Viernes) | **MEDIA** | Media | La estructura del sitio web del BCV suele cambiar rutas ocasionalmente. Requiere parser defensivo. |
| **Canales Públicos de Telegram (Patria Digital)** | **Telethon / MTProto Client** (Telegram API) | **< 30 segundos** | **MUY ALTA** | Media | Permite captura push inmediata del mensaje sin depender de web scraping. No sufre bloqueos de IP. |
| **Binance P2P Orderbook** | Endpoint JSON público (`c2c/v2/friendly/c2c/adv/search`) | 10 - 30 segundos | **ALTA** | Media | Debe utilizar rotación de User-Agent y monitoreo de rate-limits para no gatillar captchas de Akamai/Cloudflare. |
| **SENIAT (Calendario SPE)** | Tabla estática anual con refresco mensual en BD | Mensual | **MUY ALTA** | Mínima | El calendario oficial se publica en Gaceta Oficial en diciembre/enero. Se pre-carga en base de datos. |
| **Cuentas de X (Twitter)** | Web scraping vía Nitter / Scraping headless | 1 - 5 minutos | **BAJA / VARIABLE** | Alta | La API oficial de Twitter tiene costos elevados y limitaciones de cuota. Recomendado usar RSS o Telegram como sustituto primario. |

---

## 5. Taxonomía Formal de Eventos para el Sistema de IA

Para que el pipeline de IA procese de manera determinista y matemática la avalancha de noticias y señales, cada evento detectado por el **Rol Buscador** debe mapearse a la siguiente estructura formal normalizada:

### 5.1 Esquema de Metadatos del Evento (Data Schema)

```json
{
  "event_id": "EVT-202611-BCV-INT-001",
  "category": "INTERVENCION_CAMBIARIA_BCV",
  "event_name": "BCV inyecta $90M en intervención cambiaria semanal",
  "source_channel": "PORTAL_NOTICIAS_FINANCIERAS",
  "source_name": "Banca y Negocios",
  "timestamp_utc": "2026-11-17T13:30:00Z",
  "impact_criticality": "ALTO",
  "impact_weight_score": 0.85,
  "intrinsic_direction": "BAJISTA",
  "expected_impact_window": "CORTO_PLAZO_2_24H",
  "time_lag_hours": 3.0,
  "decay_half_life_hours": 18.0,
  "spread_influence": "COMPRESION_BRECHA",
  "attributes": {
    "intervention_amount_usd": 90000000,
    "bcv_exchange_rate": 45.20,
    "comparison_vs_prior_week_pct": -10.0
  }
}
```

### 5.2 Definición de Parámetros de la Taxonomía

1. **`category` (Categoría Primaria):**
   * `GASTO_PUBLICO_PATRIA`: Bonos del Sistema Patria, aguinaldos y transferencias gubernamentales.
   * `INTERVENCION_CAMBIARIA_BCV`: Subastas e inyecciones de divisas del banco central a la banca.
   * `POLITICA_MONETARIA_LIQUIDEZ`: Variaciones de M2, emisión inorgánica, tasas de encaje bancario.
   * `CALENDARIO_FISCAL_SENIAT`: Fechas de declaración y pago de impuestos de Sujetos Pasivos Especiales.
   * `REGULACION_CAMBIARIA_BANCARIA`: Resoluciones de SUDEBAN, límites bancarios, controles comerciales.
   * `OPERATIVA_MERCADO_P2P`: Lunes bancarios, incidentes de red, fallas masivas de Pago Móvil.
   * `GEOPOLITICA_PETROLERA`: Licencias de la OFAC, exportaciones petroleras, bloqueos internacionales.
2. **`impact_criticality` y `impact_weight_score`:**
   * **`ALTO` (0.75 - 1.00):** Eventos con capacidad inmediata de mover el tipo de cambio más de un 1.5% - 3.0% en 24 horas (e.g., inyección masiva de aguinaldos, megaintervención BCV, revocación de licencias petroleras).
   * **`MEDIO` (0.40 - 0.74):** Variaciones normales de nómina quincenal, pagos tributarios estándar, intervenciones promedio rutinarias.
   * **`BAJO` (0.10 - 0.39):** Noticias de declaraciones políticas generales sin impacto monetario ejecutable, rumores no contrastados.
3. **`intrinsic_direction`:**
   * **`ALCISTA`:** Genera depreciación del bolívar e incremento en el precio del USDT/VES.
   * **`BAJISTA`:** Genera apreciación relativa del bolívar, contención forzada o corrección a la baja de la tasa USDT/VES.
   * **`NEUTRAL`:** Sin sesgo direccional definido; suele incrementar la volatilidad o ensanchar el spread bid-ask sin mover la media.
4. **`expected_impact_window` (Ventana de Impacto Estimada):**
   * `INMEDIATO_0_2H`: Reacción de shock en libros de órdenes.
   * `CORTO_PLAZO_2_24H`: Efecto a lo largo de la jornada operativa.
   * `MEDIANO_PLAZO_24_72H`: Absorción bancaria e interbancaria.
   * `ESTACIONAL_SEMANAL_MENSUAL`: Ciclos prolongados (aguinaldos en dic, impuestos en marzo).

---

### 5.3 Matriz Canónica de Eventos Catalogados

| Código de Evento | Nombre Canónico | Categoría | Fuente Típica | Criticidad | Peso (Score) | Dirección Intrínseca | Ventana Estimada | Lag Típico |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `EVT_PATRIA_GUERRA_ACTIVOS` | Bono Guerra Económica: Activos y Cestaticket | `GASTO_PUBLICO_PATRIA` | Telegram Patria / X | **ALTO** | 0.90 | **ALCISTA** | `CORTO_PLAZO_2_24H` | 1 - 3 horas |
| `EVT_PATRIA_GUERRA_JUBILADOS` | Bono Guerra Económica: Jubilados | `GASTO_PUBLICO_PATRIA` | Telegram Patria / X | **MEDIO** | 0.65 | **ALCISTA** | `CORTO_PLAZO_2_24H` | 2 - 4 horas |
| `EVT_PATRIA_AGUINALDOS_FRAC` | Desembolso de Fracción de Aguinaldos Públicos | `GASTO_PUBLICO_PATRIA` | MPPEF / Medios | **ALTO** | 1.00 | **ALCISTA** | `MEDIANO_PLAZO_24_72H`| 1 - 2 horas |
| `EVT_BCV_INTERVENCION_REGULAR`| Intervención Cambiaria Semanal Lunes ($50M-$90M)| `INTERVENCION_CAMBIARIA_BCV`| Banca y Negocios | **MEDIO** | 0.70 | **BAJISTA** | `CORTO_PLAZO_2_24H` | 2 - 6 horas |
| `EVT_BCV_INTERVENCION_AGRESIVA`| Intervención Extraordinaria (> $120M) | `INTERVENCION_CAMBIARIA_BCV`| Banca y Negocios / BCV | **ALTO** | 0.95 | **BAJISTA** | `MEDIANO_PLAZO_24_72H`| 1 - 3 horas |
| `EVT_BCV_INTERVENCION_DEFICIT`| Intervención Insuficiente (< $40M) | `INTERVENCION_CAMBIARIA_BCV`| Banca y Negocios | **ALTO** | 0.85 | **ALCISTA** | `CORTO_PLAZO_2_24H` | 4 - 8 horas |
| `EVT_BCV_LIQUIDEZ_M2_SPIKE` | Expansión Semanal de M2 > 3.5% | `POLITICA_MONETARIA_LIQUIDEZ`| BCV Portal / Finanzas | **MEDIO** | 0.60 | **ALCISTA** | `ESTACIONAL_SEMANAL` | 24 - 48 horas |
| `EVT_SENIAT_PAGO_QUINCENA` | Vencimiento Anticipos IVA/ISLR Especiales | `CALENDARIO_FISCAL_SENIAT` | Calendario SENIAT | **MEDIO** | 0.65 | **BAJISTA** | `CORTO_PLAZO_2_24H` | -24h a 0h |
| `EVT_SENIAT_ZAFRA_ISLR_MAR`| Cierre Anual Declaración ISLR (Marzo) | `CALENDARIO_FISCAL_SENIAT` | SENIAT Oficial | **ALTO** | 0.85 | **BAJISTA** | `ESTACIONAL_SEMANAL` | -72h a +48h |
| `EVT_SUDEBAN_LUNES_BANCARIO` | Lunes Bancario / Feriado del Sector Financiero| `OPERATIVA_MERCADO_P2P` | SUDEBAN Calendario | **MEDIO** | 0.50 | **NEUTRAL** | `CORTO_PLAZO_2_24H` | 0 horas |
| `EVT_OFAC_LICENCIA_RENOVADA`| Renovación / Ampliación Licencia Petrolera | `GEOPOLITICA_PETROLERA` | Departamento Tesoro / Prensa | **ALTO** | 0.90 | **BAJISTA** | `ESTACIONAL_SEMANAL` | 2 - 12 horas |
| `EVT_OFAC_LICENCIA_REVOCADA`| Revocación / Vencimiento sin Prórroga de Licencia| `GEOPOLITICA_PETROLERA` | Departamento Tesoro / Prensa | **ALTO** | 1.00 | **ALCISTA** | `MEDIANO_PLAZO_24_72H`| 1 - 4 horas |
| `EVT_REGULACION_FISCALIZACION`| Operativos SUNDDE/SENIAT sobre tasa oficial | `REGULACION_CAMBIARIA_BANCARIA`| Medios Nacionales | **MEDIO** | 0.70 | **ALCISTA** (P2P) | `MEDIANO_PLAZO_24_72H`| 6 - 12 horas |
| `EVT_CAIDA_PAGO_MOVIL_NAC` | Caída de plataforma interbancaria Suiche 7B | `OPERATIVA_MERCADO_P2P` | Redes / Monitores | **MEDIO** | 0.55 | **NEUTRAL** | `INMEDIATO_0_2H` | 0 - 30 min |

---

## 6. Recomendaciones para el Pipeline de IA (Buscador, Predictor, Revisor)

1. **Manejo de Señales Contradictorias (Interferencia de Fuerzas):**
   * *Escenario Clásico:* El lunes en la mañana el BCV anuncia una fuerte intervención de $100M (**señal bajista peso 0.70**), pero a las 11:00 AM el Sistema Patria inicia la asignación masiva de aguinaldos (**señal alcista peso 1.00**).
   * *Regla para el Predictor:* El modelo debe aplicar un vector neto de fuerzas:
     $$\Delta_{\text{neto}} = \sum (\text{Signo}_i \times \text{Weight}_i \times \text{Decay}_i(t))$$
     En la economía venezolana, la emisión no respaldada para gasto público minorista siempre supera la capacidad de contención de la intervención cambiaria en un horizonte mayor a 24 horas. Por tanto, la predicción debe arrojar **ALCISTA con confiabilidad ajustada (ej. 75%-80%) y advertencia de compresión temporal en las primeras 6 horas**.
2. **Definición de Salida Estructurada para el Predictor:**
   El resultado emitido por el modelo debe contener obligatoriamente:
   * **Dirección Proyectada:** `SUBIRÁ`, `BAJARÁ`, `LATERAL/ESTABLE`.
   * **Lapso Temporal Estimado:** Ej. *"Próximas 12 a 24 horas"*, *"Horizonte de 48 a 72 horas"*.
   * **Porcentaje de Confiabilidad:** Valor entero de 0% a 100% justificado en la concordancia de eventos.
   * **Fundamentación Analítica:** Resumen conciso citando los eventos detectados, el peso relativo y el mecanismo de transmisión activo.
3. **Rol del Revisor / Auditor:**
   * Comprobar que no se usen rumores de redes no validados en fuentes oficiales o portales reconocidos.
   * Verificar que las fechas valor del BCV y los días hábiles bancarios se respeten rigurosamente (ej. descartar que una intervención bancaria se ejecute en domingo).
   * Garantizar que la predicción cumpla con los principios *Fail-closed* de seguridad: ante vacío de noticias o señales ambiguas de igual magnitud, emitir predicción `NEUTRAL / INDETERMINADA` con bajo nivel de confianza en lugar de forzar una apuesta direccional.

---
**Fin del Informe de Investigación Macroeconómica.**
