# Proposal

> **Historia de usuario para después del MVP.** Sólo tiene la propuesta: el diseño, la spec y las
> tareas se escriben con la respuesta de Nave sobre una API de liquidaciones y con datos de
> producción (ver *Antes de diseñar*). No se aplica hasta entonces.

## Historia

**Como** contador o administrador del comercio, **quiero** que cada acreditación de Nave quede
conciliada con el cobro de Odoo que le corresponde, con la comisión y su IVA asentados, **para**
cerrar el banco sin repartir pagos a mano ni calcular diferencias cobro por cobro.

## Why

En el cierre de la sesión `POS/00001` (`tasks/plan_homologacion_nave.md` §3.42, 2026-10-09), Odoo
dejó dos pagos en *Recibos pendientes*: $1.623,44 de Nave Point y $147 de Nave QR. Nave, en cambio,
acreditó ocho importes netos por separado, en el mismo día de cada cobro. Para conciliar a mano hubo
que:

- repartir los dos pagos de Odoo entre las ocho acreditaciones del extracto;
- calcular la diferencia de cada una y asentar $73,11 de comisiones y $15,35 de IVA crédito fiscal,
  que hoy no figuran en ningún asiento.

Con un comercio que cobra todo el día, eso no es viable. Y no lo resuelve un modelo de conciliación
de Odoo, porque la comisión depende del medio de pago: 4,8 % con tarjeta, 0,8 % con QR o dinero en
cuenta, y 0 % en algunos casos, siempre más el 21 % de IVA sobre la comisión (tarifas publicadas en
<https://navenegocios.ar/home/comisiones---nave>).

Nave ya tiene todo lo necesario en el resumen del panel (*Detalles > Descargar resumen*): una fila por
cobro con bruto, comisión, IVA, neto, fecha de acreditación y el **ID externo de pago**. Ese ID es la
referencia que manda Odoo: el `uuid` de la línea de pago del POS, o la referencia de la transacción
online. En la sesión revisada, el bruto coincidió al centavo y todos los cobros de Odoo aparecieron
con su ID.

## What Changes

- **Importar las liquidaciones de Nave**, desde el Excel del panel o desde una API si Nave la tiene,
  con una fila por cobro.
- **Unir cada liquidación con su cobro de Odoo por el ID externo.** Si una fila no tiene ID externo,
  como los pagos hechos fuera de Odoo, o el ID no corresponde a ningún cobro, queda para revisar a
  mano.
- **Asentar la comisión y su IVA** en cuentas configurables: gasto por comisión e IVA crédito fiscal.
- **Dejar la acreditación neta lista para conciliar** con la línea del extracto bancario por importe
  y fecha.
- **Que no importe cómo agrupó Odoo los cobros:** un pago por sesión, o uno por cobro con
  *Identificar cliente*.
- **Lo mismo para los cobros online** (checkout y link de pago), que también acreditan el neto.

## Antes de diseñar

1. **Preguntarle a Nave** si hay una API de liquidaciones con las mismas columnas del resumen, y si el
   formato del Excel es estable (`tasks/reunion_tecnica_nave.md`, consulta 7). Con API, la importación
   puede ser automática y diaria; sin API, se carga el Excel.
2. **Ver cómo llega la acreditación al banco:** si el extracto de Galicia trae alguna referencia de
   Nave o sólo el importe. Eso define si la conciliación con el extracto puede ser automática.
3. **Revisar con el contador** las cuentas para la comisión y el IVA, y si el IVA de la comisión
   requiere un comprobante de Nave (factura de la comisión) para computarse.
4. **Decidir si *Identificar cliente* se recomienda** en los métodos de Nave. Con un pago por cobro
   la conciliación es uno a uno, pero la referencia de cada pago es genérica (§3.42).
5. **Cobros sin cobro en Odoo** (ID externo *"-"*): decidir si se registran como ingreso sin factura o
   sólo se informan.

## Capabilities

### New Capabilities

- `nave-settlement-reconciliation`: cómo se importan las liquidaciones de Nave, cómo se unen con los
  cobros de Odoo y cómo se asientan la comisión y su IVA.

### Modified Capabilities

<!-- Ninguna. -->

## Impact

- Un modelo para las liquidaciones importadas, con su vista y su importación (Excel o API).
- Configuración contable por compañía: cuentas de comisión y de IVA crédito fiscal, y diario.
- `payment_nave`: la unión con las transacciones online por referencia.
- `pos_nave`: la unión con las líneas de pago del POS por `uuid`.
