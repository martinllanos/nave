# Proposal

## Why

La prueba E1c (`tasks/plan_homologacion_nave.md` §3.44, 2026-10-09) confirmó en producción que el
SSRF está cerrado: una `payment_check_url` ajena se ignora. Pero mostró otro agujero.

El webhook trae la referencia de la transacción (`external_payment_id`) y el `payment_id`. Odoo le
pregunta a Nave por ese `payment_id` y, si está aprobado, da por pagada la transacción de la
referencia. **Nunca comprueba que el pago sea de esa transacción.** Lo reprodujimos en local, sin
tocar producción y con rollback: un aviso con la referencia de una transacción de $50 cancelada y el
`payment_id` de un pago aprobado de $150 de otra venta dejó la de $50 **pagada**, asociada al pago
ajeno. Que la transacción estuviera cancelada no la protege, porque una aprobación posterior puede
pasarla a pagada (así se contempla el reintento del cliente, A16).

El webhook no viene firmado, así que cualquiera puede mandar un aviso. Lo único que hace falta es un
`payment_id` aprobado del comercio: un UUID difícil de adivinar, pero que no es secreto.

Nave ya devuelve lo necesario para cerrarlo. El pago trae su `external_payment_id`, que es la
referencia que mandó Odoo al crear la intención, y su `payment_request_id`. Lo verificamos en
producción, en sólo lectura.

## What Changes

- **Antes de aplicar un desenlace, Odoo comprueba que el pago verificado sea de la transacción**: su
  `external_payment_id` tiene que ser la referencia de la transacción, y su `payment_request_id`, la
  intención de la transacción, cuando las dos existen.
- **Un pago que no corresponde no cambia nada.** El aviso queda registrado como sospechoso y se
  acusa con 200, porque reintentarlo no cambia el resultado.
- **Si Nave no informa a qué transacción pertenece el pago, tampoco se aplica**, y se registra como
  error para que alguien lo revise.
- **Los reintentos de una misma intención siguen funcionando**: todos sus pagos llevan la misma
  referencia.
- **La conciliación periódica pasa por el mismo control.**

Con esto queda resuelto también E2c (webhook sin autenticación): un aviso se aplica sólo si Nave
confirma el pago y el pago es de esa transacción.

## Capabilities

### New Capabilities

<!-- Ninguna. -->

### Modified Capabilities

- `nave-notification-intake`: se agrega que un aviso sólo se aplica si el pago que confirma Nave
  pertenece a la transacción del aviso.

## Impact

- `payment_nave/models/payment_transaction.py`: el control en `_process_notification_data`.
- Pruebas: `payment_nave/tests/test_nave_payment.py` y `test_nave_webhook.py`. Las respuestas
  simuladas de pagos de las pruebas existentes no traen `external_payment_id` y hay que completarlas.
- Versión de `payment_nave`.
- Sin cambios en `pos_nave`: los cobros presenciales no pasan por este camino.
