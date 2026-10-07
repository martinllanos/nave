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
