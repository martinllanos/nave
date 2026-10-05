# Tasks

## 1. Resolución del `pos_id` por medio de cobro

- [x] 1.1 Agregar `nave_payment_link_pos_id` (Char, opcional) a `payment.provider`, con etiqueta que
      nombre el medio y ayuda que indique de dónde se obtiene. Verificar: el campo existe tras
      actualizar el módulo y se puede guardar vacío sin que la validación lo exija.
- [x] 1.2 Agregar al proveedor la resolución del `pos_id` a partir del `payment_type` de Nave,
      siguiendo la misma firma que `_nave_get_api_url`, con fallback a `nave_pos_id` cuando el campo
      del medio está vacío. Verificar con tests: `payment_link` devuelve el campo nuevo cuando está
      cargado, devuelve `nave_pos_id` cuando está vacío, y `ecommerce` devuelve `nave_pos_id` en
      ambos casos.
- [x] 1.3 Registrar el medio y el `pos_id` enviado cuando Nave responde `409 INVALID_POS`, en el
      checkout y en el wizard. Verificar con un test que simule ese 409 y afirme que el log nombra
      ambos datos.

## 2. Puntos de uso

- [x] 2.1 `nave_link_wizard.py`: pedir el `pos_id` declarando `payment_link` en lugar de leer
      `nave_pos_id`. Verificar con un test que, con el campo nuevo cargado, el payload del link viaja
      con ese valor y no con el de la tienda.
- [x] 2.2 `payment_transaction.py`: pedir el `pos_id` declarando el medio que **ya elige el propio
      código** para el endpoint — `payment_link` cuando la transacción tiene factura, `ecommerce` en
      el resto. La redacción original decía sólo `ecommerce`; al implementar se vio que el checkout
      ya ruteaba las facturas del portal al circuito de link, así que ese caso también enviaba el
      `pos_id` equivocado. Verificar con un test que una transacción con factura envía el `pos_id`
      del medio link, y que los tests existentes del checkout siguen pasando.
- [x] 2.3 Mostrar el campo nuevo en la pestaña de credenciales de la vista del proveedor, junto al
      `pos_id` de tienda. Verificar abriendo el formulario del proveedor Nave: los dos campos
      aparecen, cada uno identificado por su medio.

## 3. Verificación de integración

- [x] 3.1 Correr la suite completa de `payment_nave` y `pos_nave`, más flake8 y bandit según
      `.agent/rules.md` §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media
      o superior.
- [ ] 3.2 Cargar el `pos_id` de LINK DE PAGO en el proveedor de producción, generar un link desde una
      factura de prueba y confirmar que Nave lo acepta. Verificar: la respuesta trae `checkout_url`
      en lugar de `409 INVALID_POS`, y queda creada la `payment.transaction` asociada.
      - **Parcial (2026-10-05)**: el `pos_id` quedó cargado y la resolución por medio verificada en
        producción (`ecommerce` → tienda, `payment_link` → el suyo). La generación del link **no se
        pudo completar**: el proveedor tiene credenciales de **sandbox** y la autenticación de
        producción devuelve 401. Ver `tasks/plan_homologacion_nave.md` §3.17. Bloqueada hasta
        cargar las credenciales de producción.
- [ ] 3.3 Confirmar que el checkout del sitio sigue cobrando tras el cambio, con un cobro acotado.
      Verificar: la transacción llega a `done` y el pedido queda confirmado.
