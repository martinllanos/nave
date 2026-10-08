# Spec Delta

## ADDED Requirements

### Requirement: La línea en espera dice qué espera el cobro

Mientras un cobro presencial espera al cliente, la línea de pago DEBE decirle al cajero qué tiene
que hacer el cliente: apoyar o insertar la tarjeta en la terminal, o escanear el QR.

Con el QR fijo, el cliente tiene que escanear después de que el cobro exista. Si escanea antes, la
billetera le pide el monto y el pago queda fuera del punto de venta, sin ningún aviso. Que la línea
diga que se espera el escaneo le marca al cajero ese momento.

#### Scenario: Cobro con el QR fijo

- **WHEN** un cobro con el QR fijo del local queda esperando al cliente
- **THEN** la línea de pago dice que espera el escaneo del QR

#### Scenario: Cobro con la terminal

- **WHEN** un cobro con la terminal queda esperando al cliente
- **THEN** la línea de pago dice que espera la tarjeta, como hasta ahora
