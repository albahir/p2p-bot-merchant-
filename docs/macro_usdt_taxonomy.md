# Taxonomía Canónica y Modelado de Impacto Macroeconómico en USDT/VES (Venezuela)

**Documento Canónico de Referencia Macroeconómica y Cuantitativa**  
**Subsistema:** `023-ai-market-predictor` (Advisory / Market Intelligence)  
**Versión:** 1.0.0  
**Fecha de Vigencia:** Noviembre 2026  
**Clasificación:** Documentación Técnica de Producción  

---

## 1. Fundamentos del Mercado USDT/VES en Venezuela

### 1.1 Doble Rol del USDT: Activo de Cobertura y Medio de Liquidación 24/7

En la República Bolivariana de Venezuela, la tasa de cambio entre el dólar estadounidense digital (representado primordialmente por **Tether USD - USDT**) y la moneda nacional (**Bolívar - VES**) se ha consolidado como el indicador de liquidez, valor y expectativa inflacionaria más dinámico y relevante del país.

A diferencia de las economías convencionales donde las divisas cotizan predominantemente a través de cámaras interbancarias sujetas a horarios de oficina estrictos (lunes a viernes de 08:30 a 15:30 VET), el mercado de **Binance P2P** opera de forma ininterrumpida (**24 horas al día, 7 días a la semana, 365 días al año**). En este entorno:

1. **Activo de Cobertura de Tesorería (*Store of Value*):** Las empresas, comerciantes mayoristas, minoristas y familias venezolanas convierten inmediatamente sus excedentes de bolívares a USDT para proteger su poder adquisitivo frente a la depreciación crónica y la emisión monetaria no respaldada.
2. **Medio de Liquidación Inmediata (*Settlement Vehicle*):** Ante la escasez física de billetes en efectivo y los límites diarios de transferencias bancarias en divisas, el USDT actúa como moneda de liquidación B2B y B2C, permitiendo compensaciones inmediatas e interbancarias en bolívares a través del sistema Pago Móvil o transferencias intrabancarias.

### 1.2 Formación de Precios: Tasa Oficial BCV vs Binance P2P

El ecosistema cambiario venezolano presenta una estructura bimonetaria dividida en dos segmentos fundamentales:

* **Tasa Oficial del Banco Central de Venezuela ($P^{\text{BCV}}$):** Es el tipo de cambio ponderado resultante de las operaciones diarias de compra y venta en las mesas de cambio de las instituciones bancarias autorizadas. Se publica diariamente al final de la tarde (habitualmente entre las 16:00 y 17:30 VET) y entra en vigencia con fecha valor del siguiente día hábil. Esta tasa es de uso obligatorio para la facturación mercantil formal bajo supervisión del SENIAT y la SUNDDE.
* **Tasa Libre en Binance P2P ($P^{\text{P2P}}$):** Es el precio de equilibrio instantáneo determinado por el libro de órdenes (*orderbook*) de compradores y vendedores en la plataforma peer-to-peer. Refleja en tiempo real las presiones inmediatas de oferta y demanda monetaria, sin restricciones de horario bancario ni controles administrativos de asignación.

### 1.3 Dinámica de la Brecha Cambiaria y Regímenes de Volatilidad

La coexistencia de un mercado oficial regulado y un mercado libre continuo da origen al diferencial cambiario o **Brecha Cambiaria**. Cuando el acceso a divisas a tasa oficial en las mesas bancarias se restringe o raciona, los actores económicos recurren masivamente al mercado P2P, ampliando la brecha. Por el contrario, cuando el BCV incrementa significativamente la oferta de divisas en la banca comercial, la brecha tiende a comprimirse.

---

## 2. Modelado Matemático de Fuerzas Macroeconómicas

### 2.1 Ecuación de Brecha Cambiaria Porcentual ($B_t$)

La brecha cambiaria en el instante $t$ se define cuantitativamente mediante la fórmula:

$$B_t = \left( \frac{P_t^{\text{P2P}} - P_t^{\text{BCV}}}{P_t^{\text{BCV}}} \right) \times 100$$

Donde:
* $P_t^{\text{P2P}}$: Precio spot de compra/venta de referencia en Binance P2P (VES por USDT).
* $P_t^{\text{BCV}}$: Tipo de cambio oficial vigente publicado por el BCV (VES por USD).

#### Regímenes de Mercado según la Brecha Cambiaria

| Régimen | Rango de Brecha ($B_t$) | Denominación | Dinámica Operativa y Microestructura |
| :---: | :---: | :--- | :--- |
| **Régimen I** | $B_t < 8.0\%$ | **Calma / Equilibrio Institucional** | Oferta fluida de divisas en las mesas bancarias. El arbitraje informal no resulta rentable tras deducir comisiones transaccionales. Volatilidad P2P baja. |
| **Régimen II** | $8.0\% \le B_t < 15.0\%$ | **Fricción Moderada** | Racionamiento parcial de divisas para medianas empresas en la banca. Se acelera la demanda de cobertura en P2P. Los spreads comerciales se amplían de forma predecible. |
| **Régimen III** | $15.0\% \le B_t < 25.0\%$ | **Tensión Severa / Racionamiento** | Acceso mínimo a divisas oficiales. Retención defensiva de inventario de USDT por parte de los operadores comerciales. Aparecen distorsiones en precios al consumidor. |
| **Régimen IV** | $B_t \ge 25.0\%$ | **Desalineación Crítica / Ruptura** | Quiebre del mecanismo oficial de asignación. Riesgo inminente de paralización comercial por fiscalizaciones punitivas. Volatilidad extrema y desdoblamiento de precios. |

### 2.2 Micro-Spreads y Jerarquía por Método de Liquidación Bancaria

El precio efectivo en Binance P2P no es homogéneo; depende directamente del canal bancario utilizado para transferir los bolívares. El precio compuesto ponderado de mercado se formaliza como:

$$P_t^{\text{P2P}} = \sum_{m \in M} \omega_m \cdot P_{t, m}^{\text{P2P}}$$

Donde $M = \{\text{Banesco/PagoMóvil}, \text{BDV}, \text{Otros}\}$ y los factores de ponderación de liquidez empíricos $\omega_m$ satisfacen $\sum \omega_m = 1.0$:

1. **Banesco y Pago Móvil Interbancario ($\omega_{\text{Banesco}} = 0.55$):** Constituye el canal de referencia estándar de liquidez inmediata en Venezuela. Profundidad continua, libro denso y spreads bid-ask más estrechos ($0.3\% - 0.8\%$).
2. **Banco de Venezuela ($\omega_{\text{BDV}} = 0.30$):** Canal primario de dispersión de fondos estatales (subsidios del Sistema Patria y nóminas de empleados públicos). Presenta primas alcistas transitorias de $+0.3\%$ a $+1.2\%$ durante los días de dispersión de bonos gubernamentales.
3. **Otros Bancos Privados (Mercantil, BBVA Provincial, Bancamiga, BNC) ($\omega_{\text{Otros}} = 0.15$):** Menor profundidad agregada; spreads bid-ask más amplios ($1.0\% - 2.5\%$).

### 2.3 Formulación Vectorial de Fuerza Macroeconómica Neta ($F_{\text{net}}$)

Sea $\mathcal{E}_t = \{e_1, e_2, \dots, e_N\}$ el conjunto de eventos macroeconómicos activos identificados en la ventana temporal rodante de 7 días ($W = 168$ horas). Cada evento $e_i$ se caracteriza por:

* $d_i \in \{+1.0, -1.0, 0.0\}$: Dirección vectorial intrínseca sobre la cotización USDT/VES:
  - $+1.0$: Vector ALCISTA (presión hacia la depreciación del VES / subida del USDT).
  - $-1.0$: Vector BAJISTA (presión hacia la apreciación o contención del VES / bajada del USDT).
  - $0.0$: Vector NEUTRAL (impacto primordialmente friccional o de ampliación de spread).
* $w_i \in [0.10, 1.00]$: Magnitud o peso intrínseco del evento en la economía venezolana.
* $c_i \in (0.0, 1.0]$: Factor de credibilidad y certeza de la fuente emisora ($1.00$ para Gaceta Oficial y BCV; $0.85$ para portales financieros acreditados; $0.70$ para canales de mensajería).
* $\Delta t_i = t - t_i \ge 0$: Horas transcurridas desde la confirmación o inicio del evento.
* $L_i \ge 0$: Latencia o rezago inicial de transmisión hacia el sistema bancario y el libro P2P (en horas).
* $h_i > 0$: Semivida (*half-life*) de decaimiento del impacto en el mercado (en horas).

### 2.4 Funciones de Activación y Decaimiento Temporal

#### 2.4.1 Función de Activación de Propagación ($\alpha_i$) con Cota Inferior Defensiva

La transmisión de una inyección de liquidez o de una intervención cambiaria no es instantánea. Requiere un tiempo de procesamiento interbancario y de difusión cognitiva. Para evitar anomalías matemáticas causadas por noticias de eventos programados en el futuro ($\Delta t_i < 0$), la función incorpora una cota inferior defensiva estricta ($\max(0.0, \Delta t_i / L_i)$) que impide la inversión espuria del sentido del vector de fuerza:

$$\alpha_i(\Delta t_i) = \begin{cases}
\max\left(0.0, \frac{\Delta t_i}{L_i}\right) & \text{si } L_i > 0 \text{ y } \Delta t_i < L_i \\
0.0 & \text{si } \Delta t_i \le 0 \\
1.0 & \text{si } \Delta t_i \ge L_i
\end{cases}$$

O de forma analítica compacta:
$$\alpha_i(\Delta t_i) = \begin{cases}
\max\left(0.0, \frac{\Delta t_i}{L_i}\right) & \text{si } L_i > 0 \text{ y } \Delta t_i < L_i \\
1.0 & \text{si } \Delta t_i \ge L_i
\end{cases}$$

* **Comportamiento ante eventos futuros ($\Delta t_i < 0$):** Si un evento está pautado para ejecutarse en el futuro ($t < t_i$), $\alpha_i(\Delta t_i) = 0.0$. La fuerza efectiva inicial es cero, garantizando que un shock alcista nunca se registre como bajista antes de ocurrir.
* **Comportamiento en ventana de rezago ($0 < \Delta t_i < L_i$):** El impacto escala linealmente de $0.0$ a $1.0$ a medida que los fondos circulan interbancariamente.
* **Comportamiento en maduración ($L_i \le \Delta t_i$):** El impacto alcanza el $100\%$ de su fuerza base ($1.0$) y posteriormente queda sujeto exclusivamente a la función de decaimiento temporal $D_i(\Delta t_i)$.

#### 2.4.2 Función de Decaimiento Temporal ($D_i$)

El decaimiento posterior al pico de absorción sigue un modelo de enfriamiento exponencial gobernado por la constante $\lambda_i = \frac{\ln(2)}{h_i}$:

$$D_i(\Delta t_i) = \exp\left( -\frac{\ln(2)}{h_i} \cdot \max(0, \Delta t_i - L_i) \right)$$

#### 2.4.3 Fuerza Efectiva Instantánea de un Evento ($F_i(t)$)

$$F_i(t) = d_i \cdot w_i \cdot c_i \cdot \alpha_i(\Delta t_i) \cdot D_i(\Delta t_i)$$

#### 2.4.4 Fuerza Neta Macroeconómica Agregada ($F_{\text{net}}(t)$)

$$F_{\text{net}}(t) = \sum_{i=1}^N F_i(t) = \sum_{i=1}^N d_i \cdot w_i \cdot c_i \cdot \alpha_i(\Delta t_i) \cdot \exp\left( -\frac{\ln(2)}{h_i} \cdot \max(0, \Delta t_i - L_i) \right)$$

### 2.5 Algoritmo de Calibración de Confianza, Coherencia y Ambigüedad

Para transformar las magnitudes vectoriales en una proyección probabilística accionable:

#### 2.5.1 Masa de Fuerza Bruta Total ($F_{\text{gross}}(t)$)

$$F_{\text{gross}}(t) = \sum_{i=1}^N w_i \cdot c_i \cdot \alpha_i(\Delta t_i) \cdot D_i(\Delta t_i)$$

#### 2.5.2 Índice de Coherencia Direccional ($\text{Coh}(t)$)

Mide el grado de alineación unívoca entre las distintas fuerzas macroeconómicas presentes:

$$\text{Coh}(t) = \begin{cases}
\frac{|F_{\text{net}}(t)|}{F_{\text{gross}}(t)} & \text{si } F_{\text{gross}}(t) > 0 \\
0.0 & \text{si } F_{\text{gross}}(t) = 0
\end{cases}$$

* $\text{Coh}(t) \to 1.0$: Consenso macroeconómico pleno (todas las fuerzas empujan en la misma dirección).
* $\text{Coh}(t) \to 0.0$: Fuerzas contrapuestas de similar intensidad en colisión directa (alta ambigüedad).

#### 2.5.3 Índice de Cobertura de Evidencia ($\text{Cov}(t)$)

Previene la sobreestimación de certeza ante una muestra estadística insuficiente:

$$\text{Cov}(t) = \min\left(1.0, \frac{F_{\text{gross}}(t)}{\Omega_{\text{ref}}}\right)$$

Donde $\Omega_{\text{ref}} = 1.50$ es el nivel de masa de eventos representativo de un entorno con información suficiente.

#### 2.5.4 Regla Direccional y Umbral de Decisión

Con un umbral direccional calibrado $\theta = 0.25$:

$$\text{Dirección Proyectada} = \begin{cases}
\text{SUBE} & \text{si } F_{\text{net}}(t) > +\theta \\
\text{BAJA} & \text{si } F_{\text{net}}(t) < -\theta \\
\text{ESTABLE / LATERAL} & \text{si } |F_{\text{net}}(t)| \le \theta
\end{cases}$$

#### 2.5.5 Cálculo de Confianza Calibrada ($C_t$)

$$C_t = \left( \gamma_1 \cdot \text{Coh}(t) + \gamma_2 \cdot \text{Cov}(t) \right) \times 100$$

Donde:
* $\gamma_1 = 0.65$: Peso asignado a la consistencia direccional interna.
* $\gamma_2 = 0.35$: Peso asignado a la densidad y solidez fáctica de la evidencia.

#### 2.5.6 Salvaguardas Fail-Closed del Modelo

1. **Incertidumbre Extrema por Colisión:** Si $F_{\text{gross}}(t) \ge 1.00$ y $\text{Coh}(t) < 0.20$, el sistema **DEBE** forzar el veredicto a `ESTABLE`, restringir $C_t \le 45.0\%$ e incluir el flag `HIGH_AMBIGUITY_COLLIDING_FORCES`.
2. **Evidencia Insuficiente:** Si $F_{\text{gross}}(t) < 0.20$, el sistema **DEBE** forzar el veredicto a `ESTABLE`, restringir $C_t \le 35.0\%$ e incluir el flag `INSUFFICIENT_MACRO_EVIDENCE`.

---

## 3. Taxonomía Canónica de 14 Eventos Macroeconómicos

### 3.1 Tabla Maestra Canónica

| Código Canónico | Nombre del Evento | Categoría | Condición Disparadora | Dir. ($d_i$) | Peso ($w_i$) | Canal de Transmisión | Latencia ($L_i$) | Semivida ($h_i$) | Fuente Primaria | Fuente Fallback |
| :--- | :--- | :--- | :--- | :---: | :---: | :--- | :---: | :---: | :--- | :--- |
| `EVT_PATRIA_GUERRA_ACTIVOS` | Bono Guerra Económica: Activos y Cestaticket | `GASTO_PUBLICO_PATRIA` | Inicio de abono mensual días 12-15 en BDV/Patria | **+1 (SUBE)** | 0.90 | Acreditación BDV $\rightarrow$ Pago Móvil $\rightarrow$ Compra masiva retail USDT | 1.0 h | 36.0 h | Telegram `@PatriaDigital` | Blog Patria / X `@BonosSocial` |
| `EVT_PATRIA_GUERRA_JUBILADOS` | Bono Guerra Económica: Jubilados y Pensionados | `GASTO_PUBLICO_PATRIA` | Inicio de abono mensual días 16-22 en Patria | **+1 (SUBE)** | 0.65 | Monederos Patria $\rightarrow$ Retiro bancario $\rightarrow$ Consumo y cobertura familiar | 2.0 h | 24.0 h | Telegram `@PatriaDigital` | Blog Patria / X `@CarnetDLaPatria` |
| `EVT_PATRIA_AGUINALDOS_FRAC` | Desembolso de Fracción de Aguinaldos Públicos | `GASTO_PUBLICO_PATRIA` | Ejecución de cuotas de fin de año (Oct-Dic) | **+1 (SUBE)** | 1.00 | Inyección masiva de masa monetaria sin respaldo $\rightarrow$ Vaciado de bolívares hacia USDT | 1.5 h | 72.0 h | MPPEF / Medios Financieros | Canales Gremiales / Banca y Negocios |
| `EVT_BCV_INTERVENCION_REGULAR` | Intervención Cambiaria Semanal Ordinaria ($50M-$90M) | `INTERVENCION_CAMBIARIA_BCV` | Adjudicación bancaria de lunes en rango regular | **-1 (BAJA)** | 0.70 | Asignación de divisas a bancos $\rightarrow$ Drenaje de encaje VES $\rightarrow$ Demanda satisfecha | 2.0 h | 36.0 h | Banca y Negocios | Portal Oficial BCV |
| `EVT_BCV_INTERVENCION_AGRESIVA` | Intervención Extraordinaria / Shock (> $120M) | `INTERVENCION_CAMBIARIA_BCV` | Asignación semanal acumulada > $120M o extensión jueves | **-1 (BAJA)** | 0.95 | Sobreoferta de divisas en mesas $\rightarrow$ Parálisis temporal de compras en P2P | 1.0 h | 48.0 h | Portal Oficial BCV | Banca y Negocios |
| `EVT_BCV_INTERVENCION_DEFICIT` | Intervención Restringida / Insuficiente (< $40M) | `INTERVENCION_CAMBIARIA_BCV` | Monto semanal adjudicado menor a $40M | **+1 (SUBE)** | 0.85 | Déficit de divisas en la banca $\rightarrow$ Desvío compulsivo de empresas a Binance P2P | 3.0 h | 40.0 h | Banca y Negocios | Finanzas Digital |
| `EVT_BCV_LIQUIDEZ_M2_SPIKE` | Expansión Semanal Acelerada de M2 (> 3.5%) | `POLITICA_MONETARIA_LIQUIDEZ` | Reporte viernes BCV muestra $\Delta \text{M2} > 3.5\%$ semanal | **+1 (SUBE)** | 0.60 | Ajuste de expectativas en tesorerías y formadores de mercado P2P | 12.0 h | 96.0 h | BCV (Estadísticas M2) | Finanzas Digital / OVF |
| `EVT_SENIAT_PAGO_QUINCENA` | Vencimiento Anticipos IVA/ISLR Especiales | `CALENDARIO_FISCAL_SENIAT` | Días 18-25 del mes; vencimiento según calendario RIF | **-1 (BAJA)** | 0.65 | Obligación tributaria en VES $\rightarrow$ Venta forzada de USDT por empresas para pagar al fisco | 0.5 h (anticipado) | 24.0 h | Calendario SENIAT en Gaceta | Portal Fiscal SENIAT |
| `EVT_SENIAT_ZAFRA_ISLR_MAR` | Cierre de Zafra Anual ISLR (Marzo) | `CALENDARIO_FISCAL_SENIAT` | Periodo 15 al 31 de marzo; cierre del ejercicio fiscal | **-1 (BAJA)** | 0.85 | Drenaje histórico colosal de bolívares hacia el Tesoro Nacional $\rightarrow$ Sequía de VES | 24.0 h (anticipado) | 120.0 h | SENIAT Oficial | Medios Nacionales |
| `EVT_SUDEBAN_LUNES_BANCARIO` | Feriado Bancario Nacional / Lunes Bancario | `OPERATIVA_MERCADO_P2P` | Calendario bancario SUDEBAN activo en día hábil | **0 (NEUTRAL)** | 0.50 | Cierre de mesas de cambio bancarias; el 100% de la demanda opera en P2P (spread se ensancha) | 0.0 h | 18.0 h | Calendario SUDEBAN | SUDEBAN en X (`@SudebanInforma`) |
| `EVT_OFAC_LICENCIA_RENOVADA` | Renovación / Ampliación Licencia Petrolera OFAC | `GEOPOLITICA_PETROLERA` | Emisión de General License (GL44, GL41 o similar) | **-1 (BAJA)** | 0.90 | Incremento esperado de ingresos petroleros del BCV $\rightarrow$ Calma y compresión de riesgo | 2.0 h | 168.0 h | US Department of Treasury (OFAC) | Agencias (Reuters / Bloomberg) |
| `EVT_OFAC_LICENCIA_REVOCADA` | Revocación o Vencimiento de Licencia Petrolera | `GEOPOLITICA_PETROLERA` | Cancelación o reimposición de sanciones energéticas | **+1 (SUBE)** | 1.00 | Anticipación de insolvencia de caja en divisas del BCV $\rightarrow$ Huida masiva hacia USDT | 1.0 h | 240.0 h | US Department of Treasury (OFAC) | Prensa Internacional / Medios Financieros |
| `EVT_REGULACION_FISCALIZACION` | Operativos SUNDDE/SENIAT sobre Tasa Oficial | `REGULACION_CAMBIARIA_BANCARIA` | Despliegue de inspecciones a comercios con multas | **+1 (SUBE)** | 0.70 | Miedo a transar en VES oficial $\rightarrow$ Retención de divisas $\rightarrow$ Mercado P2P se aísla y sube | 4.0 h | 48.0 h | Min. Comercio / SUNDDE | Medios Nacionales |
| `EVT_CAIDA_PAGO_MOVIL_NAC` | Incidencia Crítica en Plataforma Interbancaria | `OPERATIVA_MERCADO_P2P` | Caída de Suiche 7B, Biopago o fallas eléctricas masivas | **0 (NEUTRAL)** | 0.55 | Imposibilidad técnica de liquidar órdenes P2P en VES $\rightarrow$ Parálisis y ampliación de spread | 0.1 h | 6.0 h | Redes de Monitoreo / Usuarios | Canales de Banca Digital |

---

### 3.2 Fichas Técnicas Descriptivas por Evento

#### Ficha 1: `EVT_PATRIA_GUERRA_ACTIVOS`
* **Nombre Canónico:** Bono Contra la Guerra Económica — Trabajadores Activos y Jubilados de la Administración Pública.
* **Categoría:** `GASTO_PUBLICO_PATRIA`.
* **Condición de Activación:** Días 12 al 15 de cada mes calendario. El Sistema Patria inicia el envío de mensajes SMS a través del número 3532 anunciando la acreditación.
* **Mecanismo de Transmisión:** El Estado abona montos equivalentes a $90 - $120 USD indexados en bolívares a más de 3 millones de funcionarios. La acreditación masiva se canaliza casi inmediatamente vía BDV hacia Pago Móvil para adquisición de USDT en Binance P2P como protección familiar.
* **Parámetros Cuantitativos:** $d_i = +1.0$ (SUBE), $w_i = 0.90$, $L_i = 1.0\text{ h}$, $h_i = 36.0\text{ h}$.
* **Fuentes:** Primaria: Canal Telegram `@PatriaDigital`. Fallback: Blog Oficial Patria (`blog.patria.org.ve`).

#### Ficha 2: `EVT_PATRIA_GUERRA_JUBILADOS`
* **Nombre Canónico:** Bono Contra la Guerra Económica — Pensionados IVSS y Amor Mayor.
* **Categoría:** `GASTO_PUBLICO_PATRIA`.
* **Condición de Activación:** Días 16 al 22 de cada mes calendario, usualmente coincidiendo con el pago de la pensión básica del IVSS.
* **Mecanismo de Transmisión:** Desembolso a más de 4.5 millones de adultos mayores. Aunque la conversión directa a USDT en este grupo demográfico es menor en términos relativos per cápita, el flujo en bolívares entra a comercios de alimentos y medicinas, cuyos propietarios compran USDT de inmediato para reposición de mercancía.
* **Parámetros Cuantitativos:** $d_i = +1.0$ (SUBE), $w_i = 0.65$, $L_i = 2.0\text{ h}$, $h_i = 24.0\text{ h}$.
* **Fuentes:** Primaria: Canal Telegram `@PatriaDigital`. Fallback: Cuenta oficial de X `@BonosSocial`.

#### Ficha 3: `EVT_PATRIA_AGUINALDOS_FRAC`
* **Nombre Canónico:** Desembolso de Fracción de Aguinaldos y Bonos de Fin de Año del Sector Público.
* **Categoría:** `GASTO_PUBLICO_PATRIA`.
* **Condición de Activación:** Cuotas decretadas en los meses de octubre, noviembre y diciembre por el Ejecutivo Nacional.
* **Mecanismo de Transmisión:** Es el evento de inyección de liquidez de mayor volumen del año calendario. Millones de bolívares no respaldados inundan las cuentas de empleados del magisterio, salud y fuerzas armadas. El exceso de liquidez desborda la capacidad de absorción bancaria provocando una corrida compradora inmediata hacia USDT.
* **Parámetros Cuantitativos:** $d_i = +1.0$ (SUBE), $w_i = 1.00$, $L_i = 1.5\text{ h}$, $h_i = 72.0\text{ h}$.
* **Fuentes:** Primaria: Ministerio de Finanzas / Medios Financieros. Fallback: Banca y Negocios.

#### Ficha 4: `EVT_BCV_INTERVENCION_REGULAR`
* **Nombre Canónico:** Intervención Cambiaria Semanal Ordinaria del Banco Central de Venezuela ($50M - $90M).
* **Categoría:** `INTERVENCION_CAMBIARIA_BCV`.
* **Condición de Activación:** Cada lunes hábil entre las 09:00 y las 11:30 VET, el BCV adjudica divisas en efectivo a las mesas de cambio de la banca comercial.
* **Mecanismo de Transmisión:** La inyección de divisas satisface la demanda corporativa de importadores en la banca oficial y drena liquidez en bolívares de los bancos por concepto de débito del encaje legal, aliviando la presión sobre Binance P2P.
* **Parámetros Cuantitativos:** $d_i = -1.0$ (BAJA / CONTENCIÓN), $w_i = 0.70$, $L_i = 2.0\text{ h}$, $h_i = 36.0\text{ h}$.
* **Fuentes:** Primaria: Portal Banca y Negocios. Fallback: Página oficial del BCV (`bcv.org.ve`).

#### Ficha 5: `EVT_BCV_INTERVENCION_AGRESIVA`
* **Nombre Canónico:** Intervención Cambiaria Extraordinaria de Shock (> $120M acumulados o ventas directas en jueves).
* **Categoría:** `INTERVENCION_CAMBIARIA_BCV`.
* **Condición de Activación:** Semanas con inyecciones superiores a $120 millones de dólares o ventas extraordinarias no programadas a mitad de semana para sofocar un rally alcista.
* **Mecanismo de Transmisión:** Provoca una sobreoferta inmediata en las mesas bancarias. Grandes corporaciones posponen sus compras en el mercado P2P para comprar a tasa oficial, deprimiendo el precio del USDT en Binance y comprimiendo bruscamente la brecha cambiaria.
* **Parámetros Cuantitativos:** $d_i = -1.0$ (BAJA ACELERADA), $w_i = 0.95$, $L_i = 1.0\text{ h}$, $h_i = 48.0\text{ h}$.
* **Fuentes:** Primaria: Banco Central de Venezuela. Fallback: Banca y Negocios.

#### Ficha 6: `EVT_BCV_INTERVENCION_DEFICIT`
* **Nombre Canónico:** Intervención Cambiaria Restringida o Insuficiente (< $40M).
* **Categoría:** `INTERVENCION_CAMBIARIA_BCV`.
* **Condición de Activación:** Lunes en los cuales la adjudicación del BCV a la banca se ubica por debajo de $40 millones de dólares.
* **Mecanismo de Transmisión:** Señal de escasez y racionamiento. La banca solo puede atender una fracción menor de las órdenes de sus clientes comerciales. Las empresas recurren de urgencia a Binance P2P para garantizar sus pagos internacionales, presionando el precio fuertemente al alza.
* **Parámetros Cuantitativos:** $d_i = +1.0$ (SUBE), $w_i = 0.85$, $L_i = 3.0\text{ h}$, $h_i = 40.0\text{ h}$.
* **Fuentes:** Primaria: Banca y Negocios. Fallback: Finanzas Digital.

#### Ficha 7: `EVT_BCV_LIQUIDEZ_M2_SPIKE`
* **Nombre Canónico:** Expansión Acelerada de Liquidez Monetaria M2 (> 3.5% semanal).
* **Categoría:** `POLITICA_MONETARIA_LIQUIDEZ`.
* **Condición de Activación:** Publicación de las estadísticas de agregados monetarios por el BCV los viernes por la tarde, mostrando un crecimiento semanal superior al 3.5%.
* **Mecanismo de Transmisión:** Indica monetización de déficit fiscal. Aunque el público general no lee las tablas del BCV en tiempo real, las tesorerías bancarias y los grandes formadores de mercado P2P ajustan inmediatamente sus modelos de cobertura y precios base.
* **Parámetros Cuantitativos:** $d_i = +1.0$ (SUBE), $w_i = 0.60$, $L_i = 12.0\text{ h}$, $h_i = 96.0\text{ h}$.
* **Fuentes:** Primaria: BCV (Estadísticas de Agregados Monetarios M2). Fallback: Observatorio Venezolano de Finanzas (OVF).

#### Ficha 8: `EVT_SENIAT_PAGO_QUINCENA`
* **Nombre Canónico:** Vencimiento de Anticipos Tributarios de Sujetos Pasivos Especiales (IVA e ISLR).
* **Categoría:** `CALENDARIO_FISCAL_SENIAT`.
* **Condición de Activación:** Fechas límite fijadas por el calendario fiscal del SENIAT (habitualmente entre los días 18 y 25 de cada mes).
* **Mecanismo de Transmisión:** Las empresas clasificadas como Contribuyentes Especiales deben transferir fondos líquidos en bolívares a la cuenta del Tesoro Nacional. Para cubrir estos compromisos, las empresas liquidan masivamente inventarios de USDT en Binance P2P, generando un exceso de oferta transitorio que deprime la cotización.
* **Parámetros Cuantitativos:** $d_i = -1.0$ (BAJA / CONTENCIÓN), $w_i = 0.65$, $L_i = 0.5\text{ h}$ (anticipado), $h_i = 24.0\text{ h}$.
* **Fuentes:** Primaria: Calendario Oficial de Sujetos Pasivos Especiales (Gaceta Oficial). Fallback: Portal SENIAT.

#### Ficha 9: `EVT_SENIAT_ZAFRA_ISLR_MAR`
* **Nombre Canónico:** Cierre de Zafra Anual del Impuesto Sobre la Renta (ISLR).
* **Categoría:** `CALENDARIO_FISCAL_SENIAT`.
* **Condición de Activación:** Segunda quincena del mes de marzo de cada año (15 al 31 de marzo).
* **Mecanismo de Transmisión:** Constituye el mayor drenaje de liquidez en bolívares de todo el año. Empresas y personas naturales deben liquidar todos sus ahorros en divisas para cumplir con las declaraciones fiscales. El mercado interbancario experimenta una severa sequía de bolívares, provocando caídas pronunciadas o estancamiento prolongado de la tasa USDT/VES.
* **Parámetros Cuantitativos:** $d_i = -1.0$ (BAJA PROFUNDA), $w_i = 0.85$, $L_i = 24.0\text{ h}$ (anticipado), $h_i = 120.0\text{ h}$.
* **Fuentes:** Primaria: SENIAT Oficial. Fallback: Medios Nacionales.

#### Ficha 10: `EVT_SUDEBAN_LUNES_BANCARIO`
* **Nombre Canónico:** Feriado Bancario Nacional / Lunes Bancario SUDEBAN.
* **Categoría:** `OPERATIVA_MERCADO_P2P`.
* **Condición de Activación:** Días festivos y lunes no laborables fijados anualmente en la circular de la SUDEBAN.
* **Mecanismo de Transmisión:** Al estar cerradas las mesas de cambio bancarias y suspendidas las transferencias interbancarias tradicionales no inmediatas, el 100% de la actividad cambiaria recae en Binance P2P. La menor liquidez operativa ensancha significativamente el spread entre puntas de compra y venta ($1.5\% - 3.5\%$) sin una dirección neta unívoca.
* **Parámetros Cuantitativos:** $d_i = 0.0$ (NEUTRAL / VOLATILIDAD), $w_i = 0.50$, $L_i = 0.0\text{ h}$, $h_i = 18.0\text{ h}$.
* **Fuentes:** Primaria: Calendario SUDEBAN. Fallback: Cuenta oficial en X `@SudebanInforma`.

#### Ficha 11: `EVT_OFAC_LICENCIA_RENOVADA`
* **Nombre Canónico:** Renovación o Ampliación de Licencia Petrolera General por la OFAC.
* **Categoría:** `GEOPOLITICA_PETROLERA`.
* **Condición de Activación:** Publicación en el Registro Federal de los Estados Unidos o en el portal del Departamento del Tesoro (General License 44, 41 o equivalentes).
* **Mecanismo de Transmisión:** Asegura flujos sostenidos de exportación de crudo y liquidación de divisas a través de empresas mixtas en el mercado cambiario venezolano. Reduce la prima de riesgo país, aumenta las expectativas de oferta del BCV y calma las expectativas de devaluación.
* **Parámetros Cuantitativos:** $d_i = -1.0$ (BAJA ESTRUCTURAL), $w_i = 0.90$, $L_i = 2.0\text{ h}$, $h_i = 168.0\text{ h}$.
* **Fuentes:** Primaria: US Department of the Treasury (OFAC). Fallback: Reuters / Bloomberg.

#### Ficha 12: `EVT_OFAC_LICENCIA_REVOCADA`
* **Nombre Canónico:** Revocación, No Renovación o Endurecimiento de Sanciones Petroleras por la OFAC.
* **Categoría:** `GEOPOLITICA_PETROLERA`.
* **Condición de Activación:** Emisión de advertencias formales, caducidad de licencias vigentes o anuncios de sanciones energéticas adicionales.
* **Mecanismo de Transmisión:** Desencadena un choque de expectativas inmediato. El mercado asume una caída inminente en los ingresos fiscales de divisas del BCV. Los actores económicos huyen de forma preventiva del bolívar, provocando una escalada brusca de compras de USDT en Binance P2P.
* **Parámetros Cuantitativos:** $d_i = +1.0$ (SUBIDA CRÍTICA), $w_i = 1.00$, $L_i = 1.0\text{ h}$, $h_i = 240.0\text{ h}$.
* **Fuentes:** Primaria: US Department of the Treasury (OFAC). Fallback: Medios Financieros Internacionales.

#### Ficha 13: `EVT_REGULACION_FISCALIZACION`
* **Nombre Canónico:** Operativos de Inspección y Fiscalización SUNDDE/SENIAT sobre la Tasa Oficial.
* **Categoría:** `REGULACION_CAMBIARIA_BANCARIA`.
* **Condición de Activación:** Despliegue de inspecciones policiales o tributarias con clausura de comercios acusados de cobrar a tasa no oficial.
* **Mecanismo de Transmisión:** Provoca la negativa de comerciantes a aceptar bolívares a la tasa BCV. Los comerciantes retiran sus anuncios de venta en el mercado formal y se refugian en la adquisición de USDT en cuentas personales, fragmentando el mercado y disparando la prima de riesgo en Binance P2P.
* **Parámetros Cuantitativos:** $d_i = +1.0$ (SUBE), $w_i = 0.70$, $L_i = 4.0\text{ h}$, $h_i = 48.0\text{ h}$.
* **Fuentes:** Primaria: Ministerio de Comercio Nacional / SUNDDE. Fallback: Medios Nacionales.

#### Ficha 14: `EVT_CAIDA_PAGO_MOVIL_NAC`
* **Nombre Canónico:** Falla Crítica o Interrupción en la Plataforma Interbancaria de Pago Móvil / Suiche 7B.
* **Categoría:** `OPERATIVA_MERCADO_P2P`.
* **Condición de Activación:** Colapso temporal de telecomunicaciones bancarias, fallas eléctricas masivas o mantenimiento de conmutadores de compensación interbancaria.
* **Mecanismo de Transmisión:** Los usuarios quedan incapacitados de liquidar órdenes P2P en bolívares. El volumen transaccional cae verticalmente, los comerciantes suspenden sus anuncios para evitar órdenes abiertas no pagadas y el spread se dispara sin una dirección clara.
* **Parámetros Cuantitativos:** $d_i = 0.0$ (NEUTRAL / PARÁLISIS), $w_i = 0.55$, $L_i = 0.1\text{ h}$, $h_i = 6.0\text{ h}$.
* **Fuentes:** Primaria: Monitores de servicios digitales y reportes bancarios. Fallback: Redes oficiales de los bancos.

---

## 4. Matriz Cuantitativa de Rezagos Temporales (Lag Matrix)

### 4.1 Horizontes de Propagación del Choque

Los impactos económicos sobre el precio del USDT/VES se desenvuelven a lo largo de cuatro horizontes de tiempo definidos:

1. **$T+0$ (Intradía Inmediato: 0 a 6 horas):** Reacción inicial en los libros de órdenes de Binance P2P. Absorción de órdenes pasivas y ajuste inicial del spread.
2. **$T+1$ (Corto Plazo: 24 horas):** Absorción en el sistema bancario comercial. Compensación de transferencias masivas y liquidación comercial.
3. **$T+3$ (Mediano Plazo: 72 horas):** Reposición de inventarios comerciales mayoristas, respuesta compensatoria del BCV y efecto acumulativo en precios.
4. **$T+7$ (Semanal / Tendencial: 168 horas):** Consolidación en agregados monetarios oficiales, absorción final del shock y establecimiento de un nuevo nivel de equilibrio.

### 4.2 Matriz de Horizontes y Persistencia

| Código de Evento | Impacto en $T+0$ (0-6h) | Impacto en $T+1$ (24h) | Impacto en $T+3$ (72h) | Impacto en $T+7$ (Semanal) | Naturaleza del Shock |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `EVT_PATRIA_GUERRA_ACTIVOS` | Presión compradora inicial (+0.4% a +1.0%) | Pico de subida (+1.5% a +2.5%) | Decaimiento leve, nuevo piso nominal | Reversión marginal (queda escalón nominal) | **Escalón Permanente Parcial** |
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

## 5. Catálogo de Fuentes de Datos e Ingesta Técnica

### 5.1 Inventario de Fuentes de Datos

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

### 5.2 Filosofía Fail-Closed y Resiliencia en Ingesta

1. **Cero Secretos en Ingesta:** Ninguna credencial de Telegram (API ID/Hash) ni token de API debe exponerse en registros de error o tablas de auditoría.
2. **Rechazo ante Fuentes de Redes Sociales No Verificadas:** Noticias o rumores originados en cuentas anónimas o sin respaldo documental reciben factor de credibilidad $c_i = 0.0$ y son descartados automáticamente por el filtro anti-ruido del Buscador.
3. **Manejo de Caídas de Conectividad Oficial:** Si el portal del BCV falla o retorna 504/timeout, el sistema utiliza la última tasa confirmada auditada con su correspondiente hash SHA-256 e incrementa la incertidumbre temporal sin inventar datos.

---

## 6. Protocolo de Resolución de Interferencias y Choques Contrapuestos

### 6.1 Matriz de Choques Típicos en Venezuela

| Escenario de Choque | Fuerza A (Magnitud / Dirección) | Fuerza B (Magnitud / Dirección) | Vector Resultante ($F_{\text{net}}$) | Comportamiento Esperado en Mercado |
| :--- | :--- | :--- | :---: | :--- |
| **Lunes de Intervención vs Pago de Bono Patria** | Intervención BCV Ordinaria ($w=0.70, d=-1$) | Asignación Bono Guerra ($w=0.90, d=+1$) | $+0.20$ (Levemente Alcista) | **Compresión inicial:** En las primeras 4h la intervención frena el precio; pasadas 6h la demanda masiva de bolívares supera la oferta de divisas bancarias y el USDT cierra al alza. |
| **Lunes de Intervención vs Pago de Aguinaldos** | Intervención BCV Agresiva ($w=0.95, d=-1$) | Fracción de Aguinaldos ($w=1.00, d=+1$) | $+0.05$ (Neutral / Fuerte Volatilidad) | **Tensión Explosiva:** Spread se dispara; el BCV agota rápidamente su cupo semanal y la tasa libre rompe al alza con fuerza a las 24-48h. |
| **Cierre Fiscal SENIAT vs Pago de Quincena Pública** | Vencimiento SENIAT SPE ($w=0.65, d=-1$) | Nómina Ordinaria Pública ($w=0.55, d=+1$) | $-0.10$ (Estable / Ligera Caída) | **Apatía / Lateralidad:** Las tesorerías privadas venden dólares para pagar tributos mientras los empleados compran USDT; las fuerzas se anulan temporalmente. |
| **Revocación de Licencia OFAC vs Megaintervención BCV** | Revocación OFAC ($w=1.00, d=+1$) | Inyección BCV $150M ($w=0.95, d=-1$) | $+0.05$ (Dirección estructural ALCISTA) | **Pánico estructural domina sobre liquidez inmediata:** La intervención solo frena la subida 24h; el mercado descuenta la escasez futura de dólares. |

### 6.2 Reglas Heurísticas de Decisión para el Predictor y Revisor

1. **Regla de Asimetría Fiscal/Cambiaria de Venezuela:**  
   *En el horizonte mayor a 24 horas, la emisión inorgánica de bolívares para gasto público siempre supera la capacidad del BCV para contener el tipo de cambio mediante reservas.*
2. **Regla de Contención Transitoria:**  
   *Si una intervención del BCV ocurre dentro de las últimas 6 horas ($\Delta t \le 6\text{h}$), el modelo DEBE emitir advertencia de "Frenado o Rebote de Corto Plazo" aun cuando la proyección de 48 horas sea fuertemente ALCISTA.*
3. **Regla de Indeterminación y Veredicto Fail-Closed:**  
   *Si el índice de coherencia $\text{Coh}(t) < 0.25$ con una masa total $F_{\text{gross}}(t) \ge 1.40$, el Predictor y el Revisor tienen prohibido emitir un llamado especulativo direccional. El veredicto DEBE ser `ESTABLE / AMBIGUO` con recomendación de abstención o ampliación de márgenes de spread en el bot.*

---

## 7. Esquemas Formales de Datos para el Pipeline de IA (Pydantic v2)

```python
"""Esquemas de datos canónicos para el modelado de variables macroeconómicas."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
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
    event_id: str = Field(..., description="Identificador único, ej. EVT-202611-BCV-INT-001")
    code: str = Field(..., description="Código canónico de la taxonomía de 14 eventos o alias corto (ej. GP-01, IC-01)")
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
    raw_attributes: Dict[str, Any] = Field(default_factory=dict)

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

## 8. Guía de Mantenimiento, Gobernanza y Calibración Continua

1. **Recalibración Trimestral de Pesos:** Los pesos empíricos $w_i$, latencias $L_i$ y semividas $h_i$ deben ser revisados al inicio de cada trimestre fiscal en función de la evolución del volumen transaccional de Binance P2P y las variaciones en la política de encaje bancario del BCV.
2. **Monitoreo de Gaceta Oficial:** Cualquier modificación en el calendario de días feriados de la SUDEBAN o en las alícuotas del calendario SENIAT debe incorporarse de manera inmediata en la tabla de constantes de taxonomía en `src/core/macro/taxonomy.py`.
3. **Auditoría de Certificados SSL del BCV:** Debido a la recurrente caducidad de los certificados SSL del portal oficial del Banco Central de Venezuela, el conector `httpx` debe mantenerse bajo aislamiento en sandbox con reintentos controlados y captura de errores sin alterar la ejecución del bot comercial.
