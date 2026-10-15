# Spec 005: Motor Fiscal e Historial

## QUÉ
Un módulo que consume la tabla `orders` y calcula la ganancia acumulada
aplicando un método contable (FIFO o costo promedio), generando
un reporte exportable para declaración de ISLR.

## Requisitos Funcionales
- RF-01: Implementar método FIFO y método de costo promedio ponderado.
- RF-02: Calcular costo de adquisición por cada venta, incluyendo comisiones.
- RF-03: Agrupar ganancias por período fiscal (año calendario / mensual).
- RF-04: Generar reporte Excel con dos hojas: detalle de operaciones y resumen consolidado.
- RF-05: Registrar tasa BCV del día de cada operación para conversión a bolívares.

## Requisitos No Funcionales
- RNF-01: El motor fiscal no debe tener dependencias del motor de trading.
- RNF-02: Debe poder recalcular sin afectar operaciones en vivo.

## Criterios de Aceptación
- [ ] Test verifica que FIFO y promedio dan resultados distintos (y correctos según matemática contable).
- [ ] Test verifica que el reporte Excel es válido y tiene las dos hojas.
- [ ] Test verifica que comisiones se suman al costo de adquisición.
