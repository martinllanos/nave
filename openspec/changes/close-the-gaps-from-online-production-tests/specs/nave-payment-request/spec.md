# Spec Delta

## ADDED Requirements

### Requirement: Un documento tiene un solo link cobrable a la vez

Una factura o un pedido NO DEBE quedar con más de un cobro de Nave pendiente que el cliente pueda
pagar. Al generar un link nuevo para un documento, los cobros pendientes anteriores de ese documento
DEBEN darse de baja en el proveedor. Al aprobarse un cobro de un documento, los demás cobros pendientes
de ese documento DEBEN darse de baja. Un cobro dado de baja DEBE quedar cancelado en el sitio.

Un link queda en manos del cliente: en un correo, un mensaje o una pestaña abierta. Si un link viejo
sigue cobrable después de cobrarse el documento, el cliente puede pagarlo dos veces.

#### Scenario: Se genera un link nuevo para una factura que ya tenía uno

- **WHEN** se genera un link para una factura que tiene otro link pendiente
- **THEN** el link anterior se da de baja en el proveedor y su cobro queda cancelado
- **AND** el link nuevo queda como el único cobrable

#### Scenario: Se paga uno de varios cobros pendientes

- **WHEN** se aprueba el cobro de un documento que tiene otros cobros pendientes
- **THEN** los otros cobros se dan de baja en el proveedor y quedan cancelados

#### Scenario: El proveedor no acepta dar de baja un cobro anterior

- **WHEN** el proveedor no confirma la baja de un cobro pendiente
- **THEN** el cobro queda como estaba y el registro del servidor lo anota, para revisarlo
- **AND** la generación del link nuevo o la aprobación del cobro no se interrumpen

### Requirement: La validez del link de pago está acotada

La validez de un link de pago DEBE estar entre 1 y 168 horas. El sitio NO DEBE generar un link con una
validez fuera de ese rango.

El proveedor toma una validez de 0 como 7 días: el link quedaría vigente mucho más de lo que se pidió.

#### Scenario: Validez fuera de rango

- **WHEN** se intenta generar un link con una validez de 0 horas, negativa o mayor a 168 horas
- **THEN** el link no se genera y se indica el rango permitido
