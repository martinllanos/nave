# Proposal

## Why

La verificación de un cobro online devuelve los mismos datos que la de Nave Point: marca y tipo de
tarjeta, últimos cuatro dígitos, emisor, código de cupón, lote, código de autorización y el plan de
cuotas completo. **`payment_nave` los descarta.** De todo eso guarda sólo el `nave_payment_id`, y en
el chatter escribe la billetera utilizada, que en un pago con tarjeta viene `N/A`.

Verificado el 2026-10-05 sobre el pedido `S00007` (§3.18 del plan de homologación): el cliente pagó
**$1.263,10 en 3 cuotas con interés** —7,40% de tasa, 9,83% de costo financiero total— mientras la
transacción registra los $1.150 de la venta. Ese monto es el correcto desde la óptica del comercio,
pero **en Odoo no queda rastro de que la venta se financió, con qué tarjeta ni en cuántas cuotas**.

Dos consecuencias concretas:

- Si Nave exige ver marca, últimos cuatro, cupón, lote y plan de cuotas en el flujo online —como se
  presume que lo hará en el presencial—, hoy no los tenemos, aunque nos los esté mandando.
- Ante un reclamo no se puede responder con qué tarjeta ni en cuántas cuotas pagó el cliente sin
  entrar al panel de Nave.

`pos_nave` ya hace esta extracción desde `18.0.1.4.0`. El flujo online quedó atrás.

## What Changes

- **La marca de la tarjeta queda registrada en la transacción** usando el mecanismo que Odoo ya
  tiene para eso, de modo que aparezca donde Odoo muestra el medio de pago sin inventar un lugar
  nuevo.
- **Los datos del cobro se conservan en la transacción**: tipo y últimos cuatro dígitos, emisor,
  código de cupón, código de autorización, lote y modo de ingreso.
- **El plan de cuotas se conserva** cuando lo hay: cantidad de cuotas, si tiene interés, tasa, costo
  financiero total y **el importe que efectivamente pagó el cliente**, que puede diferir del monto de
  la venta.
- **El mensaje del chatter deja de hablar de billetera cuando el pago fue con tarjeta** y pasa a
  resumir lo que corresponde a cada medio.
- Se agrega el caso a la matriz de homologación, que hoy verifica que el cobro entre pero no que sus
  datos queden registrados.

No es breaking: hoy esos datos se pierden, así que ninguna información existente cambia de lugar.

## Capabilities

### New Capabilities

- `nave-payment-record`: qué queda registrado en Odoo de un cobro de Nave —medio, instrumento y
  financiación— y dónde puede consultarlo quien atiende al cliente o concilia.

### Modified Capabilities

(ninguna: el proyecto todavía no tiene specs publicadas)

## Impact

- `payment_nave/models/payment_transaction.py`: campos nuevos, extracción en
  `_process_notification_data` y el mensaje del chatter.
- `payment_nave/views/`: los datos en el formulario de la transacción.
- `payment_nave/tests/test_nave_payment.py`: cobertura con los payloads reales de un pago con
  tarjeta en cuotas y de uno con billetera.
- `tasks/plan_homologacion_nave.md`: el caso nuevo en el bloque A.
- `pos_nave` no se toca: ya registra estos datos por su propio camino.
