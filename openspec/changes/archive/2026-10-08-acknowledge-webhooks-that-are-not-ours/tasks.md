# Tasks

## 1. Lo que se acusa y lo que se reintenta

- [x] 1.1 En `_process_notification_data`, dejar de atrapar el `RequestException` de la consulta del
      pago: registrarlo con el pago y la referencia y volver a lanzarlo, sin llamar a `_set_error`.
      Verificar: un test comprueba que, con la consulta fallando, la excepción sale y la transacción
      sigue `pending`.
- [x] 1.2 Agregar a la conciliación periódica el caso en que la intención se resolvió pero la consulta
      del pago falla. Verificar: un test comprueba que la transacción sigue `pending` y que el resto
      del lote se concilia. Es la variante de `test_22` con la segunda consulta fallando.
- [x] 1.3 En el controlador, envolver `_handle_notification_data` en un savepoint, atrapar
      `ValidationError` aparte, registrarla como información y responder 200. Las demás excepciones
      siguen respondiendo 500. Verificar con pruebas HTTP contra `/payment/nave/webhook`:
      - una referencia inexistente responde 200 y no deja error en el log;
      - una consulta fallida responde 500 y la transacción sigue `pending`;
      - una falla después de una escritura responde 500 y la escritura se descarta;
      - un aviso aprobado sigue respondiendo 200 y deja la transacción `done`.
- [x] 1.4 Actualizar los comentarios del controlador que dicen que toda falla responde 500.
      Verificar: el comentario describe los tres casos (200 acusado, 500 para reintentar, 400 por
      datos inválidos).

## 2. Cierre

- [x] 2.1 Subir `payment_nave` a `18.0.1.12.2`. Verificar: el manifiesto declara la versión nueva.
- [x] 2.2 Correr las suites de `payment_nave` y `pos_nave`, más flake8 y bandit según
      `.agent/rules.md` §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media o
      superior.
- [x] 2.3 Desplegar y verificar en el servidor:
      - un `curl` con una referencia inventada responde 200 (D4c);
      - el próximo cobro presencial recibe un solo aviso, con 200.
      Registrar el resultado en el plan: fila D4c y el hallazgo del webhook en §5.1.
