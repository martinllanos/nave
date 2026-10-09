# Spec Delta

## ADDED Requirements

### Requirement: El medio de pago de la transacción refleja cómo se pagó

El medio de pago de la transacción DEBE reflejar el instrumento que informa el proveedor, aunque el
cliente haya elegido otro en el sitio: la marca de la tarjeta si pagó con tarjeta, y el QR
interoperable si pagó con billetera o transferencia.

En la página de pago de Nave el cliente puede usar un medio distinto del que eligió en el sitio.

#### Scenario: El cliente eligió tarjeta y pagó con QR

- **WHEN** el cliente eligió *Tarjeta* en el sitio y el proveedor informa un pago con billetera
- **THEN** el medio de pago de la transacción es el QR interoperable

### Requirement: La referencia del proveedor es el código de operación

La referencia del proveedor de la transacción DEBE ser el código de operación que el proveedor muestra
en su panel y en su resumen de liquidaciones.

Es el dato con el que se cruza un cobro de Odoo con lo que informa el proveedor.

#### Scenario: Cobro aprobado

- **WHEN** el proveedor aprueba un cobro
- **THEN** la referencia del proveedor de la transacción es su código de operación
