# Design

## Context

Ver `proposal.md` — Why. Lo que condiciona el enfoque:

- **Cómo se espera hoy un cobro.** `send_payment_request` crea la intención y devuelve la promesa de
  `_await_outcome`. El core espera esa promesa en `line.pay()` y fija el estado de la línea con el
  resultado. El polling (`_poll`) consulta cada 3 s y resuelve el cobro una sola vez con `_settle`.
- **Dónde corta hoy por falta de respuesta.** Con 3 fallos de transporte seguidos (`!data`), `_poll`
  resuelve el cobro como fallido y muestra *"Desconexión"*. Esa es la causa del cobro doble de la
  corrida 3.
- **Por qué una consulta se cuelga.** `silentCall` no tiene tiempo máximo. Con el cable desenchufado,
  la consulta no falla: queda esperando. `_poll` revisa el plazo al empezar cada vuelta, así que una
  consulta colgada lo deja sin efecto.
- **Qué guarda la línea.** Al crear la intención, `line.transaction_id` queda con su identificador, y
  sólo pasa a ser el del pago cuando el cobro se aprueba. Una línea para reintentar conserva, por lo
  tanto, el identificador de la última intención. `transaction_id` es un campo de `pos.payment`, y
  el POS guarda esos registros en IndexedDB, así que debería sobrevivir a una recarga. Se verifica
  con el pedido 104 antes de reintentarlo.
- **Qué ya existe en el backend.** `nave_check_payment_status` consulta una intención cualquiera y
  devuelve el desenlace clasificado (`nave_outcome`), con los datos del pago si lo hubo. No hace
  falta tocarlo.
- **El tope de la terminal.** La terminal abandona la espera a los ~3 minutos, antes que los 300 s
  de la intención.

## Goals / Non-Goals

**Goals:**

- Que un corte de red no le haga perder al punto de venta el rastro de un cobro que pudo haberse
  cobrado.
- Que ninguna espera del cobro dependa de que la red falle de una forma u otra.

**Non-Goals:**

- Reconciliar desde el webhook. Nave notifica los pagos presenciales a la misma URL, y eso permitiría
  enterarse sin que el punto de venta consulte, pero exige otro circuito: el webhook de pagos del
  POS hoy responde 500 (§3.31). Se trata aparte.
- Reconciliar una intención cuyo identificador nunca llegó al navegador. Si la creación de la
  intención no responde, no hay identificador para consultar después (ver Risks).
- Tests de JavaScript con Hoot.

## Decisions

### La falta de respuesta deja de terminar el cobro

`_poll` deja de resolver el cobro como fallido por fallos de transporte. Sigue consultando hasta que
Nave informe un desenlace o venza el plazo con su margen, como ya exige la spec.

*Por qué*: la terminal sigue cobrando mientras el punto de venta no puede consultarla. Darlo por
fallido es afirmar algo que no se sabe, y fue lo que dejó la línea lista para cobrar de nuevo.

*Qué ve el cajero*: con tres fallos seguidos, una notificación persistente y no bloqueante: *"Sin
conexión con Nave. El cobro puede seguir activo en la terminal: no lo cobres de nuevo ni por otro
medio. Odoo lo va a confirmar cuando vuelva la conexión."* Se cierra sola con la primera respuesta.
Se usa el servicio de notificaciones y no un diálogo, porque no hay nada que decidir: el cajero
sólo tiene que esperar, y *Cancelar* y *Forzar terminación* siguen disponibles en la línea.

### Cada consulta tiene un tiempo máximo

Las llamadas del navegador a Nave pasan por un tope de tiempo. Si no responden a tiempo, cuentan
como falta de respuesta.

| Llamada | Tope | Por qué ese valor |
|---|---|---|
| Consulta de estado (`nave_check_payment_status`) | 10 s | El backend corta su propia llamada a Nave a los 5 s. El resto es margen para el viaje hasta Odoo |
| Creación de la intención (`nave_send_payment_intent`) | 45 s | El backend espera hasta 30 s a que Nave alcance la terminal |

*Por qué en el navegador y no sólo en el backend*: el backend ya tiene sus topes. Lo que se cuelga
es el tramo del navegador a Odoo, que es justo el que se corta cuando falla la red de la caja.

*Qué pasa con la respuesta tardía*: si llega después del tope, se descarta. El cobro no cambia por
eso, porque una consulta de estado es de sólo lectura y la próxima vuelta del polling trae el mismo
dato.

### Reintentar consulta primero la intención anterior

Cuando la línea tiene una intención anterior (`transaction_id`) y el importe es un cobro, no una
devolución, *Volver a intentar* la consulta antes de crear otra:

| Lo que responde Nave | Qué hace el punto de venta |
|---|---|
| Aprobada | Carga los datos de la tarjeta y da la línea por cobrada. No crea un cobro nuevo |
| En curso o desconocido | Retoma la espera de esa misma intención |
| Rechazada, dada de baja o vencida | Crea la intención nueva, como hoy |
| No responde | No crea nada. Avisa que el cobro anterior pudo haberse cobrado y que espere a que vuelva la conexión. La línea queda para reintentar |

*Por qué siempre, y no sólo cuando el desenlace fue desconocido*: marcar "desenlace desconocido"
exigiría guardar un dato más, que tendría que sobrevivir a una recarga del POS. Consultar siempre no
necesita nada nuevo: cuesta una consulta de ~0,3 s por reintento, y el caso común —un rechazo
conocido— sigue como hoy.

*Plazo al retomar una espera*: el navegador no sabe cuándo se creó esa intención. Se usa el plazo
de respaldo (5 minutos). La intención termina antes por su cuenta, por vencimiento o por el tope de
la terminal, y Nave lo informa.

### El aviso de tiempo agotado orienta al reintento seguro

Cuando vence el plazo sin ningún desenlace, el aviso pasa a decir: *"No se pudo confirmar el cobro.
Tocá Volver a intentar: Odoo va a consultar primero el cobro anterior y no lo va a cobrar dos
veces."* El reintento es ahora el camino seguro, así que el aviso lo recomienda en lugar de mandar a
revisar la terminal.

### Cómo se prueba

La decisión sobre el desenlace ya vive en el backend y tiene tests. Lo que agrega este cambio es
orquestación en el navegador, que no tiene infraestructura de tests. Se verifica de dos formas:

- **En Node, durante la implementación**, con el mismo tipo de arnés que se usó para *Forzar
  terminación*: una consulta que falla al instante, una colgada, una que vuelve con la aprobación,
  y reintentos sobre una intención aprobada, en curso, rechazada y sin respuesta. No queda en el
  repo.
- **Con la terminal**, que es la verificación que cierra el cambio, empezando por el pedido 104.

## Risks / Trade-offs

- **[Riesgo] La creación de la intención no responde** → Si el tope de 45 s vence, el navegador no
  tiene el identificador y no puede reconciliar. La intención pudo crearse igual en la terminal. El
  aviso le dice al cajero que verifique la terminal antes de reintentar. Es el mismo margen de hoy,
  pero con un tope en lugar de una espera sin fin.
- **[Riesgo] El cajero cierra la venta por otro medio durante un corte largo** → El aviso pide
  esperar, pero no lo puede impedir. Si la red no vuelve, la decisión es del cajero.
- **[Riesgo] `transaction_id` no sobrevive a la recarga** → El reintento crearía un cobro nuevo, como
  hoy. Se verifica antes de reintentar el pedido 104, mirando el dato desde la consola.
- **[Trade-off] Una consulta extra en cada reintento** → Unos 0,3 s, a cambio de no cobrar dos veces.

## Migration Plan

Ninguna. Se despliega `pos_nave` y se recarga el POS. El pedido 104, abierto en el POS de producción,
es la primera verificación.
