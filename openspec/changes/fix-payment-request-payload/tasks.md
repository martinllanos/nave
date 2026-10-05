# Tasks

## 1. El detalle de productos se corresponde con el importe

- [ ] 1.1 Extraer la construcción de una entrada del detalle a un único lugar que reciba nombre,
      descripción, cantidad y precio unitario, y que resuelva la cantidad fraccionaria enviando una
      unidad con el subtotal de la línea y la cantidad real al frente de la descripción. Verificar:
      con cantidad entera devuelve la cantidad y el precio unitario tal cual; con cantidad
      fraccionaria devuelve `quantity` 1 y el subtotal como precio unitario.
- [ ] 1.2 Usar esa construcción en las dos ramas de `_nave_get_products_payload` (pedido de venta y
      factura), de modo que ninguna conserve su propio `int(qty) or 1`. Verificar: `grep` no encuentra
      `int(` aplicado a una cantidad en `payment_transaction.py`.
- [ ] 1.3 Usar la misma construcción en el payload del wizard del link de pago. Verificar: una línea
      fraccionaria genera el mismo detalle por el link que por el checkout.
- [ ] 1.4 Cubrir con tests el detalle de las tres procedencias: cantidad entera, cantidad
      fraccionaria, varias líneas mezcladas, y un subtotal con más de dos decimales. Verificar: los
      tests comprueban el payload construido, no el importe cobrado, y pasan.

## 2. El link de pago indica a dónde vuelve el cliente

- [ ] 2.1 Agregar `additional_info.callback_url` al payload del wizard, con la misma URL de retorno
      que arma el checkout. Verificar: un test comprueba que el payload del wizard la incluye y que
      coincide con la del checkout.

## 3. El plazo de validez del checkout es configurable

- [ ] 3.1 Agregar al proveedor el campo del plazo en minutos, con 50 minutos por omisión y una ayuda
      que advierta qué pasa si se lo acorta. Verificar: un proveedor recién creado trae 50.
- [ ] 3.2 Tomar `duration_time` de ese campo al construir la intención del checkout, en lugar del
      valor fijo. Verificar: un test con el campo en otro valor comprueba que el payload lo refleja, y
      otro sin tocarlo comprueba que siguen siendo 3000 segundos.
- [ ] 3.3 Mostrar el campo en la vista del proveedor, junto al resto de la configuración de Nave.
      Verificar: el campo aparece al abrir el proveedor Nave en la interfaz.
- [ ] 3.4 Comprobar que el plazo es independiente por compañía. Verificar: un test con dos compañías,
      cada una con su proveedor y su plazo, obtiene en cada intención el plazo de su compañía.

## 4. Cierre

- [ ] 4.1 Subir la versión del módulo y dejar registrado el cambio donde el proyecto lo lleva.
      Verificar: el manifiesto declara la versión nueva.
- [ ] 4.2 Correr la suite de `payment_nave` y `pos_nave`, más flake8 y bandit según `.agent/rules.md`
      §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media o superior.
- [ ] 4.3 Generar contra sandbox una intención con una línea fraccionaria y confirmar el payload real.
      Verificar: `GET /api/payment_requests/{id}` devuelve un detalle cuyo importe coincide con el
      cobrado, y el caso A13 de la matriz pasa a ✅.
