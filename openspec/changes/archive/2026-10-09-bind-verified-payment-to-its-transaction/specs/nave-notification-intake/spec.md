# Spec Delta

## ADDED Requirements

### Requirement: Un aviso sólo se aplica con un pago de esa transacción

Antes de aplicar a una transacción el desenlace que confirma el proveedor, el sitio DEBE comprobar
que el pago confirmado pertenece a esa transacción, según los datos que el propio proveedor informa
del pago. Si no pertenece, o si el proveedor no informa a qué transacción pertenece, la transacción
NO DEBE cambiar.

Los avisos no vienen firmados: cualquiera puede mandar uno con la referencia de una transacción y el
identificador de un pago aprobado de otra venta. Confirmar el pago con el proveedor no alcanza si no
se confirma también de quién es.

#### Scenario: El pago confirmado es de otra transacción

- **WHEN** llega un aviso con la referencia de una transacción y el identificador de un pago aprobado
  que pertenece a otra transacción
- **THEN** la transacción no cambia
- **AND** el aviso se acusa como recibido y queda registrado como sospechoso

#### Scenario: El proveedor no informa a qué transacción pertenece el pago

- **WHEN** el proveedor confirma el pago pero no informa a qué transacción pertenece
- **THEN** la transacción no cambia
- **AND** queda registrado como error, para que alguien lo revise

#### Scenario: Un pago aprobado después de un rechazo en la misma intención

- **WHEN** llega el aviso de un pago aprobado de la misma intención que tuvo un intento rechazado
- **THEN** la transacción queda pagada, como hasta ahora

#### Scenario: La conciliación periódica encuentra un pago de otra transacción

- **WHEN** la conciliación periódica obtiene de una intención un pago que no pertenece a la
  transacción
- **THEN** la transacción no cambia y queda registrado como error
