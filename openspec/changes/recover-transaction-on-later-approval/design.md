# Design

## Context

Ver `proposal.md` — Why.

`_process_notification_data` mapea el estado que devuelve Nave a una llamada del modelo base de
Odoo: `_set_done`, `_set_canceled`, `_set_pending` o `_set_error`. Esas llamadas validan de qué
estado se viene y descartan la transición si no está permitida, registrando sólo un WARNING. Hacia
`done` el base admite `draft`, `pending`, `authorized` y `error` — `cancel` no—, y acepta estados
adicionales por parámetro (`extra_allowed_states`).

## Goals / Non-Goals

**Goals:**

- Que el desenlace registrado sea el del intento que prosperó, no el del primero que llegó.
- Que una transición descartada deje de pasar inadvertida.

**Non-Goals:**

- Modelar cada intento como un registro propio. Nave los expone en `payment_attempts.payments[]`,
  pero una transacción por intento rompería la correspondencia entre `reference` y
  `external_payment_id`, que es lo que permite que el webhook encuentre la transacción.
- Reprocesar los pagos ya ocurridos. La transacción `S00005` del entorno se resuelve a mano.
- Tocar el ciclo de devoluciones, donde hay un problema emparentado —un webhook `REFUNDED` tampoco
  puede mover una transacción en `done`— que está congelado a la espera de la respuesta de Nave
  sobre el endpoint de devolución (N12 del plan de homologación).

## Decisions

### La aprobación se acepta siempre, sin ventana temporal

Se habilita `cancel` como estado de origen hacia `done`, sin condicionarlo a que la intención siga
vigente.

**Por qué**: quien decide si el dinero se movió es Nave, no nuestro reloj. Nave no aprueba un pago
sobre una intención vencida: si notifica una aprobación, el cobro ocurrió. Rechazarla por tardía no
devuelve la plata — sólo esconde el cobro, que es exactamente el defecto que este cambio corrige.

**Alternativa descartada**: aceptar la recuperación sólo mientras la intención esté vigente. Agrega
una condición que puede fallar —hay que conocer el vencimiento, y los relojes no son el mismo— para
protegerse de un caso que la API no produce. Y cuando esa condición se equivoca, el modo de fallo es
el peor posible: un cobro real descartado en silencio.

El riesgo real no es el tiempo sino el estado del negocio: la venta pudo haberse dado por perdida.
Eso se atiende haciendo visible la recuperación, no descartando el pago.

### La recuperación se cuenta en el chatter, no sólo en el estado

Al pasar de `cancel` a `done` se registra un mensaje que dice que el cobro prosperó tras un intento
rechazado.

**Por qué**: el estado final no distingue un cobro directo de uno recuperado, y esa diferencia
cambia lo que hace quien concilia o atiende al cliente. El motivo del rechazo anterior ya quedó en
el chatter, así que la historia completa se lee en orden.

### Las transiciones descartadas se registran como advertencia propia

Cuando una notificación no puede aplicarse —una aprobación que no prospera, o un rechazo que llega
sobre una transacción ya pagada— se deja constancia explícita.

**Por qué**: el WARNING del modelo base fue lo único que quedó del cobro perdido, en un log que
nadie mira. Un mensaje propio, que nombre la referencia y el desenlace que se descartó, es lo que
convierte un problema silencioso en uno diagnosticable.

**Alternativa descartada**: elevarlo a error y abortar el webhook. Devolver un fallo haría que Nave
reintente una notificación que nunca va a poder aplicarse, cinco veces durante siete horas y media,
sin que eso cambie nada.

## Risks / Trade-offs

- **Una venta dada por perdida se reactiva sola**: el pedido avanza cuando alguien ya decidió otra
  cosa. → La decisión es deliberada: es preferible a un cobro sin registrar, y el chatter deja ver
  qué pasó. La alternativa no evita el cobro, sólo lo oculta.
- **El orden de llegada de las notificaciones no está garantizado**: los reintentos de Nave se
  extienden unas siete horas y media. → De ahí el tercer requisito: un desenlace ya superado no
  puede pisar a uno más nuevo.

## Migration Plan

No hay datos que migrar: el cambio sólo afecta a notificaciones futuras.

La transacción `S00005` quedó en `cancel` con un cobro real asociado y no se corrige sola. Hay que
revisarla a mano y decidir si se registra el pago o se devuelve, antes de que el entorno acumule más
operaciones.
