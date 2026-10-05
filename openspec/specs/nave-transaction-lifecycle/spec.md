# nave-transaction-lifecycle Specification

## Purpose

Define cómo una transacción de pago de Nave atraviesa los sucesivos intentos que admite una misma
intención, qué desenlace registra y qué deja ver de ese recorrido a quien después mira el documento.

## Requirements

### Requirement: Un rechazo no cierra la transacción

Una intención de pago de Nave admite varios intentos. El rechazo de un intento DEBE registrarse como
el resultado de ese intento, y NO DEBE impedir que un intento posterior sobre la misma intención
lleve la transacción a pagada.

Esto importa porque es el camino habitual del cliente al que le rechazan la tarjeta: reintenta con
otra sobre el mismo cobro. Descartar esa aprobación deja dinero cobrado sin registrar, sin que nada
lo advierta.

#### Scenario: Aprobación después de un rechazo

- **WHEN** Nave notifica un pago aprobado para una intención cuyo intento anterior fue rechazado
- **THEN** la transacción queda como pagada
- **AND** queda asociada al pago aprobado, no al rechazado
- **AND** el documento de origen avanza como en cualquier pago aprobado

#### Scenario: Rechazo sin reintento posterior

- **WHEN** un intento es rechazado y no se produce ninguna aprobación posterior
- **THEN** la transacción permanece como no concretada, con el motivo informado por Nave

### Requirement: El recorrido queda visible en el documento

Cuando una transacción llega a pagada después de uno o más rechazos, el documento de origen DEBE
mostrar que hubo intentos fallidos previos y cuál prosperó.

El estado final por sí solo no distingue un cobro directo de uno recuperado, y esa diferencia importa
para quien concilia o atiende al cliente: la venta pudo haberse dado por perdida en el medio.

#### Scenario: Pago recuperado tras un rechazo

- **WHEN** una transacción pasa a pagada después de un rechazo previo
- **THEN** el documento registra que el cobro se concretó tras un intento rechazado
- **AND** el motivo del rechazo anterior sigue siendo consultable

### Requirement: Un desenlace no se pisa con información más vieja

Una notificación que informe un desenlace ya superado NO DEBE revertir el estado de una transacción
ya pagada.

Los intentos de una intención generan notificaciones independientes, y Nave reintenta cada una hasta
cinco veces durante unas siete horas y media, así que una notificación de rechazo puede llegar o
reintentarse después de que otro intento ya prosperó.

#### Scenario: Notificación de rechazo que llega tarde

- **WHEN** llega una notificación de un intento rechazado sobre una transacción ya pagada
- **THEN** la transacción permanece pagada
- **AND** queda constancia de que esa notificación fue recibida y no aplicada
