# Tasks

## 1. El control

- [x] 1.1 En `_process_notification_data`, después de leer el pago y antes de escribir nada, comprobar
      que el pago pertenece a la transacción según la tabla de `design.md`. Si no corresponde,
      registrar una advertencia; si no hay datos, un error. En los dos casos, lanzar
      `ValidationError` sin cambiar la transacción. Verificar con tests:
      - un pago aprobado de otra referencia sobre una transacción cancelada la deja cancelada;
      - lo mismo con la referencia correcta y otra intención;
      - un pago sin `external_payment_id` ni `payment_request_id` no se aplica y deja un error;
      - un pago con sólo `external_payment_id` igual a la referencia se aplica;
      - la aprobación después de un rechazo en la misma intención (A16) sigue pasando a pagada.
- [x] 1.2 Completar las respuestas simuladas de pago de las pruebas existentes con el
      `external_payment_id` de su transacción. Verificar: la suite de `payment_nave` vuelve a pasar
      sin cambiar ninguna aserción de las pruebas existentes.
- [x] 1.3 Probar el webhook y la conciliación. Verificar con tests: por HTTP, el aviso con un pago de
      otra transacción responde 200 y la transacción no cambia; en la conciliación periódica, una
      intención cuyo pago es de otra transacción la deja pendiente y el resto del lote se concilia.

## 2. Cierre

- [x] 2.1 Subir `payment_nave` a `18.0.1.12.5`. Verificar: el manifiesto declara la versión nueva.
- [x] 2.2 Correr las suites de `payment_nave` y `pos_nave`, más flake8 y bandit según
      `.agent/rules.md` §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media o
      superior.
- [ ] 2.3 Desplegar, verificar versión y hash, y repetir en producción el aviso falso. Usar la
      referencia `A5-S00041` (cancelada) y el `payment_id` real de un cobro presencial aprobado.
      Verificar: responde 200, el log lo registra como sospechoso y la transacción sigue cancelada.
      Registrar el resultado en el plan (§3.44, filas E1c y E2c).
