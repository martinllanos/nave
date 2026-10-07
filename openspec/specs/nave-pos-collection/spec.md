# nave-pos-collection Specification

## Purpose

Define cómo el Punto de Venta de Odoo cobra con Nave de forma presencial: cómo espera la resolución
de un cobro lanzado a la terminal o al QR, cuándo deja de esperar y qué entiende el cajero de lo que
está pasando, para que pueda decidir qué hacer sin ir a revisar el equipo.

## Requirements

### Requirement: El punto de venta espera lo que dura la intención

El tiempo que el punto de venta espera la resolución de un cobro DEBE derivarse del plazo con el que
se creó esa intención, y no de un valor propio que haya que mantener sincronizado a mano.

La espera DEBE conceder un margen sobre ese plazo, para que el proveedor alcance a informar el
vencimiento antes de que el punto de venta deje de esperar por su cuenta.

#### Scenario: La intención vence sin cobrarse

- **WHEN** se lanza un cobro a la terminal y nadie paga hasta que la intención vence
- **THEN** el cajero recibe el aviso de que la intención expiró y que debe generar un cobro nuevo
- **AND** no se le pide que verifique el estado en la terminal, porque no hay nada que verificar

#### Scenario: Cambia el plazo de la intención

- **WHEN** se cobra con un plazo de intención distinto al anterior
- **THEN** el punto de venta espera conforme a ese plazo, sin que haya que tocar nada más

### Requirement: El punto de venta deja de esperar aunque el proveedor no conteste

El punto de venta DEBE dejar de esperar un cobro aunque el proveedor nunca informe un desenlace, y
DEBE avisarle al cajero que el resultado quedó sin confirmar.

#### Scenario: El proveedor deja de responder

- **WHEN** se lanza un cobro y el proveedor no informa ningún desenlace, ni siquiera el vencimiento
- **THEN** el punto de venta deja de esperar una vez vencido el plazo con su margen
- **AND** el cajero recibe un aviso que lo distingue de un vencimiento normal y le indica verificar
  el estado en la terminal antes de reintentar

#### Scenario: La línea de pago queda reintentable

- **WHEN** el punto de venta deja de esperar por cualquiera de los dos motivos
- **THEN** la línea de pago queda en condiciones de reintentarse, sin dar la venta por cobrada

### Requirement: El cajero entiende qué pasó y qué puede hacer

Cuando un cobro no se completa, el aviso que recibe el cajero DEBE describir la situación en sus
términos e indicarle qué hacer a continuación.

El motivo DEBE tomarse del pago cuando lo hay, y no de la intención de cobro. El aviso DEBE usar el
mensaje que el proveedor publica para ese motivo y NO DEBE presentar un código como si fuera la
explicación. NO DEBE afirmar una causa que el proveedor no haya informado.

#### Scenario: La tarjeta no tiene fondos

- **WHEN** el cobro se rechaza porque la tarjeta no tiene saldo suficiente
- **THEN** el cajero recibe un aviso de que la tarjeta no tiene fondos suficientes y de que puede
  reintentar o cobrar con otro medio
- **AND** no se le indica contactar al proveedor ni se presenta como un problema de seguridad

#### Scenario: La intención informa un desenlace distinto al del pago

- **WHEN** el pago informa un motivo de rechazo y la intención informa otro, como los intentos
  excedidos
- **THEN** el aviso explica el motivo del pago

#### Scenario: El proveedor informa un motivo que no está en su catálogo

- **WHEN** el motivo informado no tiene un mensaje publicado por el proveedor
- **THEN** el cajero recibe la descripción de la situación y qué hacer, sin motivo

#### Scenario: La intención se dio de baja con un motivo conocido

- **WHEN** la intención se da de baja y el proveedor informa por qué, como una cancelación en la
  terminal
- **THEN** el aviso dice ese motivo y que puede generarse un cobro nuevo

#### Scenario: La intención se dio de baja sin motivo

- **WHEN** la intención se da de baja y el proveedor no informa por qué
- **THEN** el aviso dice que el cobro ya no está disponible y que puede generarse uno nuevo
- **AND** no afirma una causa

#### Scenario: El cobro queda reintentable

- **WHEN** el cobro termina en cualquiera de estas situaciones
- **THEN** la línea de pago queda en condiciones de reintentarse, sin dar la venta por cobrada

### Requirement: Lo que pide la soporte queda a mano

Cuando un cobro no se completa, el aviso DEBE incluir, separados de la explicación y rotulados como
datos para soporte, el código que informó el proveedor y los identificadores del cobro.

El desenlace de cada cobro DEBE quedar registrado en el servidor, con su estado, su motivo y sus
identificadores, aunque el cajero cierre el aviso.

#### Scenario: El cajero llama a soporte después de un rechazo

- **WHEN** un cobro se rechaza y el cajero necesita consultarlo con la soporte del proveedor
- **THEN** el aviso le muestra, bajo un rótulo de soporte, el código tal como lo informó el
  proveedor y los identificadores del pago y de la intención

#### Scenario: El aviso ya se cerró

- **WHEN** el cajero cerró el aviso y hay que averiguar qué pasó con un cobro
- **THEN** el registro del servidor tiene el estado, el motivo y los identificadores de ese cobro
