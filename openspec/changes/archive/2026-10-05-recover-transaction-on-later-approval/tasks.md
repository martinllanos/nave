# Tasks

## 1. Recuperación de la transacción

- [x] 1.1 Permitir que una aprobación de Nave lleve a pagada una transacción que un intento anterior
      dejó cancelada, habilitando `cancel` como estado de origen en la llamada a `_set_done` de
      `_process_notification_data`. Verificar con un test: una transacción en `cancel` que recibe un
      webhook `APPROVED` queda en `done` y con el `nave_payment_id` del pago aprobado.
- [x] 1.2 Registrar en el documento que el cobro se concretó tras un intento rechazado, distinguiendo
      el mensaje del de un cobro directo. Verificar con un test que el mensaje de la recuperación
      menciona el intento previo y que un cobro sin rechazos no lo hace.

## 2. Notificaciones que no aplican

- [x] 2.1 Dejar constancia explícita cuando una notificación no pueda aplicarse al estado actual —con
      la referencia y el desenlace descartado—, en lugar de depender del WARNING del modelo base.
      Verificar con un test que un `REJECTED` sobre una transacción ya pagada deja el registro y no
      cambia el estado.
- [x] 2.2 Confirmar que un rechazo tardío no revierte una transacción pagada. Verificar con un test
      que el estado sigue en `done` y que el `nave_payment_id` del pago aprobado no se reemplaza por
      el del intento rechazado.

## 3. Documentación y verificación

- [x] 3.1 Agregar el caso a la matriz del bloque A en `tasks/plan_homologacion_nave.md`: rechazo
      seguido de aprobación sobre la misma intención, con el resultado esperado. Verificar: el caso
      figura con su identificador y su criterio de aceptación.
- [x] 3.2 Correr la suite completa de `payment_nave` y `pos_nave`, más flake8 y bandit según
      `.agent/rules.md` §6. Verificar: 0 fallos, 0 errores de lint y 0 hallazgos de severidad media o
      superior.
- [x] 3.3 Reproducir el caso contra sandbox: pagar con una tarjeta de rechazo y reintentar con una
      aprobada sobre la misma intención. Verificar: la transacción termina en `done`, el pedido se
      confirma, y el chatter muestra el rechazo y la recuperación en orden.
- [x] 3.4 Resolver a mano la transacción `S00005`, que quedó en `cancel` con un cobro real asociado.
      Verificar: queda registrada como pagada o devuelta, con constancia de la decisión tomada.
