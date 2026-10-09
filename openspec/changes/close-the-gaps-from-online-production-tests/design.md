# Design

## Context

- **Cobros de un documento.** Cada intento crea una `payment.transaction` de Nave con `invoice_ids` o
  `sale_order_ids` y su `nave_payment_request_id`: el asistente de link
  (`nave_link_wizard.action_generate_link`), el portal de la factura y la tienda. Los dos primeros
  usan el endpoint `payment_link`; la tienda, `ecommerce` (`payment_transaction.py:55`).
- **Baja de una intención.** `DELETE /api/payment_requests/{id}` con
  `{"reason": {"code": "disabled_from_saas", "description": "disabled from SAAS"}}`, que es el único
  texto aceptado (§3.36). Funciona sobre intenciones `payment_link` pendientes: dimos de baja así los
  dos links de B6c, y Nave respondió 200. Sobre una intención ya dada de baja o cobrada, Nave la
  rechaza.
- **Consulta de una intención dada de baja**: `400 {"code":"payment_request_is_disabled"}`.
  `_nave_poll_payment_request` hace `raise_for_status()` antes de leer el estado.
- **Post-proceso.** Odoo crea el `account.payment` y concilia en `_post_process`, que corre desde
  `/payment/status` o desde la tarea `payment.cron_post_process_payment_tx`, cada 10 minutos.
  `ir.cron._trigger()` la agenda para correr cuanto antes, en otro proceso.
- **Medio de pago.** `_nave_apply_card_brand` cambia `payment_method_id` a la marca, si el proveedor la
  tiene. Con billetera, Nave informa `payment_method.type = transfer_payment` y `payment_input =
  wallet`.
- `nave_payment_code` ya guarda el código de operación (`payment_code`), y `provider_reference` queda
  vacío.

## Goals / Non-Goals

**Goals:** los ocho puntos de la propuesta, sin cambiar el flujo de cobro.

**Non-Goals:**

- Devolver un cobro duplicado si igual ocurre, por ejemplo con dos pagos casi simultáneos. Queda
  registrado como advertencia, y la devolución sigue siendo manual mientras no estén las devoluciones
  por API.
- Dar de baja intentos viejos de la **tienda** al empezar uno nuevo. El cliente puede tener abierta la
  pestaña del intento anterior. Esos intentos se dan de baja recién cuando se aprueba un cobro del
  pedido.
- Traducir el mensaje *"is pending"* del core.

## Decisions

### Los cobros hermanos se dan de baja en dos momentos

Son hermanos los cobros de Nave con algún documento en común (`invoice_ids` o `sale_order_ids`), en
`draft` o `pending` y con intención, excepto el propio. Un método
`_nave_cancel_sibling_requests()` los da de baja:

- **en el asistente, antes de crear el cobro nuevo**, para el documento del asistente;
- **al aprobarse un cobro**, después de `_set_done`, en `_process_notification_data`.

Para cada hermano se manda el `DELETE`. Si Nave responde 200, o si la intención ya estaba dada de baja
(`payment_request_is_disabled`), el cobro pasa a cancelado con el motivo. Cualquier otra respuesta
queda en el log como **error**, con la referencia y la respuesta, y el cobro queda como estaba: lo
retoma la conciliación. La falla de un hermano nunca interrumpe el asistente ni el aviso.

Si un hermano resulta ya cobrado, el `DELETE` falla y queda el error. Si después llega su aviso, la
segunda aprobación del mismo documento se registra como **advertencia de cobro duplicado**.

Alternativas descartadas:

- **Reusar el link pendiente en vez de crear otro.** El monto o la validez pueden haber cambiado, y el
  asistente existe justamente para generar uno nuevo.
- **Dar de baja sólo en el asistente.** No cubre el portal, donde cada *Pagar ahora* crea un intento
  nuevo (§3.48).

**Riesgo aceptado.** Las bajas son llamadas externas. Si el aviso falla después y el savepoint
descarta la aprobación, los hermanos ya quedaron dados de baja en Nave. Es inocuo: no eran el cobro que
se pagó, y el reintento del aviso vuelve a aprobarlo.

### El 400 de una intención dada de baja se lee como estado

En `_nave_poll_payment_request`, un `400` cuyo cuerpo trae `code = payment_request_is_disabled` se
trata como `DISABLED`: `_set_canceled` con el motivo, sin excepción. Cualquier otro error sigue
propagándose, como hasta ahora.

### La validez se valida en el asistente

Una restricción `@api.constrains('duration_hours')` exige un valor entre 1 y 168, con un mensaje que
indica el rango, y la ayuda del campo lo dice. Se valida antes de crear el cobro, así que no deja
cobros huérfanos.

### El chatter usa `Markup`

`Markup(_("…<a href='%(url)s'>%(url)s</a>…")) % {…}` escapa los valores y deja el HTML del texto.

### El medio de pago se corrige también con billetera

`_nave_apply_card_brand` pasa a `_nave_apply_payment_method(payment_data)`:

- con `card_brand`, la marca, como hasta ahora;
- con `payment_method.type = transfer_payment` o `payment_input = wallet`, el método `nave_qr` del
  proveedor, si lo tiene vinculado;
- si no, el medio queda como estaba.

### `provider_reference` toma el código de operación

`_nave_store_payment_details` escribe `provider_reference = payment_code`. Sólo se completa si
viene, para no pisarlo con un vacío.

### El post-proceso se dispara, no se ejecuta en el aviso

Después de aprobar un cobro, `self.env.ref('payment.cron_post_process_payment_tx')._trigger()`. La
contabilidad corre en el proceso de la tarea programada, apenas termina el aviso.

Alternativa descartada: **llamar a `_post_process()` dentro del aviso.** Un error contable haría
fallar el aviso, el savepoint descartaría la aprobación y Nave reintentaría un cobro que ya se cobró.

### Los textos del log

- `_nave_log_invalid_pos(exc, payment_type, pos_id, hint=None)`: el POS pasa *"revisá el ID del punto
  de venta del método de pago"*, y los cobros online, la indicación actual.
- El controlador ante un `ValidationError`: si existe una transacción de Nave con esa referencia, anota
  *"Aviso de Nave que no se aplica"* con el motivo. Si no existe, el texto actual (*"no corresponde a
  ninguna transacción del sitio…"*).

## Risks / Trade-offs

- **[Riesgo] Dar de baja un link que el cliente está pagando en ese momento.** → El cliente ve un
  error en la página de Nave, o Nave rechaza el `DELETE` porque ya está cobrado. En el segundo caso,
  la advertencia de cobro duplicado lo deja a la vista.
- **[Trade-off] Más llamadas a Nave al aprobar un cobro**, una por hermano. → En la práctica son cero o
  pocas por documento.

## Migration Plan

Subir `payment_nave` a `18.0.1.13.0` y `pos_nave` a `18.0.1.11.4`. Desplegar con `-u
payment_nave,pos_nave` y verificar versiones y hashes. No hay datos que migrar. Las transacciones
pendientes con intenciones ya dadas de baja, como las dos de B6c, las cancela la próxima corrida de la
conciliación.

Verificación en producción, con pagos reales chicos:

- dos links para una factura, pagando el segundo: el primero queda dado de baja y cancelado al generar
  el segundo;
- la factura queda pagada en menos de un minuto;
- el chatter muestra un link clickeable;
- la validez 0 se rechaza;
- las transacciones de B6c quedan canceladas sin error;
- la transacción de un pago con QR muestra *QR Interoperable Nave* y el código de operación.
