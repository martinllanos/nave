# Tasks

## 1. El backend clasifica el desenlace

- [x] 1.1 Agregar a la respuesta de la consulta de estado el desenlace clasificado —aprobado,
      rechazado, dado de baja, vencido, en espera o desconocido—, incluida la intención dada de
      baja que hoy se traduce del 400. Verificar: un test por cada estado que informa Nave, con
      `BLOCKED` clasificado como rechazo y un estado inventado como desconocido.
- [x] 1.2 Registrar en el log un estado que el módulo no reconoce. Verificar: un test comprueba que
      el registro trae el estado y el identificador de la intención.
- [x] 1.3 Reemplazar el test que lee el fuente del JS para vigilar `BLOCKED` por el de 1.1.
      Verificar: ningún test de `pos_nave` lee el fuente del JS.

## 2. El polling usa la clasificación del backend

- [x] 2.1 Hacer que el polling decida con el desenlace clasificado y quitar `NAVE_STATUS` del
      navegador, sin cambiar los avisos ni los estados que deja en la línea. Verificar: en el
      navegador no queda ninguna lista de estados de Nave, y los avisos de rechazo, baja y
      vencimiento siguen siendo los mismos.
- [x] 2.2 Hacer que, una vez terminado un cobro, cualquier respuesta posterior sobre él se descarte
      sin cambiar la línea ni mostrar avisos. Verificar: leyendo el código, cada punto que recibe una
      respuesta de Nave comprueba si el cobro sigue en curso antes de actuar.

## 3. Forzar la terminación consulta a Nave

- [x] 3.1 Intervenir *Forzar terminación* en la pantalla de pago sólo para las líneas de Nave Point y
      QR interoperable. Verificar: con cualquier otro medio de pago se ejecuta el comportamiento del
      core sin cambios.
- [x] 3.2 Con un cobro en curso, consultar a Nave y terminar el cobro con el desenlace si ya lo hay:
      aprobado como exitoso y el resto como fallido, con su aviso. Verificar: el cobro aprobado carga
      los datos de la tarjeta y respeta la validación automática, igual que uno detectado por el
      polling.
- [x] 3.3 Si Nave todavía espera la tarjeta, o el estado es desconocido, avisar que la terminal sigue
      esperando y que se puede esperar o cancelar, con el bloque de soporte, sin cambiar la línea.
      Si la intención todavía se está creando, avisar que el cobro se está enviando. Verificar: en
      los dos casos la línea sigue esperando y el polling continúa.
- [x] 3.4 Si Nave no responde, pedir confirmación de que el cajero vio la aprobación en la terminal o
      en el cupón. Si confirma, terminar el cobro como exitoso y detener el polling; si no, no
      cambiar nada. Mientras la pregunta está abierta, pausar el polling. Verificar: sin la
      confirmación la línea no queda cobrada, y con la red caída la pregunta no queda huérfana.
- [x] 3.5 Si no hay un cobro en curso en la pantalla, consultar igual y aplicar el desenlace a la
      línea, delegando en el core el caso aprobado. Verificar: después de recargar el POS con una
      línea esperando, el botón no da por cobrado un cobro que Nave no aprobó.

## 4. Cierre

- [x] 4.1 Subir la versión de `pos_nave`. Verificar: el manifiesto declara la versión nueva.
- [x] 4.2 Correr las suites de `payment_nave` y `pos_nave`, más flake8 y bandit según
      `.agent/rules.md` §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media
      o superior.
- [ ] 4.3 Desplegar y probar con la terminal, con importes de $1.200 o menos: forzar la terminación
      mientras espera la tarjeta, después de un rechazo de la terminal y después de una aprobación, y
      con el navegador sin conexión mientras espera la tarjeta. Verificar: sólo la aprobación y la
      confirmación manual dejan la venta cobrada, ningún desenlace tardío reabre una línea cobrada, y
      los resultados quedan en el plan de homologación como reprueba de C9, con sus capturas.
