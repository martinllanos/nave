# Spec Delta

## ADDED Requirements

### Requirement: Si el cobro no se puede crear, el cajero sabe por qué y qué hacer

Cuando el proveedor no acepta crear un cobro presencial, el aviso al cajero DEBE decir en sus
términos qué pasó y qué puede hacer: reintentar, cobrar por otro medio o pedirle al administrador que
corrija la configuración. NO DEBE mostrar como explicación el mensaje técnico del proveedor. El
código del proveedor DEBE quedar en el aviso, aparte, para soporte.

El proveedor informa estos errores con más de un formato. El aviso DEBE ser el mismo para un mismo
error, venga en el formato que venga.

#### Scenario: El identificador configurado es de otro medio de cobro

- **WHEN** el proveedor rechaza el cobro porque el identificador del punto de venta pertenece a otro
  medio de cobro
- **THEN** el cajero lee que hay que corregir la configuración del método de pago y que debe avisar
  al administrador
- **AND** el aviso trae el código del proveedor para soporte
- **AND** el registro del servidor anota el medio y el identificador que se usaron

#### Scenario: El proveedor no puede generar el cobro en este momento

- **WHEN** el proveedor rechaza el cobro porque no pudo generar el QR, no tiene procesadores
  disponibles o el medio de cobro está fuera de servicio
- **THEN** el cajero lee que puede reintentar en unos segundos o cobrar por otro medio

#### Scenario: Un error que no está en el catálogo

- **WHEN** el proveedor rechaza el cobro con un código que el punto de venta no conoce
- **THEN** el aviso se arma como hasta ahora, con lo que informe el proveedor o con una indicación
  según el tipo de falla
