# Tasks

## 1. Un rechazo se lee como un rechazo

- [x] 1.1 Clasificar `BLOCKED` junto a los rechazos, en lugar de tratarlo como bloqueo de seguridad,
      y dejar registrado en el código por qué. Verificar: un estado `BLOCKED` produce el aviso de
      rechazo y no el de seguridad.
- [x] 1.2 Actualizar el comentario de `BLOCKED` con lo que documenta Nave —fraude o intentos
      excedidos— y con que el fraude se distingue por el motivo del pago. Verificar: el comentario
      no afirma que `BLOCKED` sea siempre falta de fondos.

## 2. El catálogo de Nave

- [x] 2.1 Crear en `payment_nave` el catálogo de motivos de rechazo y de baja, con el mensaje que
      publica Nave para cada código y traducción diferida, dejando afuera los de jerga interna
      según el diseño. Verificar: cada código de `docs/nave_codigos_referencia.md` está en el
      catálogo o figura entre los excluidos, con el motivo de la exclusión.
- [x] 2.2 Exponer una función que devuelva el mensaje de un código, o nada si no lo conoce.
      Verificar: un test cubre un código conocido, uno desconocido, uno excluido y una fila que
      agrupa varios códigos.

## 3. El backend resuelve el motivo

- [x] 3.1 Dejar de inyectar el nombre del error HTTP como motivo al traducir una intención dada de
      baja. Verificar: la respuesta traducida informa el estado y ningún motivo, y un test lo
      comprueba.
- [x] 3.2 Agregar a la respuesta de la consulta de estado el motivo resuelto —código y mensaje—,
      tomándolo del pago y, sólo si no hay pago, de la intención. Verificar: con un pago
      `no_amount_available` en una intención `BLOCKED` con *"payment retries limit reached"*, el
      motivo resuelto es el del pago.
- [x] 3.3 Con el 400 de baja, buscar el motivo en el cuerpo de la respuesta y resolverlo con el
      catálogo. Verificar: con `manual_disabled_by_user` en el cuerpo, el motivo resuelto es la
      cancelación en la terminal; sin motivo, no se resuelve ninguno.
- [x] 3.4 Registrar en el log el desenlace de cada cobro que llega a un estado final, y el cuerpo
      del 400 de baja. Verificar: un test comprueba que el registro trae el estado, el código y los
      identificadores.

## 4. El aviso

- [x] 4.1 Armar los avisos de rechazo y de baja con el mensaje resuelto, o la descripción genérica
      si no lo hay, más la acción de su categoría. Quitar la heurística de forma. Verificar: el
      aviso nunca interpola un código en la explicación.
- [x] 4.2 Agregar el bloque *"Para soporte"* con el código y los identificadores en todo desenlace
      que no sea un cobro exitoso. Verificar: el bloque aparece separado de la explicación y sólo
      con los datos disponibles.
- [x] 4.3 Reemplazar el test que vigila el fuente del JS por tests del comportamiento del backend,
      y conservar del primero sólo la clasificación de `BLOCKED`, que vive en el navegador.
      Verificar: ningún test depende de los textos del JS.

## 5. Cierre

- [x] 5.1 Subir las versiones de `payment_nave` y `pos_nave`. Verificar: los manifiestos declaran
      las versiones nuevas.
- [x] 5.2 Correr las suites de `payment_nave` y `pos_nave`, más flake8 y bandit según
      `.agent/rules.md` §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media
      o superior.
- [x] 5.3 Desplegar y repetir con la terminal el rechazo por fondos, la cancelación desde la
      terminal y el vencimiento. Verificar: los tres avisos describen la situación, el código
      aparece sólo en el bloque de soporte, el log registra los tres desenlaces, y quedan
      registrados en el plan de homologación con sus capturas. Anotar si el 400 de baja trae el
      motivo.
