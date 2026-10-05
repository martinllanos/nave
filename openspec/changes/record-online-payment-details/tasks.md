# Tasks

## 1. Registro del instrumento

- [x] 1.1 Agregar a `payment.transaction` los campos del instrumento —marca, tipo, últimos cuatro
      dígitos, emisor, modo de ingreso y billetera— y completarlos desde la respuesta de
      verificación. Verificar con un test que usa el payload real de un pago con tarjeta: los campos
      quedan cargados con los valores que devolvió Nave.
- [x] 1.2 Resolver la marca contra los `payment.method` de marca del proveedor y escribirla en
      `payment_method_id`, dejándolo como estaba si no hay equivalente. Verificar con tests: una
      marca conocida queda reflejada en el medio de pago de la transacción, y una desconocida
      conserva el texto sin romper el registro.
- [x] 1.3 Verificar que un pago con billetera conserva la billetera y deja vacíos los campos de
      tarjeta, con un test que use el payload real de un cobro por QR.

## 2. Registro de la financiación y los comprobantes

- [x] 2.1 Agregar los campos del plan de cuotas —cantidad, si tiene interés, tasa, costo financiero
      total e importe pagado por el cliente— y completarlos cuando Nave informe un plan. Verificar
      con el payload real del pedido S00007: 3 cuotas, interés, y $1.263,10 contra los $1.150 de la
      venta, que no cambia.
- [x] 2.2 Agregar los campos de comprobante —código de cupón, código de autorización y lote— y
      completarlos. Verificar con un test que los tres quedan registrados a partir de la respuesta.
- [x] 2.3 Verificar que un pago sin financiación no deja condiciones cargadas, con un test de un
      cobro en una cuota.

## 3. Presentación

- [x] 3.1 Componer el mensaje del documento según el medio del cobro: marca y últimos cuatro para
      tarjeta, billetera para billetera, y las cuotas con el importe pagado cuando corresponda.
      Verificar con tests que un pago con tarjeta no menciona billetera y que uno con billetera la
      nombra.
- [x] 3.2 Mostrar instrumento, comprobantes y financiación en el formulario de la transacción.
      Verificar abriendo una transacción aprobada: los datos están visibles sin recurrir al log.

## 4. Verificación de integración

- [x] 4.1 Agregar a la matriz del bloque A el caso que comprueba que los datos del cobro quedan
      registrados, no sólo que el cobro entra. Verificar: el caso figura con su criterio de
      aceptación.
- [x] 4.2 Correr la suite completa de `payment_nave` y `pos_nave`, más flake8 y bandit según
      `.agent/rules.md` §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media o
      superior.
- [ ] 4.3 Cobrar en cuotas contra sandbox y confirmar el registro de punta a punta. Verificar: la
      transacción muestra marca, últimos cuatro, cupón, lote y plan, y el mensaje del documento
      describe el medio sin mencionar billetera.
