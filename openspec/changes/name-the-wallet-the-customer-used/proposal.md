# Proposal

> **Historia de usuario para después de la salida a producción.** Sólo tiene la propuesta: el
> diseño, la spec y las tareas se escriben cuando haya datos reales y la respuesta de Nave (ver
> *Antes de diseñar*). No se aplica hasta entonces.

## Historia

**Como** cajero o cliente que paga con un QR, **quiero** que el ticket y el comprobante digan con
qué billetera o banco pagué (*Belo*, *MODO*, *Mercado Pago*, la app de un banco), **para**
reconocer el pago a primera vista y poder reclamarlo si hace falta.

## Why

En el cobro del bloque H (`tasks/plan_homologacion_nave.md` §3.40, 2026-10-08), el cliente pagó con
**Belo** y el ticket del POS imprimió *"Billetera: bind pago"*. Nave informa en `wallet.name` (o en
`payment_method.wallet_name`) el **procesador** del pago, no la app que usó el cliente. *Bind* es
el procesador que usa Belo.

Odoo imprime lo que manda Nave, así que el dato es correcto pero no le sirve a quien lo lee: el
cliente no reconoce *"bind pago"*. Y el cajero, ante un reclamo, tampoco sabe qué billetera buscar.

## What Changes

- **Un diccionario de procesador → billetera o banco**, editable, que traduzca el nombre que informa
  Nave al que reconoce el cliente. Por ejemplo, `bind pago` → *Belo*.
- **El ticket del POS y el resumen del cobro online muestran el nombre traducido.** Si el procesador
  no está en el diccionario, se muestra el que mandó Nave, como hoy. Nunca queda vacío.
- **El nombre que manda Nave se sigue guardando tal cual**, para conciliar y para soporte.
- **Cada procesador que no esté en el diccionario queda registrado**, para completarlo con los datos
  de producción.

## Antes de diseñar

1. **Preguntarle a Nave** si tienen la relación entre procesador y billetera o banco, o un campo con
   el nombre de la app que vio el cliente (`tasks/reunion_tecnica_nave.md`, consulta 9). Si lo
   tienen, el diccionario puede no hacer falta.
2. **Juntar los valores reales** de `nave_wallet_name` en producción, con la billetera que usó el
   cliente cuando se sepa. Hasta hoy: `mercado pago` (sandbox), `bind pago` (Belo) y
   `banco galicia - modo` (app de Galicia, §3.41). Junto con el nombre, Nave manda
   `wallet.coelsa_id` (`"88"` para Galicia) y el CUIT de la entidad: el `coelsa_id` puede ser
   mejor clave que el nombre, si es el identificador de la entidad en el sistema de transferencias.
3. **Decidir dónde vive el diccionario:** un modelo editable por compañía, datos del módulo o las
   dos cosas, con valores de fábrica que el comercio pueda corregir.

## Capabilities

### New Capabilities

<!-- Ninguna. -->

### Modified Capabilities

- `nave-payment-record`: la billetera registrada se muestra con el nombre que reconoce el cliente,
  y se conserva el que informó Nave.

## Impact

- `payment_nave/models/payment_transaction.py`: el resumen del cobro (`_nave_payment_summary`) y el
  registro de la billetera.
- `pos_nave/static/src/app/payment_nave.js`: el texto del ticket (`_format_receipt`).
- Un modelo o datos nuevos para el diccionario, con su vista de configuración.
