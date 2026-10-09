# Design

## Context

- `_process_notification_data` recibe `payment_id` y `external_payment_id` del aviso. La transacción
  ya se buscó por `external_payment_id` == `reference`. Después consulta
  `GET …/ranty-payments/payments/{payment_id}` contra una URL de Nave y aplica el desenlace según
  `status.name`. Para `APPROVED` llama a `_set_done(..., extra_allowed_states=('cancel',))`.
- **El pago que devuelve Nave** (producción, pago `608d70dd…`) trae `external_payment_id` y
  `payment_request_id`. El ejemplo de pago de la documentación del checkout trae `external_payment_id`
  pero no `payment_request_id`.
- La intención se crea con `external_payment_id = tx.reference`, y la transacción guarda el id de la
  intención en `nave_payment_request_id`.
- La conciliación periódica toma el `payment_id` de los intentos de la propia intención y llama al
  mismo `_process_notification_data`, dentro de un savepoint por transacción.
- Según `nave-notification-intake`, el controlador acusa con 200 un `ValidationError` y responde 500
  ante cualquier otra excepción, descartando lo escrito.

## Goals / Non-Goals

**Goals:** que el desenlace sólo se aplique con un pago de esa transacción, en el webhook y en la
conciliación.

**Non-Goals:**

- Firmar o autenticar el webhook: Nave no lo ofrece.
- Comparar importes. La referencia y la intención identifican el pago. El importe puede diferir
  legítimamente, por ejemplo por un interés de cuotas que paga el cliente.
- Los cobros presenciales: no pasan por `payment.transaction`.

## Decisions

### Qué cuenta como "pago de esta transacción"

La comprobación se hace con el pago que devolvió Nave, nunca con los datos del aviso:

| `external_payment_id` del pago | `payment_request_id` del pago | Resultado |
|---|---|---|
| igual a `tx.reference` | igual a `tx.nave_payment_request_id`, o ausente, o la transacción no tiene intención | ✅ se aplica |
| ausente | igual a `tx.nave_payment_request_id` | ✅ se aplica |
| distinto de `tx.reference` | cualquiera | ❌ no corresponde |
| cualquiera | distinto de `tx.nave_payment_request_id`, si los dos existen | ❌ no corresponde |
| ausente | ausente, o la transacción no tiene intención | ❌ sin datos |

Cualquier dato presente que contradiga la transacción la rechaza. Basta un dato que coincida para
aceptarla, porque la documentación del checkout no muestra `payment_request_id`.

Alternativa descartada: **exigir siempre los dos datos.** Rechazaría pagos legítimos si Nave omite
`payment_request_id` en el checkout, como sugiere su ejemplo.

### Si no hay datos, no se aplica (fail closed)

Un pago sin `external_payment_id` ni `payment_request_id` no se puede atribuir, así que no se aplica.
Si fuera un pago real, la transacción queda como estaba y se registra como **error**, para que
alguien lo revise. La conciliación periódica la vuelve a encontrar en cada corrida, porque sigue
pendiente.

Alternativa descartada: **aceptarlo**, como hasta ahora. Es justo el agujero que se cierra, porque
un atacante elige el `payment_id`.

### Cómo se rechaza

El control va después de leer el pago y antes de cualquier escritura. El rechazo lanza
`ValidationError`, así que:

- en el webhook se acusa con 200 y se registra. El controlador ya lo hace, y no tiene sentido que
  Nave reintente;
- en la conciliación, el savepoint lo descarta, lo registra y sigue con el lote.

Los dos casos dejan un registro propio antes de lanzar la excepción: **advertencia** si un dato
contradice la transacción (aviso sospechoso), y **error** si no hay datos. El mensaje lleva la
referencia, el `payment_id` y los dos valores que no coincidieron.

## Risks / Trade-offs

- **[Riesgo] Nave cambia el `external_payment_id` del pago en algún flujo**, por ejemplo en los links
  de pago. → Antes de desplegar, verificar en producción un pago de cada flujo online disponible. Si
  pasara, la transacción queda pendiente y se registra un error, no se pierde en silencio.
- **[Trade-off] Hoy no hay pagos online de producción para verificar**: los de A1 a A18 fueron en
  sandbox, y la API de producción no los encuentra. → La forma del pago está verificada con un cobro
  presencial de producción y con el ejemplo del checkout. La primera venta online real se revisa en
  el log.

## Migration Plan

Subir `payment_nave` a `18.0.1.12.5`. Desplegar con el procedimiento de siempre, `-u payment_nave`, y
verificar versión y hash. Después repetir en producción el aviso falso de E1c, esta vez con un
`payment_id` **real** de un cobro presencial aprobado y la referencia de la transacción cancelada
`A5-S00041`. Tiene que responder 200, registrar el aviso como sospechoso y dejar la transacción
cancelada. Sin cambios de datos.
