# Proposal

## Why

Una intención de pago de Nave admite **varios intentos** —su respuesta expone `payment_retries_allowed: 5` y un elemento en `payment_attempts.payments[]` por intento—, así que el botón *"Volver a intentar"* del checkout permite pagar de nuevo sobre la misma intención después de un rechazo. El módulo asume que una transacción llega una sola vez a un estado terminal: al primer rechazo la manda a `cancel`, y desde ahí Odoo no permite pasar a `done`.

Observado en vivo el 2026-10-05 (pedido `S00005`): rechazo por `no_amount_available`, reintento con otra tarjeta, Nave aprueba y notifica, y Odoo descarta la aprobación con

```
tried to write on transaction with reference S00005 with illegal value for the state
(previous state: cancel, target state: done)
```

La transacción quedó en `cancel` con el mensaje del rechazo **y el `nave_payment_id` del pago exitoso encima**: un registro que se contradice. El pedido no se confirmó y nada avisó del problema.

**Es dinero cobrado y no registrado**, en el camino que recorre cualquier cliente al que le rechazan la tarjeta y prueba con otra.

## What Changes

- **Una aprobación posterior recupera la transacción**, aunque un intento anterior la haya dejado en `cancel`. Se usa el mecanismo que Odoo provee para esto (`_set_done` admite estados de origen adicionales).
- **La recuperación queda registrada de forma visible** en el documento: quien mira el pedido tiene que poder ver que hubo un rechazo previo y que un intento posterior prosperó, porque el estado final por sí solo no lo cuenta.
- **El rechazo deja de ser el final de la historia**: pasa a ser el resultado de *un intento*, no de la transacción.
- Se agrega el caso a la matriz de homologación (`tasks/plan_homologacion_nave.md`), que hoy no lo contempla.

No es breaking: hoy esa aprobación se descarta, así que ninguna transacción pierde un estado que tuviera antes.

## Capabilities

### New Capabilities

- `nave-transaction-lifecycle`: cómo una transacción de Nave atraviesa los intentos de pago de una misma intención hasta su desenlace, y qué queda registrado de ese recorrido.

### Modified Capabilities

(ninguna: el proyecto todavía no tiene specs publicadas; `nave-payment-provider` existe sólo como delta del cambio `split-payment-link-pos-id`, y cubre la identidad del comercio, no el ciclo de vida)

## Impact

- `payment_nave/models/payment_transaction.py`, `_process_notification_data`: el mapeo de estados y el registro en el chatter.
- `payment_nave/tests/test_nave_payment.py`: cobertura del rechazo seguido de aprobación.
- `tasks/plan_homologacion_nave.md`: el caso nuevo en el bloque A.
- Operación: la transacción `S00005` del entorno quedó con un cobro real sin registrar. Hay que resolverla a mano, porque este cambio no reprocesa lo ya ocurrido.
