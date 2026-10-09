# Spec Delta

## ADDED Requirements

### Requirement: Una intención dada de baja cancela la transacción

Cuando la conciliación periódica consulta una intención que el proveedor dio de baja, la transacción
DEBE quedar cancelada, con el motivo, y NO DEBE registrarse un error.

El proveedor informa la baja de una intención con una respuesta de error, no con un estado. Tomarla
como falla deja la transacción pendiente para siempre y llena el registro de errores falsos.

#### Scenario: La conciliación encuentra una intención dada de baja

- **WHEN** la conciliación periódica consulta una intención y el proveedor responde que está dada de
  baja
- **THEN** la transacción queda cancelada y no se registra un error

### Requirement: Un cobro aprobado se refleja en el documento sin esperar

Cuando un aviso del proveedor aprueba un cobro, el registro contable del pago y el estado del documento
DEBEN actualizarse sin esperar la próxima corrida de la tarea programada. El aviso NO DEBE fallar por
un error en ese registro contable.

Un link se paga fuera del sitio, sin página de retorno. Hasta ahora la factura seguía impaga hasta 10
minutos después del cobro.

#### Scenario: Se paga un link de una factura

- **WHEN** llega el aviso de un cobro aprobado de un link de pago
- **THEN** la factura se actualiza en cuanto termina de procesarse el aviso, sin esperar la corrida de
  la tarea programada
