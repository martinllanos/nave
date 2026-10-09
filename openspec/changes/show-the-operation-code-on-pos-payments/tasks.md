# Tasks

## 1. Las vistas

- [x] 1.1 Crear `pos_nave/views/pos_order_views.xml` con la herencia de
      `point_of_sale.view_pos_pos_form`. En la lista de `payment_ids`, después de `cardholder_name`,
      agregar `payment_ref_no` y `transaction_id` visibles, y `payment_method_authcode` con
      `optional="hide"`, los tres con `readonly="1"`. Verificar: un test lee la vista de formulario
      de `pos.order` y comprueba que la lista de pagos incluye los tres campos, de sólo lectura y con
      el código de autorización como opcional oculto.
- [x] 1.2 En el mismo archivo, heredar `point_of_sale.view_pos_payment_tree` para agregar después de
      `amount` las columnas `payment_ref_no` y `transaction_id` con `optional="show"`, y
      `point_of_sale.view_pos_payment_search` para agregar los dos campos al buscador. Verificar: un
      test lee la lista y el buscador de `pos.payment` y comprueba que incluyen los dos campos.
- [x] 1.3 Dar de alta el archivo en `data` de `pos_nave/__manifest__.py`. Verificar: el módulo se
      actualiza sin errores (`-u pos_nave --stop-after-init`).

## 2. Cierre

- [x] 2.1 Subir `pos_nave` a `18.0.1.11.5`. Verificar: el manifiesto declara la versión nueva.
- [x] 2.2 Correr la suite de `pos_nave`, más flake8 y bandit según `.agent/rules.md` §6. Verificar:
      0 fallos, 0 errores de lint y 0 hallazgos de severidad media o superior.
- [ ] 2.3 Desplegar, verificar versión y hash de la vista en el contenedor, y comprobar en producción,
      sobre la orden `POS 1/0019`, que la pestaña *Pagos* muestra `BAQ334646587` y el ID de
      transacción, y que el buscador de *Punto de venta > Órdenes > Pagos* encuentra el pago por
      `BAQ334646587`. Registrar el resultado en `tasks/plan_homologacion_nave.md` (fila F3,
      trazabilidad).
