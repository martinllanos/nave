## ADDED Requirements

### Requirement: Los datos del cobro presencial son consultables desde la orden

Quien abre una orden del punto de venta DEBE ver, en la lista de pagos de la orden y sin abrir
otro registro, el número de referencia y el ID de transacción con los que Nave identifica cada
cobro. El código de autorización DEBE estar disponible en la misma lista como dato opcional.

Esos datos DEBEN ser de sólo lectura en la orden, porque identifican el pago ante Nave.

Desde la lista general de pagos del punto de venta DEBE poder buscarse un pago por su número de
referencia o por su ID de transacción.

#### Scenario: Consulta de una venta cobrada con Nave

- **WHEN** un usuario del punto de venta abre una orden pagada con un medio Nave y va a sus pagos
- **THEN** ve en la fila del pago el número de referencia (el cupón del ticket) y el ID de
  transacción que informó Nave

#### Scenario: Pago sin datos de Nave

- **WHEN** la orden tiene además un pago en efectivo
- **THEN** la fila del efectivo muestra esas columnas vacías y la orden se ve igual que antes en el
  resto

#### Scenario: Intento de modificar el identificador

- **WHEN** un usuario edita la lista de pagos de una orden que todavía admite cambios
- **THEN** no puede modificar el número de referencia, el ID de transacción ni el código de
  autorización

#### Scenario: Del panel de Nave a la venta de Odoo

- **WHEN** un usuario busca en la lista de pagos del punto de venta un número de referencia o un ID
  de transacción que figura en el panel de Nave
- **THEN** encuentra el pago y, con él, la orden a la que pertenece
