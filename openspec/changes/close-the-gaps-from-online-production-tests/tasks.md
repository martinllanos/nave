# Tasks

## 1. Un solo link cobrable por documento

- [ ] 1.1 Agregar `_nave_cancel_sibling_requests()` en `payment.transaction`, según `design.md`.
      Verificar con tests: un hermano pendiente recibe el `DELETE` con el motivo fijo y queda
      cancelado; un hermano ya dado de baja (`payment_request_is_disabled`) queda cancelado sin error;
      otra respuesta deja el hermano como estaba y un error en el log; no toca cobros de otros
      documentos ni el propio.
- [ ] 1.2 Llamarla en el asistente antes de crear el cobro nuevo, y en `_process_notification_data`
      después de una aprobación. Registrar una advertencia si el documento ya tenía otro cobro
      aprobado. Verificar con tests: el segundo link de una factura da de baja el primero; la aprobación
      de un cobro da de baja el otro pendiente del mismo pedido; una segunda aprobación del mismo
      documento deja la advertencia de cobro duplicado.

## 2. Conciliación de una intención dada de baja

- [ ] 2.1 En `_nave_poll_payment_request`, tratar `400 payment_request_is_disabled` como `DISABLED`.
      Verificar con tests: la transacción queda cancelada sin excepción; otro 400 sigue propagándose.

## 3. El asistente de link

- [ ] 3.1 Validar la validez entre 1 y 168 horas y decirlo en la ayuda del campo. Verificar con tests:
      0, -1 y 169 se rechazan sin crear un cobro; 1 y 168 se aceptan.
- [ ] 3.2 Armar el mensaje del chatter con `Markup`, con los valores escapados. Verificar con un test:
      el cuerpo publicado tiene un `<a href=…>` real y un valor con `<` aparece escapado.

## 4. Lo que queda registrado del cobro

- [ ] 4.1 Reemplazar `_nave_apply_card_brand` por `_nave_apply_payment_method(payment_data)`.
      Verificar con tests: tarjeta → la marca, como hasta ahora; billetera o transferencia sobre una
      transacción con *Tarjeta* → *QR Interoperable Nave*; sin datos → el medio no cambia.
- [ ] 4.2 Escribir `provider_reference` con `payment_code`. Verificar con un test: un cobro aprobado deja
      el código de operación en `provider_reference`.
- [ ] 4.3 Disparar la tarea de post-proceso después de una aprobación. Verificar con un test: al aprobar
      se llama a `_trigger` de `payment.cron_post_process_payment_tx`, y un rechazo no la dispara.

## 5. Textos del log

- [ ] 5.1 Agregar la indicación `hint` a `_nave_log_invalid_pos` y pasarla desde el POS. Distinguir en
      el controlador un aviso que no se aplica de uno sin transacción. Verificar con tests: el POS anota
      que hay que revisar el método de pago; un aviso sospechoso no menciona el punto de venta.

## 6. Cierre

- [ ] 6.1 Subir `payment_nave` a `18.0.1.13.0` y `pos_nave` a `18.0.1.11.4`. Verificar: los manifiestos
      declaran las versiones nuevas.
- [ ] 6.2 Correr las suites de los dos módulos, más flake8 y bandit según `.agent/rules.md` §6.
      Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media o superior.
- [ ] 6.3 Desplegar, verificar versiones y hashes, y comprobar en producción la lista del *Migration
      Plan* de `design.md`. Registrar el resultado en el plan (§3.47 a §3.50 y filas B1c, B5c, B6c y
      F3).
