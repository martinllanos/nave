# Proposal

## Why

El webhook de cobros online responde 500 a cada pago aprobado en el punto de venta, y Nave lo
reintenta. Lo vimos en C7c (`tasks/plan_homologacion_nave.md` §3.38): Nave avisó el pago de $800 a
las 04:14:54, 04:16:03 y 04:21:31, y las tres veces el log registró un error.

Nave manda los avisos de todos los pagos a la misma URL de notificación, también los de la terminal.
El aviso de un pago presencial trae como referencia el identificador de la línea de pago del POS,
que no es una transacción del sitio. `payment_nave` no la encuentra, lanza un `ValidationError`, y
el controlador lo trata como una falla de Odoo: responde 500 para que Nave reintente. Nave reintenta
cinco veces en unas siete horas y media. El POS no necesita ese aviso: resuelve el cobro consultando
la intención.

Así, el log se llena de errores falsos y no sirve para ver los verdaderos. Nave, además, recibe una
falla por cada venta presencial. Odoo resuelve lo mismo en su propio módulo de Stripe: un aviso que no
se puede aplicar se registra y se acusa con 200 (`payment_stripe/controllers/main.py:160`). El caso
estaba previsto en D4c.

Mirando ese código apareció el caso inverso. Si la consulta del pago a Nave falla por la red, la
transacción online pasa a **error** y el webhook responde 200. Un corte pasajero cierra una
transacción que quizás se cobró. Nave no reintenta, porque recibió 200, y la conciliación periódica
no la vuelve a mirar, porque sólo consulta las pendientes.

## What Changes

- **Un aviso que no corresponde a ninguna transacción del sitio se acusa con 200** y queda en el log
  como información, sin error. Incluye los avisos de pagos del punto de venta.
- **Si la consulta del pago a Nave falla, la transacción queda como estaba** y el webhook responde
  500, para que Nave reintente. La conciliación periódica, que pasa por la misma consulta, deja la
  transacción pendiente y la vuelve a intentar en la corrida siguiente.
- **Una falla de Odoo al procesar un aviso no deja cambios a medias**: lo que se haya escrito se
  descarta antes de responder 500.

No cambian los 400 por JSON inválido o campos faltantes (D2c, D3c) ni el tratamiento de los estados
que informa Nave.

## Capabilities

### New Capabilities

- `nave-notification-intake`: cómo se reciben los avisos de Nave. Qué se acusa, qué se rechaza y
  qué se deja para que Nave reintente. Hoy ningún requisito cubre la recepción del webhook.

### Modified Capabilities

<!-- Ninguna. -->

## Impact

- `payment_nave/controllers/main.py`: la respuesta a un aviso que no se puede aplicar, y descartar
  lo escrito cuando se responde 500.
- `payment_nave/models/payment_transaction.py`: la falla de la consulta del pago deja de cerrar la
  transacción.
- Pruebas: `payment_nave/tests/test_nave_payment.py`.
- Sin cambios en `pos_nave`: los cobros presenciales siguen resolviéndose por consulta.
