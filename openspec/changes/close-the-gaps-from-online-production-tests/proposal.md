# Proposal

## Why

Las pruebas de cobros online en producción del 2026-10-09 (`tasks/plan_homologacion_nave.md` §3.46 a
§3.50) funcionaron de punta a punta: tienda, portal de facturas y el asistente de link de Nave cobran,
y Odoo registra los pagos. Pero dejaron ocho problemas. Dos ponen en juego dinero.

1. **🔴 Un documento puede quedar con varios links cobrables** (B6c). Generamos tres links para la
   factura `FA-C 00001-00000021` y pagamos el último. Los otros dos siguieron *PENDING* en Nave, uno
   hasta el 16/10: el cliente podía pagar dos veces la misma factura. Los dimos de baja a mano.
2. **🔴 La conciliación periódica no reconoce una intención dada de baja.** Nave responde
   `400 payment_request_is_disabled` en lugar de un estado `DISABLED`. La conciliación de los cobros
   online lo toma como error, así que la transacción queda pendiente para siempre y registra un error
   en cada corrida. El POS ya trata ese 400 como baja.
3. **⚠️ El asistente acepta cualquier validez del link** (B5c). Con 0 horas, Nave lo dejó vigente 7
   días.
4. **El chatter muestra el HTML crudo** del mensaje del link: `<b>Link de Pago Nave generado:</b>…`.
5. **La transacción queda con el medio *Tarjeta*** aunque se pagó con QR y billetera (§3.47). El
   módulo corrige el medio según la marca de la tarjeta, pero con billetera lo deja como está.
6. **`provider_reference` queda vacío** en todas las transacciones (§3.46). Es el campo estándar de
   Odoo para la referencia del proveedor, y el código de operación de Nave es lo que figura en su panel
   y en su resumen de liquidaciones.
7. **Una factura pagada por link tarda hasta 10 minutos en marcarse como pagada** (B1c). El link se
   paga fuera del sitio, sin página de retorno, así que el pago contable espera la tarea programada de
   post-proceso.
8. **Dos textos del log confunden:** el registro de `invalid_pos` pide revisar el proveedor también en
   el POS (§3.43), y ante un aviso sospechoso el controlador agrega que *"puede ser un cobro del punto
   de venta"* (§3.44).

## What Changes

- **Un documento tiene un solo link cobrable a la vez.** Al generar un link nuevo, se dan de baja en
  Nave los links pendientes del mismo documento. Cuando se aprueba un cobro, se dan de baja los demás
  links pendientes del documento. Las transacciones dadas de baja quedan canceladas en Odoo.
- **La conciliación reconoce una intención dada de baja** y cancela la transacción, sin error.
- **La validez del link va de 1 a 168 horas**, que es el máximo que ofrece el panel de Nave.
- **El chatter muestra el link como un link.**
- **El medio de la transacción refleja cómo se pagó**: *QR Interoperable Nave* si fue con billetera o
  transferencia.
- **`provider_reference` guarda el código de operación de Nave.**
- **Al aprobarse un cobro, el post-proceso se adelanta**: se dispara la tarea programada en el acto,
  sin hacer la contabilidad dentro del aviso.
- **Los textos del log dicen lo que pasó** en cada caso.

## Capabilities

### New Capabilities

<!-- Ninguna. -->

### Modified Capabilities

- `nave-payment-request`: un documento no queda con dos links cobrables, y la validez del link está
  acotada.
- `nave-transaction-lifecycle`: una intención dada de baja cancela la transacción, y un cobro aprobado
  se refleja en el documento sin esperar la tarea programada.
- `nave-payment-record`: el medio de pago refleja cómo se pagó, y la referencia del proveedor es el
  código de operación de Nave.

El chatter y los textos del log no cambian requisitos.

## Impact

- `payment_nave/models/nave_link_wizard.py`: validez, baja de los links anteriores y mensaje del
  chatter.
- `payment_nave/models/payment_transaction.py`: baja de los links hermanos al aprobarse un cobro,
  conciliación de intenciones dadas de baja, medio de pago, `provider_reference` y disparo del
  post-proceso.
- `payment_nave/models/payment_provider.py`: el texto de `_nave_log_invalid_pos`.
- `payment_nave/controllers/main.py`: el texto ante un aviso que no se aplica.
- `pos_nave/models/pos_payment_method.py`: la indicación de qué revisar en el registro de
  `invalid_pos`.
- Pruebas de los dos módulos y versiones.
