# Proposal

## Why

Desde una orden del punto de venta no se ve con qué código cobró Nave. La pestaña *Pagos* muestra
fecha, método, importe, modo y datos de tarjeta, pero no el número de referencia del pago (el cupón
que va impreso en el ticket, por ejemplo `BAQ334646587`) ni el ID de transacción de Nave.

Odoo sí guarda esos datos. En la orden `POS 1/0019` de producción, el pago con *Nave QR* tiene
`payment_ref_no = BAQ334646587`, `transaction_id = 21232e74-…` y el código de autorización. Los
nueve pagos Nave del punto de venta tienen la referencia y el ID cargados. El problema es sólo de
vista. La lista de pagos de la orden del núcleo (`point_of_sale.view_pos_pos_form`) no incluye esos
campos. El formulario del pago sí los muestra, pero esa lista es editable en línea y un clic sobre
la fila no lo abre.

Sin el código, para buscar en el panel de Nave el cobro de una venta, o para atender un reclamo, hay
que pedir el ticket impreso o consultar la base. Ya pasó en las pruebas de producción y va a pasar en
la demo.

## What Changes

- **Pestaña *Pagos* de la orden.** Se agregan como columnas el **número de referencia de pago**
  (`payment_ref_no`) y el **ID de transacción de pago** (`transaction_id`), visibles por defecto. El
  **código de autorización** (`payment_method_authcode`) se agrega como columna opcional oculta.
  - Las tres columnas son de sólo lectura: el ID de transacción es el que se usa para consultar o
    devolver el pago en Nave, y no debe poder editarse desde la orden.
  - En las filas de pagos sin esos datos (efectivo, por ejemplo) la celda queda vacía.
- **Lista *Punto de venta > Órdenes > Pagos*.** Se agregan las mismas columnas, la referencia y el ID
  como opcionales visibles. El buscador permite **encontrar un pago por su número de referencia o por
  su ID de transacción**, que es el camino inverso: del panel de Nave a la orden de Odoo.
- Las etiquetas son las del núcleo, ya traducidas ("Número de referencia de pago", "ID de transacción
  de pago", "Código APPR de pago"). Los campos son genéricos de `pos.payment` y sirven también para
  otros proveedores de terminal.

No cambia qué datos se guardan ni cómo se cobra.

## Capabilities

### New Capabilities

Ninguna.

### Modified Capabilities

- `nave-payment-record`: hoy exige que los datos del cobro sean consultables desde la *transacción*
  (`payment.transaction`, cobros online). Se agrega el requisito equivalente para el cobro
  presencial: consultables desde la orden del punto de venta y buscables desde la lista de pagos.

## Impact

- `pos_nave/views/pos_order_views.xml` (nuevo): herencia de `point_of_sale.view_pos_pos_form`, de
  `point_of_sale.view_pos_payment_tree` y de `point_of_sale.view_pos_payment_search`.
- `pos_nave/__manifest__.py`: alta del archivo de vistas y versión **18.0.1.11.5**.
- Tests: un caso que verifique que las vistas resultantes incluyen los campos.
- Sin cambios en modelos, datos ni JavaScript del punto de venta. Para desplegarlo hay que actualizar
  el módulo (`-u pos_nave`).
