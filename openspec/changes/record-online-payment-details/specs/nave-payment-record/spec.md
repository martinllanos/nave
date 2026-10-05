# Spec Delta

## Purpose

Define qué queda registrado en Odoo de un cobro procesado por Nave —con qué instrumento se pagó, con
qué financiación y cuánto desembolsó el cliente— para que quien atiende un reclamo o concilia pueda
responder sin entrar al panel del proveedor.

## ADDED Requirements

### Requirement: El instrumento de pago queda registrado

Cuando Nave informa los datos del instrumento con que se pagó, la transacción DEBE conservarlos:
marca, tipo de tarjeta, últimos cuatro dígitos, entidad emisora y modo de ingreso.

La marca DEBE registrarse de modo que aparezca donde Odoo muestra el medio de pago de una
transacción, y no sólo en un campo propio del módulo.

Estos datos los devuelve la verificación de cada cobro y hoy se descartan, con lo cual la única
forma de saber con qué tarjeta pagó alguien es entrar al panel de Nave.

#### Scenario: Cobro con tarjeta

- **WHEN** Nave informa un pago aprobado con tarjeta
- **THEN** la transacción conserva marca, tipo, últimos cuatro dígitos y emisor
- **AND** el medio de pago de la transacción refleja la marca utilizada

#### Scenario: Cobro con billetera

- **WHEN** Nave informa un pago aprobado con billetera, sin datos de tarjeta
- **THEN** la transacción conserva la billetera utilizada
- **AND** los datos de tarjeta quedan vacíos en lugar de rellenarse con valores inventados

### Requirement: La financiación queda registrada

Cuando el pago se hizo en cuotas, la transacción DEBE conservar la cantidad de cuotas, si tienen
interés, la tasa, el costo financiero total y **el importe que efectivamente pagó el cliente**.

Ese importe puede diferir del monto de la venta: el costo financiero lo paga el cliente y no forma
parte de lo que factura el comercio. Sin registrarlo, nada en Odoo indica que la venta se financió.

#### Scenario: Pago en cuotas con interés

- **WHEN** Nave informa un pago aprobado con un plan de cuotas con interés
- **THEN** la transacción conserva la cantidad de cuotas y las condiciones del plan
- **AND** conserva el importe total que pagó el cliente, además del monto de la venta
- **AND** el monto de la venta no se altera

#### Scenario: Pago en una cuota

- **WHEN** Nave informa un pago aprobado sin financiación
- **THEN** la transacción no presenta condiciones de financiación

### Requirement: Los comprobantes del cobro quedan registrados

La transacción DEBE conservar los identificadores con los que Nave y la entidad emisora reconocen la
operación: código de cupón, código de autorización y lote.

Son los datos que se piden al reclamar una operación ante el adquirente, y los que una homologación
presencial exige ver impresos.

#### Scenario: Cobro aprobado

- **WHEN** Nave informa un pago aprobado
- **THEN** la transacción conserva el código de cupón, el de autorización y el lote que Nave informó

### Requirement: El resumen del cobro describe el medio que se usó

El mensaje que la transacción deja en el documento DEBE describir el medio con que se pagó, sin
afirmar datos que no correspondan a ese medio.

Hoy el mensaje nombra siempre la billetera utilizada, de modo que un pago con tarjeta queda
registrado como *"Billetera utilizada: N/A"*, que no informa nada y confunde a quien lo lee.

#### Scenario: Resumen de un pago con tarjeta

- **WHEN** se registra un pago aprobado con tarjeta
- **THEN** el mensaje nombra la marca y los últimos cuatro dígitos
- **AND** no menciona billetera alguna

#### Scenario: Resumen de un pago en cuotas

- **WHEN** se registra un pago aprobado en varias cuotas
- **THEN** el mensaje indica la cantidad de cuotas y el importe que pagó el cliente

#### Scenario: Resumen de un pago con billetera

- **WHEN** se registra un pago aprobado con billetera
- **THEN** el mensaje nombra la billetera utilizada

### Requirement: Los datos del cobro son consultables desde la transacción

Quien abre una transacción de Nave en Odoo DEBE poder ver estos datos sin recurrir al log, a la base
ni al panel del proveedor.

#### Scenario: Consulta de una transacción cobrada

- **WHEN** un usuario con acceso a las transacciones de pago abre una transacción de Nave aprobada
- **THEN** ve el instrumento, los comprobantes y, si la hubo, la financiación
